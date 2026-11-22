"""SQLite сервиса (DATA_DIR/app.sqlite): покупатели, ссылки из писем, платежи, расход платных функций, кэш выдачи.

Одна короткая транзакция на операцию и общий лок — сервис работает одним процессом,
а запись здесь редкая (вход, оплата, запуск платной функции).
"""

from __future__ import annotations

import sqlite3
import threading
import time
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
-- бонусные запуски сверх квоты тарифа (промокоды): тратятся, когда квота тарифа на функцию исчерпана
CREATE TABLE IF NOT EXISTS user_bonus (
    user_id INTEGER NOT NULL,
    feature TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, feature)
);
-- промокоды: bonus — JSON {функция: сколько прибавить или убавить}, тариф plan_id на plan_days дней,
-- max_uses — всего активаций (0 — без ограничения), expires_at — до какого момента действует
CREATE TABLE IF NOT EXISTS promo_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    note TEXT NOT NULL DEFAULT '',
    bonus TEXT NOT NULL DEFAULT '{}',
    plan_id TEXT,
    plan_days INTEGER NOT NULL DEFAULT 0,
    max_uses INTEGER NOT NULL DEFAULT 0,
    expires_at REAL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
-- кто какой промокод активировал: один покупатель — один раз
CREATE TABLE IF NOT EXISTS promo_redemptions (
    code_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    at REAL NOT NULL,
    PRIMARY KEY (code_id, user_id)
);
-- каждый запрос к ProxyAPI: кто (user_id, NULL — админка или фон), какая функция, модель, токены, успех
CREATE TABLE IF NOT EXISTS ai_calls (
    ts REAL NOT NULL,
    user_id INTEGER,
    feature TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_calls_ts ON ai_calls (ts);
-- баланс ProxyAPI, ₽: новая строка — только когда он изменился; разница соседних строк — списание или пополнение
CREATE TABLE IF NOT EXISTS ai_balance (
    ts REAL NOT NULL,
    balance REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS prepaid_terms (
    id INTEGER PRIMARY KEY, buyer INTEGER NOT NULL, plan TEXT NOT NULL, starts REAL NOT NULL,
    ends REAL NOT NULL, cycle INTEGER NOT NULL, prepaid INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS prepaid_start ON prepaid_terms(starts);
CREATE INDEX IF NOT EXISTS prepaid_buyer ON prepaid_terms(buyer,starts);
CREATE TABLE IF NOT EXISTS partners (
    user_id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, joined REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS referrals (
    buyer INTEGER PRIMARY KEY, partner INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS referrals_partner ON referrals(partner);
CREATE TABLE IF NOT EXISTS commissions (
    payment TEXT PRIMARY KEY, partner INTEGER NOT NULL, kopecks INTEGER NOT NULL, at REAL NOT NULL, payout INTEGER
);
CREATE INDEX IF NOT EXISTS commissions_balance ON commissions(partner, payout);
CREATE TABLE IF NOT EXISTS payouts (
    id INTEGER PRIMARY KEY, partner INTEGER NOT NULL, kopecks INTEGER NOT NULL, details BLOB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', reference TEXT NOT NULL DEFAULT '', at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
    body TEXT NOT NULL, published INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS wb_audits (
    id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, token BLOB, status TEXT NOT NULL, cursor TEXT NOT NULL DEFAULT '{}',
    next_at REAL NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS wb_one_active ON wb_audits(owner) WHERE status IN ('import','photos');
CREATE TABLE IF NOT EXISTS wb_cards (
    audit INTEGER NOT NULL, nm INTEGER NOT NULL, sku TEXT NOT NULL, title TEXT NOT NULL, photo TEXT NOT NULL,
    findings TEXT NOT NULL, checked INTEGER NOT NULL DEFAULT 0, image_status TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(audit,nm)
);
CREATE INDEX IF NOT EXISTS wb_unchecked ON wb_cards(audit,checked,nm);
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
        "quota_json": "TEXT",
        "prepaid": "INTEGER NOT NULL DEFAULT 0",
        "period_start": "REAL",  # начало оплаченного периода — от него считаются квоты
        # на неподтверждённую почту регистрировались повторно — пароль мог задать не владелец
        "cycle_days": "INTEGER",
        "contested": "INTEGER",
    },
    "payouts": {
        "method": "TEXT NOT NULL DEFAULT 'manual'",
        "attempt": "TEXT",
        "provider_id": "TEXT",
        "sent_at": "REAL",
        "poll_at": "REAL",
    },
    "prepaid_terms": {"quota_json": "TEXT"},
    "wb_cards": {"score": "INTEGER"},
    "payments": {
        "plan": "TEXT",
        "provider": "TEXT",
        "quota_json": "TEXT",
        "term_days": "INTEGER",
        "cycle_days": "INTEGER",
    },  # provider: tochka или yookassa (пусто — ЮKassa)
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
                due = con.execute(
                    "SELECT * FROM prepaid_terms WHERE starts<=? ORDER BY starts,id", (time.time(),)
                ).fetchall()
                if due:
                    for term in due:
                        con.execute(
                            "UPDATE users SET pro_until=?,plan_id=?,period_start=?,cycle_days=?,"
                            "prepaid=?,quota_json=? WHERE id=?",
                            (
                                term["ends"],
                                term["plan"],
                                term["starts"],
                                term["cycle"],
                                term["prepaid"],
                                term["quota_json"],
                                term["buyer"],
                            ),
                        )
                        con.execute("DELETE FROM prepaid_terms WHERE id=?", (term["id"],))
                    con.commit()
                yield con
        finally:
            con.close()
