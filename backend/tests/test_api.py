"""HTTP API целиком, классическим движком: загрузка, полка, публичные данные, админка."""

from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.services import site

from .conftest import jpeg_bytes, make_cover


def _upload(client: TestClient, seed: int) -> dict:
    files = {"file": (f"cover-{seed}.jpg", jpeg_bytes(make_cover(seed)), "image/jpeg")}
    r = client.post("/api/analyze", files=files)
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["neural"] is False
    assert body["expert"]["enabled"] is False


def test_analyze_and_shelf(client: TestClient) -> None:
    a, b = _upload(client, 1), _upload(client, 2)
    assert {"id", "grid", "fixations", "palette", "index", "scores", "notes"} <= set(a)

    r = client.post("/api/shelf", data={"variants": json.dumps({"A": a["id"], "B": b["id"]}), "layout": "mobile"})
    assert r.status_code == 200, r.text
    assert set(r.json()["results"]) == {"A", "B"}


def test_rejects_bad_input(client: TestClient) -> None:
    r = client.post("/api/analyze", files={"file": ("x.jpg", b"garbage", "image/jpeg")})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_image"

    r = client.post("/api/shelf", data={"variants": "[1, 2]"})
    assert r.status_code == 422

    too_many = json.dumps({str(i): "x" for i in range(config.MAX_VARIANTS + 1)})
    assert client.post("/api/shelf", data={"variants": too_many}).status_code == 422

    r = client.post("/api/shelf", data={"variants": json.dumps({"A": "unknown"})})
    assert r.json()["detail"]["code"] == "image_expired"


def test_expert_needs_login_then_key(client: TestClient, user_headers: dict) -> None:
    assert client.post("/api/expert/critique", json={"id": "x"}).json()["detail"]["code"] == "login_required"
    r = client.post("/api/expert/critique", json={"id": "whatever"}, headers=user_headers)
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "expert_disabled"


def test_seeded_examples_are_public(client: TestClient) -> None:
    body = client.get("/api/public/site").json()
    assert body["landing"]["title"]
    assert len(body["examples"]) >= 1
    url = body["examples"][0]["variants"][0]["url"]
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_file_route_accepts_only_hex_ids(client: TestClient) -> None:
    # один сегмент пути, но не id: до файловой системы запрос дойти не должен
    for url in ("/api/public/files/ABC/x.jpg", "/api/public/files/0a/..jpg", "/api/public/files/0a/.env"):
        assert client.get(url).status_code == 404, url


def test_admin_requires_token(client: TestClient) -> None:
    assert client.get("/api/admin/settings").status_code == 401
    assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401

    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = client.get("/api/admin/settings", headers=headers).json()
    assert "api_key" not in body["expert"]  # ключ наружу не отдаём

    r = client.put("/api/admin/expert", headers=headers, json={"base_url": "http://evil.example", "models": []})
    assert r.status_code == 422


def test_seed_not_restored_after_delete(client: TestClient) -> None:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    first = site.load()["examples"][0]
    assert client.delete(f"/api/admin/examples/{first['id']}", headers=headers).status_code == 200

    site._cache = None  # как после перезапуска сервера
    assert all(e.get("seed") != first["seed"] for e in site.load()["examples"])


def test_unknown_routes_answer_in_api_format(client: TestClient) -> None:
    for method, url, status in [("GET", "/api/unknown", 404), ("POST", "/api/health", 405)]:
        r = client.request(method, url)
        assert r.status_code == status
        assert set(r.json()["detail"]) == {"code", "message"}


def test_validation_error_names_field_in_russian(client: TestClient, user_headers: dict) -> None:
    body = {"id": "x", "context": {"price": "1" * 50}}
    r = client.post("/api/expert/critique", json=body, headers=user_headers)
    detail = r.json()["detail"]
    assert r.status_code == 422 and "цена" in detail["message"]


def _admin(client: TestClient) -> dict:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_limit_counts_only_failures(client: TestClient) -> None:
    for _ in range(10):
        assert client.post("/api/admin/login", json={"password": "test-password"}).status_code == 200
    for _ in range(5):
        client.post("/api/admin/login", json={"password": "wrong"})
    assert client.post("/api/admin/login", json={"password": "test-password"}).status_code == 429


def test_hero_is_validated_and_cleared(client: TestClient) -> None:
    headers = _admin(client)
    ex = client.post("/api/admin/examples", headers=headers, json={"title": "Тест", "hero": "whatever"}).json()
    assert ex["hero"] is None
    files = [("files", (f"v{i}.jpg", jpeg_bytes(make_cover(i)), "image/jpeg")) for i in range(6)]
    url = f"/api/admin/examples/{ex['id']}/images"
    ex = client.post(url, headers=headers, data={"role": "variants"}, files=files).json()
    assert len(ex["variants"]) == config.MAX_VARIANTS and ex["skipped"] == 2
    assert all(v["url"].endswith(".jpg") for v in ex["variants"])

    body = {"title": "Тест", "hero": "not-a-variant"}
    assert client.put(f"/api/admin/examples/{ex['id']}", headers=headers, json=body).status_code == 422
    hero = ex["variants"][0]["id"]
    client.put(f"/api/admin/examples/{ex['id']}", headers=headers, json={"title": "Тест", "hero": hero})
    ex = client.delete(f"/api/admin/examples/{ex['id']}/images/{hero}", headers=headers).json()
    assert ex["hero"] is None and not site.image_path(ex["id"], hero).exists()
    client.delete(f"/api/admin/examples/{ex['id']}", headers=headers)


def test_expired_image_has_its_own_code(client: TestClient) -> None:
    # без ключа экспертный разбор выключен раньше проверки картинки, поэтому проверяем через полку
    r = client.post("/api/shelf", data={"variants": json.dumps({"A": "gone", "B": "gone2"})})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "image_expired"


def test_gif_is_rejected_like_in_the_interface(client: TestClient) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, format="GIF")
    r = client.post("/api/analyze", files={"file": ("a.gif", buf.getvalue(), "image/gif")})
    assert r.status_code == 422 and "JPG" in r.json()["detail"]["message"]
