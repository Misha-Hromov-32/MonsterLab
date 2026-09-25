"""Вход в админ-панель: один пароль и подписанный токен без хранения сессий.

Токен = "<срок действия>.<HMAC-SHA256>". Ключ подписи — случайный секрет из DATA_DIR плюс
пароль: смена пароля (после перезапуска) обнуляет все выданные токены.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from functools import cache
from pathlib import Path

from .. import config

log = logging.getLogger(__name__)

TOKEN_TTL = 7 * 24 * 3600
PASSWORD_FILE = config.DATA_DIR / "admin_password.txt"
SECRET_FILE = config.DATA_DIR / ".secret"

_lock = threading.Lock()


def _private_file(path: Path, content: bytes) -> None:
    """Создаёт файл, доступный только владельцу (на Windows права не меняются)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(content)


@cache
def admin_password() -> str:
    """ADMIN_PASSWORD из окружения; если не задан — генерируется один раз и хранится в DATA_DIR."""
    if config.ADMIN_PASSWORD:
        return config.ADMIN_PASSWORD
    with _lock:
        saved = PASSWORD_FILE.read_text("utf-8").strip() if PASSWORD_FILE.exists() else ""
        if not saved:  # файла нет или его очистили — пустой пароль недопустим, генерируем новый
            saved = secrets.token_urlsafe(9)
            _private_file(PASSWORD_FILE, saved.encode())
            log.warning("ADMIN_PASSWORD не задан. Сгенерирован пароль админки: %s", saved)
        return saved


@cache
def secret() -> bytes:
    """Случайный секрет сервера из DATA_DIR — основа подписей токенов (админки и покупателей)."""
    with _lock:
        if not SECRET_FILE.exists():
            _private_file(SECRET_FILE, secrets.token_bytes(32))
        return SECRET_FILE.read_bytes()


@cache
def _signing_key() -> bytes:
    return secret() + admin_password().encode()


def _sign(msg: str) -> str:
    return hmac.new(_signing_key(), msg.encode(), hashlib.sha256).hexdigest()


def check_password(password: str) -> bool:
    given = password.strip().encode()
    return bool(given) and hmac.compare_digest(given, admin_password().encode())


def make_token() -> str:
    exp = str(int(time.time()) + TOKEN_TTL)
    return f"{exp}.{_sign(exp)}"


def verify_token(token: str) -> bool:
    exp, _, sig = token.partition(".")
    return bool(
        exp.isascii()
        and exp.isdigit()
        and len(exp) <= 12  # unix-время, не произвольное число
        and int(exp) >= time.time()
        and hmac.compare_digest(sig.encode("utf-8", "replace"), _sign(exp).encode())
    )
