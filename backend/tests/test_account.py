"""Аккаунты, лимиты тарифов, оплата через ЮKassa и платные инструменты — внешние сервисы подменены."""

from __future__ import annotations

import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import accounts, billing, expert, improve, marketplace

from .conftest import jpeg_bytes, make_cover


def test_register_login_me(client: TestClient) -> None:
    creds = {"email": "Anna@Example.com", "password": "пароль-подлиннее"}
    assert client.post("/api/auth/register", json=creds).status_code == 200
    again = client.post("/api/auth/register", json=creds)
    assert again.status_code == 422 and "уже зарегистрирован" in again.json()["detail"]["message"]

    assert client.post("/api/auth/login", json={**creds, "password": "не тот"}).status_code == 401
    token = client.post("/api/auth/login", json={**creds, "email": "anna@example.com"}).json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "anna@example.com" and me["plan"] == "free"
    assert set(me["usage"]) == set(accounts.FEATURES)


@pytest.mark.parametrize("token", ["", "u1.1.9999999999.bad", "u1.x.y.z", "admin-token"])
def test_bad_user_tokens(client: TestClient, token: str) -> None:
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_short_password_and_bad_email() -> None:
    with pytest.raises(accounts.AccountError):
        accounts.register("не-почта", "достаточно-длинный")
    with pytest.raises(accounts.AccountError):
        accounts.register("ok@example.com", "123")


def _upload(client: TestClient) -> str:
    files = {"file": ("c.jpg", jpeg_bytes(make_cover(3)), "image/jpeg")}
    return client.post("/api/analyze", files=files).json()["id"]


def test_improve_spends_limit_only_on_success(client: TestClient, user_headers: dict, monkeypatch) -> None:
    monkeypatch.setattr(expert, "current_config", lambda: expert.ExpertConfig("key", "https://x.test/v1", ["m"]))
    calls = []

    def fake_generate(jpeg: bytes, prompt: str) -> bytes:
        calls.append(prompt)
        if len(calls) == 1:
            raise improve.ImproveError("сбой")
        return jpeg_bytes(make_cover(9))

    monkeypatch.setattr(improve, "generate", fake_generate)
    image_id = _upload(client)
    first = client.post("/api/improve", json={"id": image_id}, headers=user_headers)
    assert first.status_code == 502  # сбой модели лимит не тратит
    body = {"id": image_id, "issues": ["мелкий текст — укрупнить"]}
    ok = client.post("/api/improve", json=body, headers=user_headers)
    assert ok.status_code == 200 and ok.json()["image"].startswith("data:image/jpeg;base64,")
    assert "мелкий текст" in calls[-1]
    # на бесплатном тарифе — одно улучшение в день
    again = client.post("/api/improve", json={"id": image_id}, headers=user_headers)
    assert again.status_code == 403 and again.json()["detail"]["code"] == "limit_reached"


def test_competitors_from_marketplace(client: TestClient, user_headers: dict, monkeypatch) -> None:
    async def fake_search(query: str, limit: int) -> list[dict]:
        path = marketplace.image_path(marketplace.query_key(query), "123456")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(jpeg_bytes(make_cover(5)))
        return [{"id": "123456", "brand": "Бренд", "name": "Термос"}]

    monkeypatch.setattr(marketplace, "search", fake_search)
    body = client.get("/api/competitors", params={"query": "термос"}, headers=user_headers).json()
    assert body["items"][0]["brand"] == "Бренд"
    assert client.get(body["items"][0]["url"]).headers["content-type"] == "image/jpeg"
    assert client.get("/api/competitors/files/zzzz/1.jpg").status_code == 404
    assert client.get("/api/competitors", params={"query": "термос"}).status_code == 401


def test_choice_percent_sums_to_100() -> None:
    chance = expert.choice_percent({"A": 0.333, "B": 0.333, "C": 0.334})
    assert sum(chance.values()) == 100 and max(chance.values()) - min(chance.values()) <= 1


# ---------------------------------------------------------------- оплата


@pytest.fixture
def yookassa(monkeypatch) -> dict:
    """Подменённая ЮKassa: платежи живут в словаре, статус меняет сам тест."""
    payments: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        if request.method == "POST":
            body = json.loads(request.content)
            pid = f"pay-{len(payments) + 1}"
            payments[pid] = {"id": pid, "status": "pending", "paid": False, "metadata": body["metadata"]}
            confirmation = {"confirmation_url": f"https://pay.test/{pid}"}
            return httpx.Response(200, json={**payments[pid], "confirmation": confirmation})
        pid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=payments[pid]) if pid in payments else httpx.Response(404)

    monkeypatch.setattr(config, "YOOKASSA_SHOP_ID", "123")
    monkeypatch.setattr(config, "YOOKASSA_SECRET_KEY", "test")
    real = httpx.Client
    monkeypatch.setattr(billing.httpx, "Client", lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    return payments


def test_payment_extends_subscription_once(client: TestClient, user_headers: dict, yookassa: dict) -> None:
    url = client.post("/api/billing/checkout", headers=user_headers).json()["url"]
    pid = url.rsplit("/", 1)[-1]

    # уведомление до оплаты и уведомление о чужом платеже ничего не меняют
    client.post("/api/billing/webhook", json={"object": {"id": pid}})
    client.post("/api/billing/webhook", json={"object": {"id": "чужой"}})
    assert client.get("/api/auth/me", headers=user_headers).json()["plan"] == "free"

    yookassa[pid].update(status="succeeded", paid=True)
    for _ in range(2):  # ЮKassa может прислать уведомление повторно
        assert client.post("/api/billing/webhook", json={"object": {"id": pid}}).status_code == 200
    me = client.get("/api/auth/me", headers=user_headers).json()
    assert me["plan"] == "pro"
    assert 29 * 86400 < me["pro_until"] - time.time() <= 30 * 86400  # продлено ровно один раз
    assert me["limits"]["improve"] > 1


def test_checkout_without_shop_is_503(client: TestClient, user_headers: dict) -> None:
    r = client.post("/api/billing/checkout", headers=user_headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "billing_unavailable"


def test_admin_sets_price_and_limits(client: TestClient) -> None:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    limits = {"expert": 5, "improve": 2, "competitors": 4}
    body = {"price_rub": 1490, "period_days": 30, "limits": {"free": limits, "pro": {**limits, "improve": 50}}}
    assert client.put("/api/admin/billing", json=body, headers=headers).status_code == 200
    plan = client.get("/api/billing/plan").json()
    assert plan["price_rub"] == 1490 and plan["limits"]["pro"]["improve"] == 50 and plan["enabled"] is False
    bad = {**body, "price_rub": 0}
    assert client.put("/api/admin/billing", json=bad, headers=headers).status_code == 422
