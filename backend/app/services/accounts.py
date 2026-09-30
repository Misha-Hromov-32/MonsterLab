"""Покупатели: регистрация с подтверждением email, вход, сброс пароля, тариф и дневные лимиты.

Всё секретное — в services/crypto.py:
- email в базе зашифрован AES-256-GCM, ищется по «слепому» индексу HMAC-SHA256;
- пароль — Argon2id с солью и секретным «перцем»;
- токен входа "u2.<id>.<срок>.<HMAC-SHA256>" — в базе сессий не храним, но ключ подписи
  включает stamp покупателя: смена пароля меняет stamp и отзывает все выданные токены;
- ссылки из писем одноразовые, в базе лежит только SHA-256 от них.

Пока email не подтверждён, войти нельзя — ни токена, ни функций сервиса.
Тариф «pro» действует, пока pro_until в будущем (продлевает оплата).
"""

from __future__ import annotations

import re
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage

from .. import config
from . import crypto, db, mail, site

TOKEN_TTL = 30 * 24 * 3600
TOKEN_PREFIX = "u2"
MIN_PASSWORD = 8
RESEND_COOLDOWN = 60  # не чаще письма в минуту одному покупателю
LINK_TTL = {"verify": mail.VERIFY_TTL_HOURS * 3600, "reset": mail.RESET_TTL_HOURS * 3600}
FEATURES = ("expert", "improve", "competitors")
FEATURE_TITLES = {
    "expert": "экспертных разборов",
    "improve": "улучшений обложки",
    "competitors": "подборов конкурентов",
}
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


class AccountError(ValueError):
    """Понятная пользователю причина: неверный пароль, занятый email и т. п."""


class EmailUnverified(AccountError):
    """Пароль верный, но почта ещё не подтверждена."""


class LimitReached(Exception):
    def __init__(self, feature: str, limit: int, plan: str) -> None:
        self.feature, self.limit, self.plan = feature, limit, plan
        what = FEATURE_TITLES.get(feature, "запусков")
        hint = " Подписка увеличит лимит." if plan == "free" else " Лимит обновится завтра."
        super().__init__(f"На сегодня исчерпан лимит {what}: {limit}.{hint}")


@dataclass(frozen=True)
class User:
    id: int
    email: str
    pro_until: float
    verified: bool
    stamp: str

    @property
    def plan(self) -> str:
        return "pro" if self.pro_until > time.time() else "free"


def normalize(email: str) -> str:
    return email.strip().lower()


def _index(email: str) -> str:
    return crypto.blind_index(normalize(email), "email")


def _check_password_rules(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AccountError(f"Пароль — не короче {MIN_PASSWORD} символов")


# ---------------------------------------------------------------- токены входа


def make_token(user: User) -> str:
    body = f"{TOKEN_PREFIX}.{user.id}.{int(time.time()) + TOKEN_TTL}"
    return f"{body}.{crypto.sign(body, 'user/token', user.stamp.encode())}"


def user_from_token(token: str) -> User | None:
    """Покупатель по токену: подпись, срок, подтверждённая почта и неизменный с выдачи пароль."""
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != TOKEN_PREFIX or not (parts[1].isdigit() and parts[2].isdigit()):
        return None
    if len(parts[1]) > 12 or len(parts[2]) > 12 or int(parts[2]) < time.time():
        return None
    user = get(int(parts[1]))
    if user is None or not user.verified:
        return None
    body = ".".join(parts[:3])
    return user if crypto.verify(body, parts[3], "user/token", user.stamp.encode()) else None


# ---------------------------------------------------------------- пользователи


def _row(row) -> User | None:
    if row is None:
        return None
    email = crypto.decrypt(row["email_enc"], "email").decode()
    return User(row["id"], email, row["pro_until"], row["verified_at"] is not None, row["stamp"])


def get(user_id: int) -> User | None:
    with db.connect() as con:
        return _row(con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def find(email: str) -> User | None:
    with db.connect() as con:
        return _row(con.execute("SELECT * FROM users WHERE email_index = ?", (_index(email),)).fetchone())


def register(email: str, password: str) -> User:
    """Новый покупатель с неподтверждённой почтой. Если он уже регистрировался, но не подтвердил
    почту, — возвращаем его же (пароль не меняем: иначе чужой человек мог бы перехватить аккаунт)."""
    email = normalize(email)
    if not _EMAIL.match(email):
        raise AccountError("Проверьте email")
    _check_password_rules(password)
    existing = find(email)
    if existing is not None:
        if existing.verified:
            raise AccountError("Этот email уже зарегистрирован — войдите")
        return existing
    hashed = crypto.hash_password(password)  # Argon2 — до транзакции, чтобы не держать базу
    try:
        with db.connect() as con:
            cur = con.execute(
                "INSERT INTO users (email_index, email_enc, password, stamp, created_at) VALUES (?, ?, ?, ?, ?)",
                (_index(email), crypto.encrypt(email.encode(), "email"), hashed, secrets.token_hex(16), time.time()),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:  # тот же email только что зарегистрировали параллельно
        return register(email, password)
    return get(user_id)


def login(email: str, password: str) -> User:
    with db.connect() as con:
        row = con.execute("SELECT * FROM users WHERE email_index = ?", (_index(email),)).fetchone()
    if row is None:
        crypto.dummy_check(password)  # по времени ответа не понять, есть ли такой email
        raise AccountError("Неверный email или пароль")
    if not crypto.check_password(password, row["password"]):
        raise AccountError("Неверный email или пароль")
    if crypto.needs_rehash(row["password"]):  # параметры Argon2 усилили — пересчитываем при входе
        with db.connect() as con:
            con.execute("UPDATE users SET password = ? WHERE id = ?", (crypto.hash_password(password), row["id"]))
    user = _row(row)
    if not user.verified:
        raise EmailUnverified(f"Подтвердите почту: ссылка в письме на {user.email}")
    return user


# ---------------------------------------------------------------- ссылки из писем


def _issue(user: User, purpose: str) -> str | None:
    """Новый одноразовый токен для ссылки; None — прошлое письмо ушло меньше минуты назад."""
    now = time.time()
    token, token_hash = crypto.random_token()
    with db.connect() as con:
        con.execute("DELETE FROM email_tokens WHERE expires_at < ?", (now,))
        last = con.execute(
            "SELECT MAX(created_at) FROM email_tokens WHERE user_id = ? AND purpose = ?", (user.id, purpose)
        ).fetchone()[0]
        if last and now - last < RESEND_COOLDOWN:
            return None
        con.execute(
            "INSERT INTO email_tokens (hash, user_id, purpose, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (token_hash, user.id, purpose, now + LINK_TTL[purpose], now),
        )
    return token


def _send(user: User, purpose: str, letter: Callable[[str, str], EmailMessage]) -> bool:
    """Выпускает ссылку и отправляет письмо. False — письмо недавно уже отправляли.
    Письмо не ушло — ссылку отзываем, чтобы покупатель мог сразу попробовать ещё раз."""
    token = _issue(user, purpose)
    if token is None:
        return False
    try:
        mail.deliver(letter(user.email, f"{config.PUBLIC_URL}/?{purpose}={token}"))
    except mail.MailError:
        with db.connect() as con:
            con.execute("DELETE FROM email_tokens WHERE hash = ?", (crypto.token_hash(token),))
        raise
    return True


def send_verification(user: User) -> bool:
    return False if user.verified else _send(user, "verify", mail.verification_letter)


def send_reset(email: str) -> None:
    """Письмо со ссылкой сброса, если такой покупатель есть. Снаружи ответ одинаковый в любом случае."""
    user = find(email)
    if user is not None:
        _send(user, "reset", mail.reset_letter)


def _consume(token: str, purpose: str) -> int:
    """Проверяет ссылку и гасит её вместе с прежними ссылками той же цели. Возвращает id покупателя."""
    with db.connect() as con:
        row = con.execute(
            "SELECT user_id FROM email_tokens WHERE hash = ? AND purpose = ? AND expires_at >= ?",
            (crypto.token_hash(token.strip()), purpose, time.time()),
        ).fetchone()
        if row is None:
            raise AccountError("Ссылка устарела или уже использована — запросите новую")
        con.execute("DELETE FROM email_tokens WHERE user_id = ? AND purpose = ?", (row["user_id"], purpose))
    return row["user_id"]


def verify_email(token: str) -> User:
    user_id = _consume(token, "verify")
    with db.connect() as con:
        con.execute("UPDATE users SET verified_at = ? WHERE id = ? AND verified_at IS NULL", (time.time(), user_id))
    return get(user_id)


def reset_password(token: str, password: str) -> User:
    """Новый пароль по ссылке из письма. Новый stamp отзывает все прежние входы;
    ссылка пришла на эту почту — значит, почта заодно подтверждена."""
    _check_password_rules(password)
    hashed = crypto.hash_password(password)
    user_id = _consume(token, "reset")
    with db.connect() as con:
        con.execute(
            "UPDATE users SET password = ?, stamp = ?, verified_at = COALESCE(verified_at, ?) WHERE id = ?",
            (hashed, secrets.token_hex(16), time.time(), user_id),
        )
    return get(user_id)


def extend_pro(user_id: int, days: int) -> None:
    """Продлевает подписку: от текущего окончания, если она ещё действует, иначе от сегодня."""
    with db.connect() as con:
        row = con.execute("SELECT pro_until FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return
        start = max(time.time(), row["pro_until"])
        con.execute("UPDATE users SET pro_until = ? WHERE id = ?", (start + days * 86400, user_id))


# ---------------------------------------------------------------- лимиты


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def limits(plan: str) -> dict[str, int]:
    return dict(site.read()["billing"]["limits"][plan])


def usage(user: User) -> dict[str, int]:
    with db.connect() as con:
        rows = con.execute("SELECT feature, count FROM usage WHERE user_id = ? AND day = ?", (user.id, _today()))
        used = {r["feature"]: r["count"] for r in rows}
    return {f: used.get(f, 0) for f in FEATURES}


def check(user: User, feature: str) -> None:
    """До запуска платной функции: есть ли ещё запуски на сегодня."""
    limit = limits(user.plan).get(feature, 0)
    if usage(user)[feature] >= limit:
        raise LimitReached(feature, limit, user.plan)


def spend(user: User, feature: str) -> None:
    """После успешного запуска: списать один запуск. Сбой модели запуск не тратит."""
    with db.connect() as con:
        con.execute(
            "INSERT INTO usage (user_id, feature, day, count) VALUES (?, ?, ?, 1) "
            "ON CONFLICT (user_id, feature, day) DO UPDATE SET count = count + 1",
            (user.id, feature, _today()),
        )
