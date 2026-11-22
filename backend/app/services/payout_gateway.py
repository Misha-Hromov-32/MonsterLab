"""Выплаты СБП через отдельный шлюз ЮKassa. Запуск перевода подтверждает администратор."""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from decimal import Decimal

import httpx

from ..errors import api_error
from . import crypto, db

log = logging.getLogger(__name__)
BASE = "https://api.yookassa.ru/v3"
RETRY_WINDOW = 20 * 3600


def enabled():
    return bool(os.getenv("YOOKASSA_PAYOUT_AGENT_ID") and os.getenv("YOOKASSA_PAYOUT_SECRET"))


def _call(method, path, **kwargs):
    if not enabled():
        raise api_error(503, "gateway_disabled", "Шлюз выплат ЮKassa не подключён")
    try:
        return httpx.request(
            method,
            BASE + path,
            auth=(os.environ["YOOKASSA_PAYOUT_AGENT_ID"], os.environ["YOOKASSA_PAYOUT_SECRET"]),
            timeout=15,
            **kwargs,
        )
    except httpx.HTTPError as exc:
        raise api_error(503, "gateway_wait", "Связь с ЮKassa прервана. Статус можно проверить повторно.") from exc


def banks():
    response = _call("GET", "/sbp_banks")
    if not response.is_success:
        raise api_error(503, "gateway_failed", "Не удалось получить список банков СБП")
    return [{"bank_id": item["bank_id"], "name": item["name"]} for item in response.json()["items"]]


def dispatch(payout: int, provider_id: str = ""):
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM payouts WHERE id=? AND method='sbp'", (payout,)).fetchone()
        if row is None or row["status"] not in ("pending", "sending"):
            raise api_error(409, "closed", "Эта заявка уже закрыта или предназначена для ручного перевода")
        if not enabled():
            raise api_error(503, "gateway_disabled", "Шлюз выплат ЮKassa не подключён")
        if row["status"] == "pending":
            if provider_id:
                raise api_error(422, "bad_id", "У новой заявки ещё нет номера операции")
            con.execute(
                "UPDATE payouts SET status='sending',attempt=?,sent_at=? WHERE id=?",
                (uuid.uuid4().hex, time.time(), payout),
            )
            row = con.execute("SELECT * FROM payouts WHERE id=?", (payout,)).fetchone()
        con.execute("UPDATE payouts SET poll_at=? WHERE id=?", (time.time() + 90, payout))
    saved_id = row["provider_id"] or provider_id
    if saved_id:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", saved_id):
            raise api_error(422, "bad_id", "Проверьте идентификатор выплаты ЮKassa")
        response = _call("GET", "/payouts/" + saved_id)
    else:
        if time.time() - row["sent_at"] >= RETRY_WINDOW:
            raise api_error(
                409, "reconcile", "Укажите ID операции из кабинета ЮKassa для сверки. Средства зарезервированы."
            )
        dest = json.loads(crypto.decrypt(row["details"], "payout"))
        response = _call(
            "POST",
            "/payouts",
            headers={"Idempotence-Key": row["attempt"]},
            json={
                "amount": {"value": f"{row['kopecks'] / 100:.2f}", "currency": "RUB"},
                "payout_destination_data": {"type": "sbp", "phone": dest["phone"], "bank_id": dest["bank_id"]},
                "description": f"Партнёрское вознаграждение MonStoreLab, заявка {payout}",
                "metadata": {"request": row["attempt"]},
            },
        )
    if not response.is_success:
        if not saved_id and response.status_code == 400 and response.json().get("type") == "error":
            with db.connect() as con:
                changed = con.execute(
                    "UPDATE payouts SET status='declined',details=X'',reference=? WHERE id=?"
                    " AND status='sending' AND provider_id IS NULL",
                    ("ЮKassa отклонила параметры выплаты", payout),
                ).rowcount
                if changed:
                    con.execute("UPDATE commissions SET payout=NULL WHERE payout=?", (payout,))
            return
        raise api_error(503, "gateway_wait", "ЮKassa не подтвердила операцию. Проверьте статус в кабинете выплат.")
    op = response.json()
    if (
        op.get("metadata", {}).get("request") != row["attempt"]
        or op["amount"]["currency"] != "RUB"
        or Decimal(op["amount"]["value"]) * 100 != row["kopecks"]
        or (saved_id and op["id"] != saved_id)
        or op.get("status") not in ("pending", "succeeded", "canceled")
    ):
        raise api_error(409, "mismatch", "Операция в ЮKassa не соответствует заявке")
    status = {"pending": "sending", "succeeded": "paid", "canceled": "declined"}[op["status"]]
    if op.get("test") is True:
        status = "declined"
    reference = "Тестовый шлюз. Средства не перечислены." if op.get("test") else op["id"]
    with db.connect() as con:
        changed = con.execute(
            "UPDATE payouts SET provider_id=?,status=?,reference=?,details=CASE WHEN ? THEN details ELSE X'' END"
            " WHERE id=? AND status='sending' AND (provider_id IS NULL OR provider_id=?)",
            (op["id"], status, reference, status == "sending", payout, op["id"]),
        ).rowcount
        if changed and status == "declined":
            con.execute("UPDATE commissions SET payout=NULL WHERE payout=?", (payout,))


def reconcile_one():
    with db.connect() as con:
        row = con.execute(
            "SELECT id FROM payouts WHERE status='sending' AND poll_at<=? AND (provider_id IS NOT NULL OR sent_at>?)"
            " ORDER BY poll_at LIMIT 1",
            (time.time(), time.time() - RETRY_WINDOW),
        ).fetchone()
    if row:
        dispatch(row["id"])


async def watch():
    while enabled():
        await asyncio.sleep(30)
        try:
            await asyncio.to_thread(reconcile_one)
        except Exception:
            log.exception("Не удалось сверить выплату")
