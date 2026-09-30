"""Изоляция кабинетов, сохранение анализа и повторное открытие без списания квот."""

from app.core.imaging import decode
from app.services import accounts, improve, library

from .conftest import jpeg_bytes, make_cover, verified_token


def test_personal_library_owner_access_and_restore(client, anon):
    owner_token = verified_token(client)
    other_token = verified_token(client)
    owner = {"Authorization": f"Bearer {owner_token}"}
    other = {"Authorization": f"Bearer {other_token}"}
    image = jpeg_bytes(make_cover(771))
    response = client.post("/api/analyze", files={"file": ("my-cover.jpg", image, "image/jpeg")}, headers=owner)
    assert response.status_code == 200, response.text
    report = response.json()
    key = report["library_id"]
    listing = client.get("/api/library", headers=owner)
    assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["name"] == "my-cover.jpg"
    assert client.get("/api/library", headers=other).json()["items"] == []
    assert anon.get("/api/library").status_code == 401
    for suffix in ("", "/download"):
        assert client.get(f"/api/library/{key}{suffix}", headers=other).status_code == 404
        assert anon.get(f"/api/library/{key}{suffix}").status_code == 401
    assert client.delete(f"/api/library/{key}", headers=other).status_code == 404
    usage = client.get("/api/auth/me", headers=owner).json()
    restored = client.get(f"/api/library/{key}", headers=owner)
    assert restored.status_code == 200
    assert restored.json()["analysis"]["index"] == report["index"]
    assert restored.json()["image"].startswith("data:image/jpeg;base64,")
    assert client.get("/api/auth/me", headers=owner).json() == usage
    download = client.get(f"/api/library/{key}/download", headers=owner)
    assert download.status_code == 200 and download.headers["content-type"] == "image/jpeg"
    assert client.delete(f"/api/library/{key}", headers=owner).status_code == 200
    assert client.get(f"/api/library/{key}", headers=owner).status_code == 404


def test_generated_covers_saved_and_deduplicated(client, monkeypatch):
    token = verified_token(client)
    user = accounts.user_from_token(token)
    headers = {"Authorization": f"Bearer {token}"}
    original = jpeg_bytes(make_cover(772))
    generated = jpeg_bytes(make_cover(773))
    first = client.post("/api/analyze", files={"file": ("source.jpg", original, "image/jpeg")}, headers=headers).json()
    monkeypatch.setattr(improve, "generate", lambda jpeg, prompt: generated)
    result = client.post("/api/improve", json={"id": first["id"]}, headers=headers)
    assert result.status_code == 200, result.text
    key = result.json()["library_id"]
    row = library.get(user.id, key)
    assert row["kind"] == "generated" and row["baseline"] is not None
    duplicate = library.save(user.id, decode(generated), "another name.jpg", {"index": 30})
    assert duplicate["library_id"] == key
    assert duplicate["generated_baseline"] == row["baseline"]
    assert library.listing(user.id, 0, 24)["total"] == 2
    restored = client.get(f"/api/library/{key}", headers=headers).json()
    assert restored["analysis"]["index"] == 30
    assert restored["generated_baseline"] == row["baseline"]
