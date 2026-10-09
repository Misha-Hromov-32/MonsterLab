"""Покупатели: регистрация с подтверждением email, вход, сброс пароля, тариф и квоты функций.

Всё секретное — в services/crypto.py:
- email в базе зашифрован AES-256-GCM, ищется по «слепому» индексу HMAC-SHA256;
- пароль — Argon2id с солью и секретным «перцем»;
- токен входа "u2.<id>.<срок>.<HMAC-SHA256>" — в базе сессий не храним, но ключ подписи
  включает stamp покупателя: смена пароля меняет stamp и отзывает все выданные токены;
- ссылки из писем одноразовые, в базе лежит только SHA-256 от них.

Пока email не подтверждён, войти нельзя — ни токена, ни функций сервиса.

Тарифы (services/site.py → billing): без оплаты — «демо», разовый набор запусков на всё время;
оплаченный тариф plan_id действует, пока pro_until в будущем, а его квоты считаются с period_start.
"""

from __future__ import annotations

import logging
import re
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage

from .. import config
from . import crypto, db, mail, site

log = logging.getLogger(__name__)

# Редакция правил сервиса (страница /legal). Новая редакция — новая дата здесь и в документах.
LEGAL_VERSION = "2026-10-05"
TOKEN_TTL = 30 * 24 * 3600
TOKEN_PREFIX = "u2"
MIN_PASSWORD = 8
RESEND_COOLDOWN = 60  # не чаще письма в минуту одному покупателю
LINK_TTL = {"verify": mail.VERIFY_TTL_HOURS * 3600, "reset": mail.RESET_TTL_HOURS * 3600}
DEMO = "demo"
FEATURES = ("analyze", "shelf", "expert", "choice", "improve", "competitors")
FEATURE_TITLES = {
    "analyze": "проверок обложек",
    "shelf": "тестов полки",
    "expert": "визуальных разборов",
    "choice": "выборов покупателя",
    "improve": "улучшенных обложек",
    "competitors": "подборов конкурентов",
}
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
# Одноразовые ящики: на них регистрируются ради нового демо-доступа
DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "10minutemail.com",
        "10minutemail.net",
        "guerrillamail.com",
        "guerrillamail.net",
        "sharklasers.com",
        "temp-mail.org",
        "temp-mail.io",
        "tempmail.com",
        "tempmail.net",
        "tempmail.plus",
        "yopmail.com",
        "yopmail.net",
        "trashmail.com",
        "getnada.com",
        "dropmail.me",
        "emailondeck.com",
        "maildrop.cc",
        "mohmal.com",
        "fakeinbox.com",
        "throwawaymail.com",
        "minuteinbox.com",
        "tempr.email",
        "mail.tm",
        "mailnesia.com",
        "spambox.us",
        "tempinbox.com",
        "burnermail.io",
        "inboxkitten.com",
        "1secmail.com",
        "1secmail.net",
        "1secmail.org",
        "emltmp.com",
        "cryptogmail.com",
        "mailpoof.com",
    }
)


# 406-ФЗ (ст. 10.6 закона «Об информации»): пользователей из России сайт авторизует российскими способами.
# По почте регистрируем только на российских почтовых сервисах; остальным — VK ID или Яндекс ID.
# Свои домены (корпоративная почта на российском хостинге) — ALLOWED_EMAIL_DOMAINS в .env.
RUSSIAN_EMAIL_DOMAINS = frozenset(
    {
        # Яндекс
        "yandex.ru",
        "ya.ru",
        "yandex.com",
        "yandex.by",
        "yandex.kz",
        "narod.ru",
        # VK (Почта Mail.ru)
        "mail.ru",
        "inbox.ru",
        "list.ru",
        "bk.ru",
        "internet.ru",
        "vk.com",
        # Рамблер
        "rambler.ru",
        "lenta.ru",
        "autorambler.ru",
        "myrambler.ru",
        "ro.ru",
    }
)
FOREIGN_EMAIL = "Регистрация на эту почту недоступна"


def email_allowed(email: str) -> bool:
    """Можно ли регистрироваться по этой почте (вход через VK ID / Яндекс ID не ограничен — это и есть
    российский способ авторизации, какой бы адрес ни был привязан к аккаунту)."""
    domain = normalize(email).rpartition("@")[2]
    return domain in RUSSIAN_EMAIL_DOMAINS or domain in config.ALLOWED_EMAIL_DOMAINS


class AccountError(ValueError):
    """Понятная пользователю причина: неверный пароль, занятый email и т. п."""


class ConsentRequired(AccountError):
    """Вход через провайдера создал бы новый аккаунт, а согласия с правилами ещё нет."""


class EmailUnverified(AccountError):
    """Пароль верный, но почта ещё не подтверждена."""


class LimitReached(Exception):
    def __init__(self, feature: str, limit: int, plan: str) -> None:
        self.feature, self.limit, self.plan = feature, limit, plan
        what = FEATURE_TITLES.get(feature, "запусков")
        if plan == DEMO:
            text = f"Демо-доступ: {what} больше нет (было {limit}). Выберите тариф, чтобы продолжить."
        else:
            text = f"В этом периоде закончились {what}: {limit}. Перейдите на тариф выше или дождитесь продления."
        super().__init__(text)


@dataclass(frozen=True)
class User:
    id: int
    email: str
    pro_until: float
    verified: bool
    stamp: str
    plan_id: str = ""
    period_start: float = 0

    @property
    def plan(self) -> str:
        """Действующий тариф: id оплаченного, пока он не истёк, иначе «demo»."""
        return (self.plan_id or "pro") if self.pro_until > time.time() else DEMO


def normalize(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    return bool(_EMAIL.match(email))


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
    # сначала подпись, потом расшифровка: поддельный токен не доходит до данных покупателя
    with db.connect() as con:
        row = con.execute("SELECT stamp, verified_at FROM users WHERE id = ?", (int(parts[1]),)).fetchone()
    if row is None or row["verified_at"] is None:
        return None
    if not crypto.verify(".".join(parts[:3]), parts[3], "user/token", row["stamp"].encode()):
        return None
    return get(int(parts[1]))


# ---------------------------------------------------------------- пользователи


def _row(row) -> User | None:
    if row is None:
        return None
    try:
        email = crypto.decrypt(row["email_enc"], "email").decode()
    except crypto.CryptoError:
        # данные зашифрованы другим ключом — скорее всего, сменили MASTER_KEY; покупатель для сервиса «не найден»
        log.error("Не расшифровать email покупателя %s: MASTER_KEY не тот, которым он зашифрован", row["id"])
        return None
    return User(
        row["id"],
        email,
        row["pro_until"],
        row["verified_at"] is not None,
        row["stamp"],
        row["plan_id"] or "",
        row["period_start"] or 0,
    )


def get(user_id: int) -> User | None:
    with db.connect() as con:
        return _row(con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def find(email: str) -> User | None:
    with db.connect() as con:
        return _row(con.execute("SELECT * FROM users WHERE email_index = ?", (_index(email),)).fetchone())


def register(email: str, password: str, accepted: bool = False) -> User:
    """Новый покупатель с неподтверждённой почтой. accepted — приняты пользовательское соглашение
    и дано согласие на обработку персональных данных: без этого аккаунт не создаётся.
    Если он уже регистрировался, но не подтвердил почту, — возвращаем его же и помечаем «спорным»:
    кто из регистрировавшихся владеет почтой, неизвестно, поэтому пароль не меняем, а после
    подтверждения владелец почты задаёт его заново (см. verify_email)."""
    if not accepted:
        raise AccountError("Чтобы зарегистрироваться, примите соглашение и дайте согласие на обработку данных")
    email = normalize(email)
    if not _EMAIL.match(email):
        raise AccountError("Проверьте email")
    if email.rpartition("@")[2] in DISPOSABLE_DOMAINS:
        raise AccountError("Временные почтовые ящики не подходят — укажите свой постоянный email")
    if not email_allowed(email):
        raise AccountError(FOREIGN_EMAIL)
    _check_password_rules(password)
    existing = find(email)
    if existing is not None:
        if existing.verified:
            raise AccountError("Этот email уже зарегистрирован — войдите")
        with db.connect() as con:
            stored = con.execute("SELECT password FROM users WHERE id = ?", (existing.id,)).fetchone()["password"]
        if not crypto.check_password(password, stored):  # тот же пароль — тот же человек нажал ещё раз
            with db.connect() as con:
                con.execute("UPDATE users SET contested = 1 WHERE id = ?", (existing.id,))
        return existing
    hashed = crypto.hash_password(password)  # Argon2 — до транзакции, чтобы не держать базу
    now = time.time()
    try:
        with db.connect() as con:
            cur = con.execute(
                "INSERT INTO users (email_index, email_enc, password, stamp, created_at,"
                " terms_accepted_at, pd_consent_at, legal_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _index(email),
                    crypto.encrypt(email.encode(), "email"),
                    hashed,
                    secrets.token_hex(16),
                    now,
                    now,
                    now,
                    LEGAL_VERSION,
                ),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:  # тот же email только что зарегистрировали параллельно
        return register(email, password, accepted)
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


# ---------------------------------------------------------------- вход через VK ID / Яндекс ID


def _identity_index(provider: str, subject: str) -> str:
    return crypto.blind_index(f"{provider}:{subject}", "identity")


def _create_verified(email_index: str, email: str, now: float) -> int:
    """Новый покупатель после входа через провайдера: почта (если есть) подтверждена провайдером, пароля нет —
    задать его можно через «Забыли пароль». Согласия приняты перед входом. Возвращает id."""
    with db.connect() as con:
        return con.execute(
            "INSERT INTO users (email_index, email_enc, password, stamp, verified_at, created_at,"
            " terms_accepted_at, pd_consent_at, legal_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                email_index,
                crypto.encrypt(email.encode(), "email"),
                crypto.hash_password(secrets.token_urlsafe(32)),
                secrets.token_hex(16),
                now,
                now,
                now,
                now,
                LEGAL_VERSION,
            ),
        ).lastrowid


def oauth_login(provider: str, subject: str, email: str | None, accepted: bool) -> User:
    """Покупатель по входу через провайдера. subject — id у провайдера, email — адрес, подтверждённый провайдером.

    Уже входил так — тот же аккаунт. Иначе ищем по email: есть аккаунт — привязываем провайдера к нему
    (тариф и обложки сохраняются); нет — создаём новый, если приняты правила. Провайдер не передал почту
    (у многих аккаунтов VK её нет) — аккаунт создаётся без почты и находится по id у провайдера.
    Неподтверждённый аккаунт с этим email подтверждаем, а пароль сбрасываем: его мог задать не владелец
    почты (захват аккаунта до регистрации), а владелец только что доказал её через провайдера."""
    index = _identity_index(provider, subject)
    with db.connect() as con:
        row = con.execute("SELECT user_id FROM user_identities WHERE subject_index = ?", (index,)).fetchone()
    if row is not None and (user := get(row["user_id"])) is not None:
        return user
    email = normalize(email or "")
    if email and not _EMAIL.match(email):
        email = ""  # непонятный адрес от провайдера — как будто его нет
    now = time.time()
    existing = find(email) if email else None
    if existing is None:
        if not accepted:
            raise ConsentRequired("Чтобы создать аккаунт, примите соглашение и дайте согласие на обработку данных")
        # без почты email_index — слепой индекс id у провайдера (своё назначение — с адресами не пересекается)
        email_index = _index(email) if email else crypto.blind_index(f"{provider}:{subject}", "no-email")
        try:
            user_id = _create_verified(email_index, email, now)
        except sqlite3.IntegrityError:  # тот же аккаунт только что создали параллельно
            return oauth_login(provider, subject, email, accepted)
    else:
        user_id = existing.id
        if not existing.verified:
            hashed = crypto.hash_password(secrets.token_urlsafe(32))
            with db.connect() as con:
                con.execute(
                    "UPDATE users SET verified_at = ?, password = ?, stamp = ?, contested = 0 WHERE id = ?",
                    (now, hashed, secrets.token_hex(16), user_id),
                )
    with db.connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO user_identities (subject_index, provider, user_id, created_at) VALUES (?, ?, ?, ?)",
            (index, provider, user_id, now),
        )
    user = get(user_id)
    if user is None:
        raise AccountError("Не удалось войти — попробуйте ещё раз")
    return user


def providers(user_id: int) -> list[str]:
    """Через какие сервисы покупатель входил: vk, yandex."""
    with db.connect() as con:
        rows = con.execute("SELECT DISTINCT provider FROM user_identities WHERE user_id = ?", (user_id,)).fetchall()
    return sorted(r["provider"] for r in rows)


# ---------------------------------------------------------------- ссылки из писем


def _issue(user: User, purpose: str, cooldown: bool = True) -> str | None:
    """Новый одноразовый токен для ссылки; None — прошлое письмо ушло меньше минуты назад."""
    now = time.time()
    token, token_hash = crypto.random_token()
    with db.connect() as con:
        con.execute("DELETE FROM email_tokens WHERE expires_at < ?", (now,))
        last = con.execute(
            "SELECT MAX(created_at) FROM email_tokens WHERE user_id = ? AND purpose = ?", (user.id, purpose)
        ).fetchone()[0]
        if cooldown and last and now - last < RESEND_COOLDOWN:
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


def verify_email(token: str) -> tuple[User, str | None]:
    """Подтверждает почту. Второе значение — токен для нового пароля, если пароль нужно задать заново:
    на эту почту регистрировались несколько раз, и пароль мог прийти от чужого человека, который
    заранее занял адрес (захват аккаунта до регистрации). Ссылку открыл владелец почты — пароль
    задаёт он, а прежний перестаёт действовать."""
    user_id = _consume(token, "verify")
    with db.connect() as con:
        row = con.execute("SELECT contested FROM users WHERE id = ?", (user_id,)).fetchone()
        contested = bool(row and row["contested"])
        con.execute("UPDATE users SET verified_at = ? WHERE id = ? AND verified_at IS NULL", (time.time(), user_id))
        if contested:
            con.execute(
                "UPDATE users SET password = ?, stamp = ?, contested = 0 WHERE id = ?",
                (crypto.hash_password(secrets.token_urlsafe(32)), secrets.token_hex(16), user_id),
            )
    user = get(user_id)
    return user, (_issue(user, "reset", cooldown=False) if contested and user else None)


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


def activate(user_id: int, plan_id: str, days: int) -> None:
    """Оплата прошла: тариф plan_id на days дней. Если тариф ещё действует, срок прибавляется
    к оставшемуся; квоты начинаются заново с момента оплаты."""
    now = time.time()
    with db.connect() as con:
        row = con.execute("SELECT pro_until FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return
        until = max(now, row["pro_until"]) + days * 86400
        con.execute(
            "UPDATE users SET pro_until = ?, plan_id = ?, period_start = ? WHERE id = ?",
            (until, plan_id, now, user_id),
        )


# ---------------------------------------------------------------- тарифы и квоты


def plans() -> list[dict]:
    return list(site.read()["billing"]["plans"])


def find_plan(plan_id: str) -> dict | None:
    return next((p for p in plans() if p["id"] == plan_id), None)


def limits(user: User) -> dict[str, int]:
    """Квоты действующего тарифа. Тариф, убранный из настроек, продолжает работать по квотам старшего."""
    billing = site.read()["billing"]
    if user.plan == DEMO:
        quota = billing["demo"]
    else:
        plan = find_plan(user.plan) or max(billing["plans"], key=lambda p: p["price_rub"])
        quota = plan["limits"]
    return {f: int(quota.get(f, 0)) for f in FEATURES}


def _period(user: User) -> str:
    """Ключ периода в таблице usage: «demo» — на всё время, иначе — начало оплаченного периода."""
    return DEMO if user.plan == DEMO else f"p{int(user.period_start)}"


def usage(user: User) -> dict[str, int]:
    with db.connect() as con:
        rows = con.execute("SELECT feature, count FROM usage WHERE user_id = ? AND day = ?", (user.id, _period(user)))
        used = {r["feature"]: r["count"] for r in rows}
    return {f: used.get(f, 0) for f in FEATURES}


def bonus(user: User) -> dict[str, int]:
    """Бонусные запуски по промокодам — сверх квоты тарифа, не сгорают при продлении."""
    with db.connect() as con:
        rows = con.execute("SELECT feature, balance FROM user_bonus WHERE user_id = ?", (user.id,))
        got = {r["feature"]: r["balance"] for r in rows}
    return {f: max(0, got.get(f, 0)) for f in FEATURES}


def check(user: User, feature: str) -> None:
    """До запуска функции: остались ли запуски в квоте тарифа или бонусные."""
    limit = limits(user).get(feature, 0)
    if usage(user)[feature] >= limit and bonus(user)[feature] <= 0:
        raise LimitReached(feature, limit, user.plan)


def spend(user: User, feature: str) -> None:
    """После успешного запуска: списать один запуск — из квоты тарифа, а когда она кончилась, из бонусных.
    Сбой модели запуск не тратит."""
    limit = limits(user).get(feature, 0)
    period = _period(user)
    with db.connect() as con:
        row = con.execute(
            "SELECT count FROM usage WHERE user_id = ? AND feature = ? AND day = ?", (user.id, feature, period)
        ).fetchone()
        used = row["count"] if row else 0
        from_bonus = (
            used >= limit
            and con.execute(
                "UPDATE user_bonus SET balance = balance - 1 WHERE user_id = ? AND feature = ? AND balance > 0",
                (user.id, feature),
            ).rowcount
            == 1
        )
        if not from_bonus:
            con.execute(
                "INSERT INTO usage (user_id, feature, day, count) VALUES (?, ?, ?, 1) "
                "ON CONFLICT (user_id, feature, day) DO UPDATE SET count = count + 1",
                (user.id, feature, period),
            )
        con.execute("INSERT INTO events (ts, user_id, feature) VALUES (?, ?, ?)", (time.time(), user.id, feature))


def extend(user_id: int, days: int) -> None:
    """Продлить действующий тариф на days дней, не меняя сам тариф и не обнуляя квоты (промокод)."""
    with db.connect() as con:
        con.execute("UPDATE users SET pro_until = pro_until + ? WHERE id = ?", (days * 86400, user_id))
