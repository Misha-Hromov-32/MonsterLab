"""Вход через VK ID и Яндекс ID: OAuth 2.0/2.1 с кодом подтверждения и PKCE (S256).

1. start(): случайный state и PKCE-верификатор; в базе — SHA-256 от state и зашифрованный верификатор
   (oauth_states, живут 10 минут). Покупатель уходит на страницу провайдера.
2. Провайдер возвращает его на PUBLIC_URL/auth/<провайдер>/callback с кодом и тем же state;
   фронтенд дополнительно сверяет state со своим (sessionStorage) — чужую ссылку входа не подсунуть.
3. finish(): state одноразовый; код меняется на токен вместе с верификатором, по токену — id и email.
   Токен провайдера дальше не нужен и нигде не хранится.

VK ID: https://id.vk.ru/about/business/go/docs — /authorize, /oauth2/auth (с device_id), /oauth2/user_info.
Яндекс ID: https://yandex.ru/dev/id/doc/ru/ — oauth.yandex.ru/authorize, /token, login.yandex.ru/info.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from .. import config
from . import crypto, db

log = logging.getLogger(__name__)

STATE_TTL_S = 600
TITLES = {"vk": "VK ID", "yandex": "Яндекс ID"}


class OAuthError(RuntimeError):
    """Понятная пользователю причина: ссылка устарела, провайдер не ответил или отказал."""


@dataclass(frozen=True)
class Identity:
    provider: str
    subject: str  # id пользователя у провайдера
    email: str | None  # подтверждённый провайдером адрес или None
    accepted: bool  # покупатель отметил согласия перед входом


def _client_id(provider: str) -> str:
    return {"vk": config.VK_CLIENT_ID, "yandex": config.YANDEX_CLIENT_ID}.get(provider, "")


def enabled() -> list[str]:
    """Провайдеры, для которых заданы ключи (у Яндекса нужен ещё секрет)."""
    out = []
    if config.VK_CLIENT_ID:
        out.append("vk")
    if config.YANDEX_CLIENT_ID and config.YANDEX_CLIENT_SECRET:
        out.append("yandex")
    return out


def redirect_uri(provider: str) -> str:
    # без параметров после «?»: VK ID принимает только точный путь
    return f"{config.PUBLIC_URL}/auth/{provider}/callback"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def start(provider: str, accepted: bool) -> tuple[str, str]:
    """Адрес страницы входа провайдера и state, который фронтенд сверит после возврата."""
    if provider not in enabled():
        raise OAuthError("Этот способ входа сейчас недоступен")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)  # 86 символов — в пределах 43–128 по RFC 7636
    now = time.time()
    with db.connect() as con:
        con.execute("DELETE FROM oauth_states WHERE created_at < ?", (now - STATE_TTL_S,))
        con.execute(
            "INSERT INTO oauth_states (hash, provider, verifier_enc, accepted, created_at) VALUES (?, ?, ?, ?, ?)",
            (crypto.token_hash(state), provider, crypto.encrypt(verifier.encode(), "oauth"), int(accepted), now),
        )
    params = {
        "response_type": "code",
        "client_id": _client_id(provider),
        "redirect_uri": redirect_uri(provider),
        "state": state,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
    }
    if provider == "vk":
        params["scope"] = "vkid.personal_info email"
        return f"https://id.vk.ru/authorize?{urlencode(params)}", state
    params["scope"] = "login:email"
    return f"https://oauth.yandex.ru/authorize?{urlencode(params)}", state


def _consume(provider: str, state: str) -> tuple[str, bool]:
    """Одноразовый state → (PKCE-верификатор, приняты ли согласия)."""
    with db.connect() as con:
        row = con.execute("SELECT * FROM oauth_states WHERE hash = ?", (crypto.token_hash(state),)).fetchone()
        if row is not None:
            con.execute("DELETE FROM oauth_states WHERE hash = ?", (row["hash"],))
    if row is None or row["provider"] != provider or row["created_at"] < time.time() - STATE_TTL_S:
        raise OAuthError("Вход устарел или уже использован — нажмите кнопку входа ещё раз")
    return crypto.decrypt(row["verifier_enc"], "oauth").decode(), bool(row["accepted"])


def _jwt_claims(token: str | None) -> dict:
    """Полезная нагрузка id_token без проверки подписи: токен получен напрямую от провайдера по TLS."""
    try:
        part = (token or "").split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return claims if isinstance(claims, dict) else {}
    except (IndexError, ValueError):
        return {}


def _post(client: httpx.Client, url: str, data: dict, title: str) -> dict:
    r = client.post(url, data=data)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400 or "error" in body:
        log.warning("%s отказал: %s %s", title, r.status_code, str(body or r.text)[:300])
        raise OAuthError(f"{title} не подтвердил вход — попробуйте ещё раз")
    return body


def finish(provider: str, code: str, state: str, device_id: str | None = None) -> Identity:
    verifier, accepted = _consume(provider, state)
    title = TITLES.get(provider, provider)
    try:
        with httpx.Client(timeout=httpx.Timeout(20, connect=10)) as client:
            if provider == "vk":
                if not device_id:
                    raise OAuthError("VK ID не передал данные устройства — попробуйте ещё раз")
                tokens = _post(
                    client,
                    "https://id.vk.ru/oauth2/auth",
                    {
                        "grant_type": "authorization_code",
                        "code": code,
                        "code_verifier": verifier,
                        "client_id": config.VK_CLIENT_ID,
                        "device_id": device_id,
                        "redirect_uri": redirect_uri("vk"),
                        "state": state,
                    },
                    title,
                )
                info = (
                    _post(
                        client,
                        "https://id.vk.ru/oauth2/user_info",
                        {"client_id": config.VK_CLIENT_ID, "access_token": tokens.get("access_token", "")},
                        title,
                    ).get("user")
                    or {}
                )
                claims = _jwt_claims(tokens.get("id_token"))
                subject = str(info.get("user_id") or tokens.get("user_id") or claims.get("sub") or "")
                email = info.get("email") or claims.get("email")
                if claims.get("email_verified") is False:  # явно неподтверждённой почте не верим
                    email = None
            else:
                tokens = _post(
                    client,
                    "https://oauth.yandex.ru/token",
                    {
                        "grant_type": "authorization_code",
                        "code": code,
                        "code_verifier": verifier,
                        "client_id": config.YANDEX_CLIENT_ID,
                        "client_secret": config.YANDEX_CLIENT_SECRET,
                    },
                    title,
                )
                r = client.get(
                    "https://login.yandex.ru/info",
                    params={"format": "json"},
                    headers={"Authorization": f"OAuth {tokens.get('access_token', '')}"},
                )
                if r.status_code >= 400:
                    raise OAuthError(f"{title} не передал данные — попробуйте ещё раз")
                info = r.json()
                subject = str(info.get("id") or "")
                email = info.get("default_email")
    except httpx.HTTPError as exc:
        raise OAuthError(f"{title} сейчас недоступен — попробуйте через минуту") from exc
    except ValueError as exc:  # не JSON
        raise OAuthError(f"{title} ответил непонятно — попробуйте ещё раз") from exc
    if not subject:
        raise OAuthError(f"{title} не передал данные — попробуйте ещё раз")
    return Identity(provider, subject, (email or None) and str(email)[:254], accepted)
