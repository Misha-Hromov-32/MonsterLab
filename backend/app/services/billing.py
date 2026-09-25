"""Оплата подписки через ЮKassa (https://yookassa.ru/developers/api).

1. checkout() создаёт платёж и возвращает ссылку на страницу оплаты ЮKassa.
2. Покупатель платит, ЮKassa возвращает его на сайт и присылает уведомление на /api/billing/webhook.
3. confirm() НЕ верит телу уведомления: заново запрашивает платёж у ЮKassa по id и, если он
   действительно оплачен, один раз продлевает подписку (payments.applied защищает от повторов).

Без YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY оплата выключена — сервис работает на бесплатном тарифе.
"""

from __future__ import annotations

import logging
import time
import uuid

import httpx

from .. import config
from . import accounts, db, site

log = logging.getLogger(__name__)

API = "https://api.yookassa.ru/v3"


class BillingError(RuntimeError):
    """Понятная пользователю причина: оплата не подключена, ЮKassa недоступна."""


def enabled() -> bool:
    return bool(config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET_KEY)


def plan() -> dict:
    billing = site.read()["billing"]
    return {"price_rub": billing["price_rub"], "period_days": billing["period_days"], "limits": billing["limits"]}


def _client() -> httpx.Client:
    if not enabled():
        raise BillingError("Оплата пока не подключена")
    auth = (config.YOOKASSA_SHOP_ID, config.YOOKASSA_SECRET_KEY)
    return httpx.Client(base_url=API, auth=auth, timeout=httpx.Timeout(20, connect=10))


def checkout(user: accounts.User) -> str:
    """Создаёт платёж на месяц подписки и возвращает адрес страницы оплаты."""
    info = plan()
    amount = {"value": f"{info['price_rub']:.2f}", "currency": "RUB"}
    description = f"Monster Lab: подписка на {info['period_days']} дней"
    body: dict = {
        "amount": amount,
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": f"{config.PUBLIC_URL}/?payment=return"},
        "description": description,
        "metadata": {"user_id": str(user.id), "days": str(info["period_days"])},
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
    try:
        with _client() as client:
            r = client.post("/payments", json=body, headers={"Idempotence-Key": uuid.uuid4().hex})
    except httpx.HTTPError as exc:
        raise BillingError("ЮKassa сейчас недоступна, попробуйте через минуту") from exc
    if r.status_code >= 400:
        log.error("ЮKassa отказала в создании платежа: %s %s", r.status_code, r.text[:300])
        raise BillingError("Не удалось создать платёж, попробуйте позже")
    payment = r.json()
    with db.connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO payments (id, user_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (payment["id"], user.id, amount["value"], payment["status"], time.time()),
        )
    return payment["confirmation"]["confirmation_url"]


def confirm(payment_id: str) -> bool:
    """Проверяет платёж в ЮKassa и продлевает подписку, если он оплачен. True — подписка продлена сейчас."""
    try:
        with _client() as client:
            r = client.get(f"/payments/{payment_id}")
    except httpx.HTTPError as exc:
        raise BillingError("ЮKassa недоступна") from exc
    if r.status_code == 404:
        return False
    r.raise_for_status()
    payment = r.json()
    user_id = int(payment.get("metadata", {}).get("user_id", 0) or 0)
    days = int(payment.get("metadata", {}).get("days", 0) or plan()["period_days"])
    with db.connect() as con:
        row = con.execute("SELECT applied FROM payments WHERE id = ?", (payment_id,)).fetchone()
        if row is None:  # платёж создан не через нас — не наш
            log.warning("Уведомление о неизвестном платеже %s", payment_id)
            return False
        con.execute("UPDATE payments SET status = ? WHERE id = ?", (payment["status"], payment_id))
        if payment["status"] != "succeeded" or not payment.get("paid") or row["applied"] or not user_id:
            return False
        con.execute("UPDATE payments SET applied = 1 WHERE id = ?", (payment_id,))
    accounts.extend_pro(user_id, days)
    log.info("Подписка продлена: пользователь %s, платёж %s", user_id, payment_id)
    return True
