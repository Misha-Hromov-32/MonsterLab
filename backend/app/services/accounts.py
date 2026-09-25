"""Покупатели: регистрация по email и паролю, токены входа, тариф и дневные лимиты платных функций.

Токен = "u1.<id>.<срок>.<HMAC>" — подписан секретом сервера, в базе сессий не храним.
Пароль — scrypt с солью. Тариф «pro» действует, пока pro_until в будущем (продлевает оплата).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass

from . import auth, db, site

TOKEN_TTL = 30 * 24 * 3600
FEATURES = ("expert", "improve", "competitors")
FEATURE_TITLES = {
    "expert": "экспертных разборов",
    "improve": "улучшений обложки",
    "competitors": "подборов конкурентов",
}
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


class AccountError(ValueError):
    """Понятная пользователю причина: неверный пароль, занятый email и т. п."""


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

    @property
    def plan(self) -> str:
        return "pro" if self.pro_until > time.time() else "free"


# ---------------------------------------------------------------- пароли и токены


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _check(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$")
        return hmac.compare_digest(_hash(password, bytes.fromhex(salt)), stored)
    except ValueError:
        return False


def _sign(msg: str) -> str:
    return hmac.new(auth.secret() + b"users", msg.encode(), hashlib.sha256).hexdigest()


def make_token(user: User) -> str:
    body = f"u1.{user.id}.{int(time.time()) + TOKEN_TTL}"
    return f"{body}.{_sign(body)}"


def user_from_token(token: str) -> User | None:
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "u1" or not (parts[1].isdigit() and parts[2].isdigit()):
        return None
    body = ".".join(parts[:3])
    if int(parts[2]) < time.time() or not hmac.compare_digest(parts[3].encode(), _sign(body).encode()):
        return None
    return get(int(parts[1]))


# ---------------------------------------------------------------- пользователи


def _row(row) -> User | None:
    return User(row["id"], row["email"], row["pro_until"]) if row else None


def get(user_id: int) -> User | None:
    with db.connect() as con:
        return _row(con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def register(email: str, password: str) -> User:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise AccountError("Проверьте email")
    if len(password) < 8:
        raise AccountError("Пароль — не короче 8 символов")
    with db.connect() as con:
        if con.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise AccountError("Этот email уже зарегистрирован — войдите")
        cur = con.execute(
            "INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)", (email, _hash(password), time.time())
        )
        return User(cur.lastrowid, email, 0)


def login(email: str, password: str) -> User:
    with db.connect() as con:
        row = con.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if row is None or not _check(password, row["password"]):
        raise AccountError("Неверный email или пароль")
    return _row(row)


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
