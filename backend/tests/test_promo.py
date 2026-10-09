"""Промокоды: создание в админке, активация покупателем, бонусные запуски и тариф по промокоду."""

from __future__ import annotations

import time
from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.services import accounts

from .conftest import verified_token

_codes = count(1)


@pytest.fixture
def admin(client: TestClient) -> dict:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client: TestClient, admin: dict, **fields) -> dict:
    body = {"code": f"PROMO{next(_codes)}", "bonus": {"analyze": 5}, **fields}
    r = client.post("/api/admin/promo", json=body, headers=admin)
    assert r.status_code == 200, r.text
    return next(p for p in r.json()["items"] if p["code"] == body["code"].upper())


def _user(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {verified_token(client)}"}


def _redeem(client: TestClient, auth: dict, code: str):
    return client.post("/api/promo/redeem", json={"code": code}, headers=auth)


def test_promo_adds_bonus_once_per_user(client: TestClient, admin: dict) -> None:
    p = _create(client, admin, bonus={"analyze": 10, "expert": 2}, note="Для блогера")
    alice = _user(client)
    r = _redeem(client, alice, p["code"].lower())  # регистр не важен
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"]["bonus"] == {"analyze": 10, "expert": 2}
    assert body["user"]["bonus"]["analyze"] == 10 and body["user"]["bonus"]["expert"] == 2
    again = _redeem(client, alice, p["code"])
    assert again.status_code == 422 and again.json()["detail"]["message"] == "Вы уже активировали этот промокод"
    listed = next(x for x in client.get("/api/admin/promo", headers=admin).json()["items"] if x["id"] == p["id"])
    assert listed["uses"] == 1 and listed["note"] == "Для блогера"


def test_max_uses_expiry_and_inactive(client: TestClient, admin: dict) -> None:
    limited = _create(client, admin, max_uses=1)
    assert _redeem(client, _user(client), limited["code"]).status_code == 200
    assert _redeem(client, _user(client), limited["code"]).json()["detail"]["message"] == "Промокод закончился"

    expired = _create(client, admin, expires_at=time.time() - 60)
    assert (
        _redeem(client, _user(client), expired["code"]).json()["detail"]["message"] == "Срок действия промокода истёк"
    )

    off = _create(client, admin, active=False)
    assert _redeem(client, _user(client), off["code"]).json()["detail"]["message"] == "Промокод не найден"
    assert _redeem(client, _user(client), "НЕТ-ТАКОГО").json()["detail"]["message"] == "Промокод не найден"


def test_negative_and_mixed_bonus_never_below_zero(client: TestClient, admin: dict) -> None:
    plus = _create(client, admin, bonus={"shelf": 3, "improve": 4})
    minus = _create(client, admin, bonus={"shelf": -5, "improve": -1, "choice": 2})
    auth = _user(client)
    _redeem(client, auth, plus["code"])
    bonus = _redeem(client, auth, minus["code"]).json()["user"]["bonus"]
    assert bonus["shelf"] == 0 and bonus["improve"] == 3 and bonus["choice"] == 2


def test_bonus_is_spent_after_plan_quota(client: TestClient, admin: dict) -> None:
    auth = _user(client)
    me = client.get("/api/auth/me", headers=auth).json()
    user = accounts.find(me["email"])
    limit = me["limits"]["analyze"]
    for _ in range(limit):
        accounts.spend(user, "analyze")
    with pytest.raises(accounts.LimitReached):
        accounts.check(user, "analyze")

    p = _create(client, admin, bonus={"analyze": 2})
    _redeem(client, auth, p["code"])
    accounts.check(user, "analyze")  # квота кончилась, но есть бонусные
    accounts.spend(user, "analyze")
    me = client.get("/api/auth/me", headers=auth).json()
    assert me["bonus"]["analyze"] == 1 and me["usage"]["analyze"] == limit  # списан бонус, не квота


def test_promo_plan_for_demo_and_extension_for_paid(client: TestClient, admin: dict) -> None:
    p = _create(client, admin, bonus={}, plan_id="start", plan_days=7)
    demo = _user(client)
    me = _redeem(client, demo, p["code"]).json()["user"]
    assert me["plan"] == "start" and me["pro_until"] > time.time() + 6 * 86400

    paid = _user(client)
    email = client.get("/api/auth/me", headers=paid).json()["email"]
    accounts.activate(accounts.find(email).id, "agency", 30)
    before = client.get("/api/auth/me", headers=paid).json()["pro_until"]
    me = _redeem(client, paid, p["code"]).json()["user"]
    assert me["plan"] == "agency"  # платный тариф не меняется на тариф из промокода — только продлевается
    assert abs(me["pro_until"] - before - 7 * 86400) < 5


def test_admin_validation(client: TestClient, admin: dict) -> None:
    bad = [
        {"code": "EMPTY1", "bonus": {}},
        {"code": "BADFEAT", "bonus": {"teleport": 1}},
        {"code": "NOPLANDAYS", "bonus": {}, "plan_id": "start"},
        {"code": "GHOSTPLAN", "bonus": {}, "plan_id": "gold", "plan_days": 5},
        {"code": "a b", "bonus": {"analyze": 1}},
    ]
    for body in bad:
        assert client.post("/api/admin/promo", json=body, headers=admin).status_code == 422, body
    p = _create(client, admin)
    dup = client.post("/api/admin/promo", json={"code": p["code"], "bonus": {"analyze": 1}}, headers=admin)
    assert dup.status_code == 422 and dup.json()["detail"]["message"] == "Такой код уже есть"
    assert client.get("/api/admin/promo").status_code == 401

    edited = client.put(
        f"/api/admin/promo/{p['id']}", json={"code": p["code"], "bonus": {"expert": 3}}, headers=admin
    ).json()
    assert next(x for x in edited["items"] if x["id"] == p["id"])["bonus"] == {"expert": 3}
    items = client.delete(f"/api/admin/promo/{p['id']}", headers=admin).json()["items"]
    assert all(x["id"] != p["id"] for x in items)


def test_guessing_codes_is_rate_limited(client: TestClient) -> None:
    auth = _user(client)
    codes = [_redeem(client, auth, f"GUESS{i}").status_code for i in range(11)]
    assert codes[:10] == [422] * 10 and codes[10] == 429
