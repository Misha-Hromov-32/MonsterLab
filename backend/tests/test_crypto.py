"""Шифрование, подписи и хэши паролей: services/crypto.py."""

from __future__ import annotations

import pytest

from app.services import crypto


def test_encrypt_roundtrip_and_fresh_nonce() -> None:
    a = crypto.encrypt(b"anna@example.com", "email")
    b = crypto.encrypt(b"anna@example.com", "email")
    assert a != b  # новый nonce — одинаковые адреса в базе не совпадают
    assert crypto.decrypt(a, "email") == b"anna@example.com"


def test_tampered_or_foreign_ciphertext_is_rejected() -> None:
    blob = bytearray(crypto.encrypt(b"anna@example.com", "email"))
    blob[15] ^= 1
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(bytes(blob), "email")
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(crypto.encrypt(b"x", "other"), "email")  # другое назначение — другой ключ
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(b"short", "email")


def test_password_hash() -> None:
    stored = crypto.hash_password("пароль-подлиннее")
    assert stored.startswith("$argon2id$") and "пароль" not in stored
    assert crypto.check_password("пароль-подлиннее", stored)
    assert not crypto.check_password("пароль-подлиннеe", stored)
    assert not crypto.check_password("что угодно", "не хэш")
    assert crypto.hash_password("пароль-подлиннее") != stored  # своя соль у каждого хэша


def test_signatures_depend_on_purpose_and_stamp() -> None:
    sig = crypto.sign("u2.1.2", "user/token", b"stamp")
    assert crypto.verify("u2.1.2", sig, "user/token", b"stamp")
    assert not crypto.verify("u2.1.3", sig, "user/token", b"stamp")
    assert not crypto.verify("u2.1.2", sig, "user/token", b"new-stamp")
    assert not crypto.verify("u2.1.2", sig, "admin/token", b"stamp")


def test_blind_index_is_stable_and_keyed() -> None:
    assert crypto.blind_index("a@b.ru", "email") == crypto.blind_index("a@b.ru", "email")
    assert crypto.blind_index("a@b.ru", "email") != crypto.blind_index("a@b.ru", "other")
