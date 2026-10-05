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
CREATE TABLE IF NOT EXISTS personal_covers (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    digest TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    jpeg BLOB NOT NULL,
    preview BLOB NOT NULL,
    report TEXT,
    baseline REAL,
    created_at REAL NOT NULL,
    UNIQUE(user_id, digest)
);
CREATE INDEX IF NOT EXISTS personal_covers_owner ON personal_covers(user_id, created_at);
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
    legal_version TEXT,
    plan_id TEXT,
    period_start REAL
);
-- ссылки из писем: подтверждение email и сброс пароля. Храним только SHA-256 от токена.
CREATE TABLE IF NOT EXISTS email_tokens (
    hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL
);
-- вход через VK ID / Яндекс ID: какой аккаунт у провайдера к какому покупателю привязан.
-- id у провайдера хранится только «слепым» индексом HMAC-SHA256 от "провайдер:id".
CREATE TABLE IF NOT EXISTS user_identities (
    subject_index TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL
);
-- незавершённые входы через провайдера: SHA-256 от state и зашифрованный PKCE-верификатор, живут 10 минут
CREATE TABLE IF NOT EXISTS oauth_states (
    hash TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    verifier_enc BLOB NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount TEXT NOT NULL,
    status TEXT NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    plan TEXT
);
-- статистика для админки: каждый успешный запуск функции и открытия сайта по дням
CREATE TABLE IF NOT EXISTS events (
    ts REAL NOT NULL,
    user_id INTEGER NOT NULL,
    feature TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
CREATE TABLE IF NOT EXISTS visits (
    day TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
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
ADDED_COLUMNS = {
    "users": {
        "terms_accepted_at": "REAL",
        "pd_consent_at": "REAL",
        "legal_version": "TEXT",
        "plan_id": "TEXT",  # оплаченный тариф; действует, пока pro_until в будущем
        "period_start": "REAL",  # начало оплаченного периода — от него считаются квоты
        # на неподтверждённую почту регистрировались повторно — пароль мог задать не владелец
        "contested": "INTEGER",
    },
    "payments": {"plan": "TEXT", "provider": "TEXT"},  # provider: tochka или yookassa (пусто — ЮKassa)
}

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
