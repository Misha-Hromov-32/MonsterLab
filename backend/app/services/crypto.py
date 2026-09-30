"""Криптография сервиса — всё, что он хэширует, подписывает и шифрует. Алгоритмы — по рекомендациям OWASP.

- Пароли — Argon2id (победитель Password Hashing Competition, RFC 9106) с солью и секретным «перцем»:
  без мастер-ключа утёкшую базу нельзя перебирать даже по словарю.
- Персональные данные (email) — AES-256-GCM: шифрование с проверкой целостности.
- Поиск по email — «слепой» индекс HMAC-SHA256: адрес находится, но в базе его не видно.
- Подписи токенов — HMAC-SHA256, одноразовые ссылки из писем хранятся как SHA-256.

Все ключи выводятся из одного мастер-ключа (HKDF-SHA256): MASTER_KEY из окружения или, если он
не задан, случайный ключ в DATA_DIR/.master_key, созданный при первом запуске. Сменить мастер-ключ
у работающего сервиса нельзя: зашифрованные email станут нечитаемыми.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import threading
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .. import config

log = logging.getLogger(__name__)

KEY_FILE = config.DATA_DIR / ".master_key"
KEY_BYTES = 32
NONCE_BYTES = 12

# Параметры Argon2id по умолчанию в argon2-cffi — профиль RFC 9106 «low memory»: 64 МБ, 3 прохода.
_hasher = PasswordHasher()
_lock = threading.Lock()


class CryptoError(ValueError):
    """Шифртекст повреждён, подделан или зашифрован другим ключом."""


# ---------------------------------------------------------------- ключи


@cache
def master_key() -> bytes:
    """Мастер-ключ: MASTER_KEY (64 hex-символа) или ключ, сгенерированный в DATA_DIR при первом запуске."""
    if config.MASTER_KEY:
        return config.MASTER_KEY
    with _lock:
        if not KEY_FILE.exists():
            KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_bytes(KEY_BYTES))
            log.warning(
                "MASTER_KEY не задан — сгенерирован ключ %s. Храните копию: без него не прочитать email покупателей",
                KEY_FILE,
            )
        key = KEY_FILE.read_bytes()
    if len(key) != KEY_BYTES:
        raise RuntimeError(f"{KEY_FILE} повреждён: ожидалось {KEY_BYTES} байта")
    return key


@cache
def subkey(purpose: str) -> bytes:
    """Отдельный ключ под каждую задачу (HKDF): утечка одного не раскрывает остальные."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=f"monster-lab/{purpose}".encode())
    return hkdf.derive(master_key())


def hmac256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


# ---------------------------------------------------------------- шифрование


def encrypt(plaintext: bytes, purpose: str) -> bytes:
    """AES-256-GCM: nonce ‖ шифртекст ‖ тег. purpose — и ключ, и связанные данные: шифртекст
    одного назначения не расшифруется как другой."""
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + AESGCM(subkey(f"{purpose}/enc")).encrypt(nonce, plaintext, purpose.encode())


def decrypt(blob: bytes, purpose: str) -> bytes:
    try:
        return AESGCM(subkey(f"{purpose}/enc")).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], purpose.encode())
    except (InvalidTag, ValueError) as exc:
        raise CryptoError("Данные повреждены или зашифрованы другим ключом") from exc


def blind_index(value: str, purpose: str) -> str:
    """Детерминированный «слепой» индекс: найти запись по email, не храня сам email открыто."""
    return hmac256(subkey(f"{purpose}/index"), value.encode()).hex()


def sign(message: str, purpose: str, extra: bytes = b"") -> str:
    """Подпись токена — HMAC-SHA256; extra — секрет, смена которого отзывает все подписи."""
    return hmac256(subkey(purpose) + extra, message.encode()).hex()


def verify(message: str, signature: str, purpose: str, extra: bytes = b"") -> bool:
    return hmac.compare_digest(signature.encode("utf-8", "replace"), sign(message, purpose, extra).encode())


# ---------------------------------------------------------------- пароли


def _peppered(password: str) -> bytes:
    return hmac256(subkey("password/pepper"), password.encode())


def hash_password(password: str) -> str:
    """Argon2id в стандартном формате $argon2id$v=19$m=…,t=…,p=…$соль$хэш."""
    return _hasher.hash(_peppered(password))


def check_password(password: str, stored: str) -> bool:
    try:
        return _hasher.verify(stored, _peppered(password))
    except (VerificationError, InvalidHashError, UnicodeEncodeError):  # неверный пароль или испорченный хэш
        return False


def needs_rehash(stored: str) -> bool:
    """Параметры Argon2 с тех пор усилили — пересчитать хэш при входе."""
    return _hasher.check_needs_rehash(stored)


@cache
def _dummy_hash() -> str:
    return _hasher.hash(b"dummy")


def dummy_check(password: str) -> None:
    """Столько же работы, сколько проверка настоящего пароля: по времени ответа не понять, есть ли такой email."""
    check_password(password, _dummy_hash())


# ---------------------------------------------------------------- ссылки из писем


def random_token() -> tuple[str, str]:
    """Одноразовая ссылка из письма: сам токен (уходит в письмо) и его SHA-256 (хранится в базе)."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
