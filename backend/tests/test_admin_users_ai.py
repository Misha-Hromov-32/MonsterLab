"""Админка: раздел «Пользователи» и расходы на нейросети (баланс ProxyAPI, списания, журнал запросов)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.services import aicost, db

from .conftest import verified_token


@pytest.fixture
def admin(client: TestClient) -> dict:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_users_needs_admin(client: TestClient) -> None:
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/admin/ai").status_code == 401


def test_users_lists_everyone_with_details(client: TestClient, admin: dict) -> None:
    verified_token(client, "listed@example.com")
    body = client.get("/api/admin/users", headers=admin).json()
    assert body["summary"]["total"] == len(body["items"]) >= 2
    me = next(u for u in body["items"] if u["email"] == "listed@example.com")
    assert me["verified"] and me["plan"] == "demo" and me["plan_title"] == "Демо"
    assert set(me["usage"]) == set(me["limits"]) >= {"analyze", "expert"}
    assert me["paid_total"] == 0 and me["payments"] == [] and me["providers"] == []
    session = next(u for u in body["items"] if u["email"] == "session@example.com")
    assert session["plan"] == "agency" and session["pro_until"] > time.time()


@pytest.fixture
def fresh_ai(monkeypatch: pytest.MonkeyPatch):
    with db.connect() as con:
        con.execute("DELETE FROM ai_calls")
        con.execute("DELETE FROM ai_balance")
    aicost._cache.clear()
    balance = {"value": 500.0}
    monkeypatch.setattr(aicost, "fetch_balance", lambda: {"balance": balance["value"], "budget": None})
    return balance


def test_spending_is_split_between_calls(client: TestClient, admin: dict, fresh_ai: dict) -> None:
    aicost.snapshot()  # 500 ₽
    uid = client.get("/api/admin/users", headers=admin).json()["items"][0]["id"]
    token = aicost.CALLER.set((uid, "improve"))
    aicost.record("openai/gpt-image-2", {"input_tokens": 300, "output_tokens": 4000}, True)
    aicost.CALLER.reset(token)
    token = aicost.CALLER.set((None, "check"))
    aicost.record("google/gemini-2.5-flash", {"prompt_tokens": 2, "completion_tokens": 1}, True)
    aicost.record("google/gemini-2.5-flash", None, False)  # ошибка модели — доли списания не получает
    aicost.CALLER.reset(token)
    time.sleep(0.01)
    fresh_ai["value"] = 486.0  # списали 14 ₽
    aicost.snapshot()
    fresh_ai["value"] = 986.0  # пополнили на 500 ₽
    aicost.snapshot()

    body = client.get("/api/admin/ai", headers=admin).json()
    assert body["current"]["balance"] == 986.0
    assert body["spent"]["today"] == 14.0 and body["topups_30"] == 500.0
    topup, spend = body["changes"][:2]
    assert topup["delta"] == 500.0 and spend["delta"] == -14.0 and spend["calls"] == 3
    improve = next(f for f in spend["by_feature"] if f["feature"] == "improve")
    assert improve["rub"] > 13.5  # генерация несравнимо дороже проверки ключа
    image = next(c for c in body["calls"] if c["feature"] == "improve")
    assert image["email"] and image["prompt_tokens"] == 300 and image["completion_tokens"] == 4000
    failed = next(c for c in body["calls"] if not c["ok"])
    assert failed["rub"] is None
    assert sum(f["rub"] for f in body["features"]) == pytest.approx(14.0, abs=0.02)


def test_same_balance_is_not_stored_twice(fresh_ai: dict) -> None:
    aicost.snapshot()
    aicost.snapshot()
    with db.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM ai_balance").fetchone()[0] == 1


def test_balance_without_permission_is_explained(client: TestClient, admin: dict, monkeypatch) -> None:
    aicost._cache.clear()

    def forbidden():
        raise aicost.BalanceError("forbidden", "нет разрешения")

    monkeypatch.setattr(aicost, "fetch_balance", forbidden)
    body = client.get("/api/admin/ai", headers=admin).json()
    assert body["current"]["error"]["code"] == "forbidden"
    assert "changes" in body and "calls" in body


def test_balance_url_only_for_proxyapi() -> None:
    assert aicost._balance_url("https://api.proxyapi.ru/v1") == "https://api.proxyapi.ru/proxyapi/balance"
    with pytest.raises(aicost.BalanceError):
        aicost._balance_url("https://evil.example/v1")
