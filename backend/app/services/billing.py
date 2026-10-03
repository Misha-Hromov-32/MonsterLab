"""Оплата подписки: Точка Банк (интернет-эквайринг) или ЮKassa — выбирается PAYMENT_PROVIDER.

1. checkout() создаёт платёж у провайдера, запоминает его в таблице payments (покупатель, тариф, сумма)
   и возвращает ссылку на платёжную страницу.
2. Покупатель платит, страница возвращает его на сайт, провайдер присылает уведомление на /api/billing/webhook.
3. confirm() НЕ верит уведомлению: заново запрашивает платёж у провайдера по id и, если он действительно
   оплачен на нужную сумму, один раз продлевает подписку (payments.applied защищает от повторов).
   sync_user() делает то же для недавних платежей покупателя — на случай, если уведомление задержалось.

Точка: https://developers.tochka.com/docs/tochka-api/ — платёжные ссылки с чеком, статус APPROVED.
ЮKassa: https://yookassa.ru/developers/api — статус succeeded.
"""

from __future__ import annotations

import base64
import json
import logging
import ssl
import time
import uuid
from functools import cache
from pathlib import Path

import certifi
import httpx

from .. import config
from . import accounts, db, site

log = logging.getLogger(__name__)

YOOKASSA_API = "https://api.yookassa.ru/v3"
TOCHKA_API = "https://enter.tochka.com/uapi"
# API Точки подписан сертификатом Минцифры — его нет в стандартном списке certifi
RUSSIAN_CA = Path(__file__).resolve().parent.parent / "certs" / "russian_trusted_ca.pem"
TOCHKA_MODES = ["sbp", "card"]
SYNC_WINDOW_S = 2 * 86400  # sync_user проверяет платежи покупателя за последние двое суток
AMOUNT_EPS = 0.009


class BillingError(RuntimeError):
    """Понятная пользователю причина: оплата не подключена, платёжный сервис недоступен."""


def provider() -> str | None:
    """Через кого сейчас принимаем оплату; None — оплата не настроена."""
    if config.PAYMENT_PROVIDER == "tochka":
        return "tochka" if config.TOCHKA_JWT and config.TOCHKA_CUSTOMER_CODE else None
    return "yookassa" if config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET_KEY else None


def enabled() -> bool:
    return provider() is not None


def plans() -> dict:
    """Условия для страницы тарифов: демо-квоты и платные тарифы."""
    billing = site.read()["billing"]
    return {"demo": billing["demo"], "plans": billing["plans"]}


# ---------------------------------------------------------------- клиенты HTTP


@cache
def _tochka_ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(RUSSIAN_CA)
    return ctx


def _client(name: str) -> httpx.Client:
    timeout = httpx.Timeout(20, connect=10)
    if name == "tochka":
        if not config.TOCHKA_JWT:
            raise BillingError("Оплата пока не подключена")
        headers = {"Authorization": f"Bearer {config.TOCHKA_JWT}"}
        return httpx.Client(base_url=TOCHKA_API, headers=headers, timeout=timeout, verify=_tochka_ssl())
    if not (config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET_KEY):
        raise BillingError("Оплата пока не подключена")
    auth = (config.YOOKASSA_SHOP_ID, config.YOOKASSA_SECRET_KEY)
    return httpx.Client(base_url=YOOKASSA_API, auth=auth, timeout=timeout)


def _call(name: str, method: str, path: str, **kw) -> httpx.Response:
    try:
        with _client(name) as client:
            return client.request(method, path, **kw)
    except httpx.HTTPError as exc:
        raise BillingError("Платёжный сервис сейчас недоступен, попробуйте через минуту") from exc


# ---------------------------------------------------------------- создание платежа


def checkout(user: accounts.User, plan_id: str) -> str:
    """Создаёт платёж за тариф plan_id и возвращает адрес страницы оплаты."""
    info = accounts.find_plan(plan_id)
    if info is None:
        raise BillingError("Такого тарифа нет — обновите страницу")
    name = provider()
    if name is None:
        raise BillingError("Оплата пока не подключена")
    price = float(info["price_rub"])
    description = f"MonStoreLab, тариф «{info['title']}» на {info['period_days']} дней"
    make = _tochka_checkout if name == "tochka" else _yookassa_checkout
    payment_id, status, url = make(user, info, price, description)
    with db.connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO payments (id, user_id, amount, status, plan, provider, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payment_id, user.id, f"{price:.2f}", status, info["id"], name, time.time()),
        )
    return url


def _tochka_checkout(user: accounts.User, info: dict, price: float, description: str) -> tuple[str, str, str]:
    data: dict = {
        "customerCode": config.TOCHKA_CUSTOMER_CODE,
        "amount": round(price, 2),
        "purpose": description[:140],
        "redirectUrl": f"{config.PUBLIC_URL}/?payment=return",
        "failRedirectUrl": f"{config.PUBLIC_URL}/?payment=fail",
        "paymentMode": TOCHKA_MODES,
    }
    if config.TOCHKA_MERCHANT_ID:
        data["merchantId"] = config.TOCHKA_MERCHANT_ID
    path = "/acquiring/v1.0/payments"
    if config.TOCHKA_RECEIPT:  # чек по 54-ФЗ: покупатель и одна позиция «услуга»
        path = "/acquiring/v1.0/payments_with_receipt"
        data["Client"] = {"email": user.email}
        data["Items"] = [
            {
                "name": description[:128],
                "amount": round(price, 2),
                "quantity": 1,
                "paymentMethod": "full_payment",
                "paymentObject": "service",
                "vatType": "none",
            }
        ]
        if config.TOCHKA_TAX_SYSTEM:
            data["taxSystemCode"] = config.TOCHKA_TAX_SYSTEM
    r = _call("tochka", "POST", path, json={"Data": data})
    if r.status_code >= 400:
        log.error("Точка отказала в создании платежа: %s %s", r.status_code, r.text[:400])
        raise BillingError("Не удалось создать платёж, попробуйте позже")
    op = r.json()["Data"]
    return op["operationId"], op.get("status") or "CREATED", op["paymentLink"]


def _yookassa_checkout(user: accounts.User, info: dict, price: float, description: str) -> tuple[str, str, str]:
    amount = {"value": f"{price:.2f}", "currency": "RUB"}
    body: dict = {
        "amount": amount,
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": f"{config.PUBLIC_URL}/?payment=return"},
        "description": description,
        "metadata": {"user_id": str(user.id), "plan": info["id"], "days": str(info["period_days"])},
    }
    if config.YOOKASSA_RECEIPT:  # чек по 54-ФЗ: покупатель и одна позиция «услуга»
        body["receipt"] = {
            "customer": {"email": user.email},
            "items": [
                {
                    "description": description[:128],
                    "quantity": "1.00",
                    "amount": amount,
                    "vat_code": config.YOOKASSA_VAT_CODE,
                    "payment_subject": "service",
                    "payment_mode": "full_payment",
                }
            ],
        }
    r = _call("yookassa", "POST", "/payments", json=body, headers={"Idempotence-Key": uuid.uuid4().hex})
    if r.status_code >= 400:
        log.error("ЮKassa отказала в создании платежа: %s %s", r.status_code, r.text[:300])
        raise BillingError("Не удалось создать платёж, попробуйте позже")
    payment = r.json()
    return payment["id"], payment["status"], payment["confirmation"]["confirmation_url"]


# ---------------------------------------------------------------- подтверждение


def _fetch(name: str, payment_id: str) -> tuple[str, bool, float] | None:
    """Статус платежа у провайдера: (статус, оплачен ли, сумма); None — платежа у провайдера нет."""
    if name == "tochka":
        r = _call("tochka", "GET", f"/acquiring/v1.0/payments/{payment_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        ops = r.json()["Data"]["Operation"]
        if not ops:
            return None
        op = ops[0]
        return op["status"], op["status"] == "APPROVED", float(op["amount"])
    r = _call("yookassa", "GET", f"/payments/{payment_id}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    p = r.json()
    paid = p["status"] == "succeeded" and bool(p.get("paid"))
    return p["status"], paid, float(p["amount"]["value"]) if "amount" in p else 0.0


def confirm(payment_id: str) -> bool:
    """Проверяет платёж у провайдера и продлевает подписку, если он оплачен. True — подписка продлена сейчас."""
    with db.connect() as con:
        row = con.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if row is None:  # платёж создан не через нас — не наш
        log.warning("Уведомление о неизвестном платеже %s", payment_id)
        return False
    if row["applied"]:
        return False
    name = row["provider"] or "yookassa"  # платежи до появления Точки — из ЮKassa
    try:
        found = _fetch(name, payment_id)
    except httpx.HTTPStatusError as exc:
        raise BillingError("Платёжный сервис не ответил") from exc
    if found is None:
        return False
    status, paid, amount = found
    with db.connect() as con:
        con.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
        if not paid:
            return False
        if amount + AMOUNT_EPS < float(row["amount"]):
            log.error("Платёж %s: оплачено %.2f вместо %s — тариф не продлеваю", payment_id, amount, row["amount"])
            return False
        # applied ставим в той же транзакции, что и проверяем: повторное уведомление ничего не продлит
        if con.execute("UPDATE payments SET applied = 1 WHERE id = ? AND applied = 0", (payment_id,)).rowcount != 1:
            return False
    plan = accounts.find_plan(row["plan"] or "")
    days = int(plan["period_days"]) if plan else 30
    accounts.activate(row["user_id"], row["plan"] or "pro", days)
    log.info("Тариф %s оплачен: пользователь %s, платёж %s (%s)", row["plan"], row["user_id"], payment_id, name)
    return True


def sync_user(user: accounts.User) -> bool:
    """Перепроверяет недавние неоплаченные платежи покупателя — после возврата со страницы оплаты,
    чтобы не зависеть от задержки уведомления. True — какой-то из них продлил тариф."""
    since = time.time() - SYNC_WINDOW_S
    with db.connect() as con:
        ids = [
            r["id"]
            for r in con.execute(
                "SELECT id FROM payments WHERE user_id = ? AND applied = 0 AND created_at >= ?"
                " ORDER BY created_at DESC LIMIT 5",
                (user.id, since),
            )
        ]
    return any([confirm(pid) for pid in ids])


def webhook_payment_id(raw: bytes) -> str | None:
    """id платежа из уведомления. ЮKassa присылает JSON, Точка — JWT (подпись не проверяем: телу всё равно
    не верим, платёж перепроверяется запросом к банку)."""
    text = raw.decode("utf-8", "replace").strip()
    if text.startswith("{"):
        try:
            return str(json.loads(text)["object"]["id"])[:64]
        except (ValueError, KeyError, TypeError):
            return None
    parts = text.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except ValueError:
        return None
    op = payload.get("operationId") if isinstance(payload, dict) else None
    return str(op)[:64] if op else None
