"""Вход через VK ID и Яндекс ID: PKCE, одноразовый state, привязка к аккаунтам и защита от захвата."""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import oauth

from .conftest import CONSENT, PASSWORD, verified_token


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


@pytest.fixture
def providers(monkeypatch) -> dict:
    """Подменённые VK ID и Яндекс ID. people[код] — кого вернёт провайдер; seen — что пришло в обмен кода."""
    people: dict[str, dict] = {}
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://id.vk.ru/oauth2/auth") or url.startswith("https://oauth.yandex.ru/token"):
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            seen.append(form)
            person = people.get(form["code"])
            if person is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            claims = {"sub": person["id"]}
            if "email_verified" in person:
                claims["email_verified"] = person["email_verified"]
            return httpx.Response(
                200, json={"access_token": f"at-{form['code']}", "id_token": f"h.{_b64(claims)}.s", "user_id": 1}
            )
        token = (
            request.headers.get("authorization", "").removeprefix("OAuth ")
            or parse_qs(request.content.decode()).get("access_token", [""])[0]
        )
        person = people[token.removeprefix("at-")]
        if url.startswith("https://id.vk.ru/oauth2/user_info"):
            return httpx.Response(200, json={"user": {"user_id": person["id"], "email": person.get("email")}})
        return httpx.Response(200, json={"id": person["id"], "default_email": person.get("email")})

    monkeypatch.setattr(config, "VK_CLIENT_ID", "54806327")
    monkeypatch.setattr(config, "YANDEX_CLIENT_ID", "ya-client")
    monkeypatch.setattr(config, "YANDEX_CLIENT_SECRET", "ya-secret")
    real = httpx.Client
    monkeypatch.setattr(oauth.httpx, "Client", lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    return {"people": people, "seen": seen}


def _login(anon: TestClient, provider: str, code: str, consent: bool = True, **extra) -> httpx.Response:
    body = CONSENT if consent else {}
    start = anon.post(f"/api/auth/oauth/{provider}/start", json=body).json()
    q = parse_qs(urlsplit(start["url"]).query)
    assert q["state"] == [start["state"]] and q["code_challenge_method"] == ["S256"]
    return anon.post(
        f"/api/auth/oauth/{provider}/finish",
        json={"code": code, "state": start["state"], "device_id": "dev-1", **extra},
    )


def test_start_uses_pkce_and_exact_redirect(anon: TestClient, providers: dict) -> None:
    start = anon.post("/api/auth/oauth/vk/start", json=CONSENT).json()
    url = urlsplit(start["url"])
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.netloc == "id.vk.ru" and q["client_id"] == "54806327" and "email" in q["scope"]
    assert q["redirect_uri"].endswith("/auth/vk/callback") and "?" not in q["redirect_uri"]
    assert len(q["code_challenge"]) == 43  # SHA-256 в base64url без «=»

    providers["people"]["c1"] = {"id": "vk-1", "email": "pkce@example.com"}
    anon.post("/api/auth/oauth/vk/finish", json={"code": "c1", "state": start["state"], "device_id": "dev-1"})
    sent = providers["seen"][-1]
    assert sent["device_id"] == "dev-1" and sent["redirect_uri"] == q["redirect_uri"]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(sent["code_verifier"].encode()).digest()).rstrip(b"=")
    assert challenge.decode() == q["code_challenge"]


def test_new_vk_user_gets_verified_account_and_same_account_next_time(anon: TestClient, providers: dict) -> None:
    providers["people"]["new"] = {"id": "vk-100", "email": "Vk.User@Example.com"}
    r = _login(anon, "vk", "new")
    assert r.status_code == 200, r.text
    session = r.json()
    assert session["user"]["email"] == "vk.user@example.com" and session["user"]["plan"] == "demo"
    me = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {session['token']}"})
    assert me.status_code == 200

    # почту в VK сменили — вход всё равно в тот же аккаунт: привязка по id у провайдера
    providers["people"]["again"] = {"id": "vk-100", "email": "other@example.com"}
    assert _login(anon, "vk", "again", consent=False).json()["user"]["email"] == "vk.user@example.com"


def test_new_user_without_consent_is_asked_for_it(anon: TestClient, providers: dict) -> None:
    providers["people"]["nc"] = {"id": "vk-200", "email": "noconsent@example.com"}
    r = _login(anon, "vk", "nc", consent=False)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "consent_required"


def test_existing_account_is_linked_not_duplicated(anon: TestClient, providers: dict) -> None:
    verified_token(anon, "linked@example.com")
    providers["people"]["ln"] = {"id": "ya-1", "email": "linked@example.com"}
    r = _login(anon, "yandex", "ln", consent=False)
    assert r.status_code == 200 and r.json()["user"]["email"] == "linked@example.com"
    sent = providers["seen"][-1]
    assert sent["client_secret"] == "ya-secret" and sent["code_verifier"]
    # пароль владельца продолжает работать
    login = anon.post("/api/auth/login", json={"email": "linked@example.com", "password": PASSWORD})
    assert login.status_code == 200


def test_preregistered_password_is_dropped_when_owner_signs_in_with_provider(anon: TestClient, providers: dict) -> None:
    attacker = {"email": "owner@example.com", "password": "пароль-захватчика", **CONSENT}
    assert anon.post("/api/auth/register", json=attacker).status_code == 200
    providers["people"]["own"] = {"id": "vk-300", "email": "owner@example.com"}
    assert _login(anon, "vk", "own").status_code == 200
    assert anon.post("/api/auth/login", json=attacker).status_code == 401


def test_state_is_single_use_and_bound_to_provider(anon: TestClient, providers: dict) -> None:
    providers["people"]["s1"] = {"id": "vk-400", "email": "state@example.com"}
    start = anon.post("/api/auth/oauth/vk/start", json=CONSENT).json()
    wrong = anon.post("/api/auth/oauth/yandex/finish", json={"code": "s1", "state": start["state"]})
    assert wrong.status_code == 422  # state выдан для VK — и после попытки он уже погашен
    again = anon.post("/api/auth/oauth/vk/finish", json={"code": "s1", "state": start["state"], "device_id": "d"})
    assert again.status_code == 422 and again.json()["detail"]["code"] == "oauth_failed"


def test_vk_without_email_gets_account_by_vk_id(anon: TestClient, providers: dict) -> None:
    providers["people"]["ne"] = {"id": "vk-500"}
    assert _login(anon, "vk", "ne", consent=False).json()["detail"]["code"] == "consent_required"
    first = _login(anon, "vk", "ne")
    assert first.status_code == 200, first.text
    me = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {first.json()['token']}"}).json()
    assert me["email"] == "" and me["providers"] == ["vk"] and me["plan"] == "demo"
    # следующий вход тем же VK — тот же аккаунт, даже без согласий
    providers["people"]["ne2"] = {"id": "vk-500"}
    again = _login(anon, "vk", "ne2", consent=False).json()
    assert again["token"].split(".")[1] == first.json()["token"].split(".")[1]


def test_unverified_provider_email_does_not_open_someone_elses_account(anon: TestClient, providers: dict) -> None:
    verified_token(anon, "vk-victim@example.com")
    providers["people"]["uv"] = {"id": "vk-501", "email": "vk-victim@example.com", "email_verified": False}
    r = _login(anon, "vk", "uv")
    assert r.status_code == 200 and r.json()["user"]["email"] == ""  # отдельный аккаунт без почты


def test_disabled_provider_and_bad_code(anon: TestClient, providers: dict, monkeypatch) -> None:
    assert _login(anon, "vk", "unknown-code").json()["detail"]["code"] == "oauth_failed"
    monkeypatch.setattr(config, "YANDEX_CLIENT_SECRET", "")
    r = anon.post("/api/auth/oauth/yandex/start", json=CONSENT)
    assert r.status_code == 503
    assert anon.post("/api/auth/oauth/github/start", json=CONSENT).status_code == 404
    assert anon.get("/api/health").json()["features"]["oauth"] == ["vk"]
