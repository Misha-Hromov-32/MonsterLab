"""SQLite сервиса (DATA_DIR/app.sqlite): покупатели, ссылки из писем, платежи, расход платных функций, кэш выдачи.

Одна короткая транзакция на операцию и общий лок — сервис работает одним процессом,
а запись здесь редкая (вход, оплата, запуск платной функции).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from .. import config

DB_FILE = config.DATA_DIR / "app.sqlite"

SCHEMA = """
-- email хранится зашифрованным (AES-256-GCM), ищется по email_index — HMAC-SHA256 от адреса;
-- password — Argon2id; stamp меняется при смене пароля и отзывает все входы.
-- terms_accepted_at / pd_consent_at / legal_version — когда и с какой редакцией правил покупатель согласился
-- (оператор персональных данных обязан уметь доказать согласие).
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_index TEXT NOT NULL UNIQUE,
    email_enc BLOB NOT NULL,
    password TEXT NOT NULL,
    stamp TEXT NOT NULL,
    verified_at REAL,
    created_at REAL NOT NULL,
    pro_until REAL NOT NULL DEFAULT 0,
    terms_accepted_at REAL,
    pd_consent_at REAL,
    legal_version TEXT
);
-- ссылки из писем: подтверждение email и сброс пароля. Храним только SHA-256 от токена.
CREATE TABLE IF NOT EXISTS email_tokens (
    hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount TEXT NOT NULL,
    status TEXT NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    user_id INTEGER NOT NULL,
    feature TEXT NOT NULL,
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, feature, day)
);
CREATE TABLE IF NOT EXISTS competitor_cache (
    query TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
"""

# Колонки, добавленные после создания таблицы: в уже существующую базу их докладывает _migrate().
ADDED_COLUMNS = {"users": {"terms_accepted_at": "REAL", "pd_consent_at": "REAL", "legal_version": "TEXT"}}

_lock = threading.Lock()


def _migrate(con: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        have = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for name, kind in columns.items():
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Соединение на одну операцию: транзакция фиксируется при выходе, файл закрывается."""
    with _lock:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row
        try:
            with con:
                con.executescript(SCHEMA)
                _migrate(con)
                yield con
        finally:
            con.close()
