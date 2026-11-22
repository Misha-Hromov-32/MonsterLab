"""Реферальная программа. Все суммы в журнале начислений хранятся в копейках."""

import json
import secrets
import time
from decimal import ROUND_HALF_UP, Decimal

from ..errors import api_error
from . import crypto, db, payout_gateway, site


def attribute(con, buyer: int, code: str) -> None:
    if code:
        con.execute(
            "INSERT OR IGNORE INTO referrals SELECT ?, user_id FROM partners WHERE code=? AND user_id<>?",
            (buyer, code, buyer),
        )


def credit(con, payment, percent: int) -> None:
    amount = int((Decimal(payment["amount"]) * percent).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if amount > 0:
        con.execute(
            "INSERT INTO commissions(payment,partner,kopecks,at) SELECT ?,partner,?,? FROM referrals WHERE buyer=?",
            (payment["id"], amount, time.time(), payment["user_id"]),
        )


def join(user_id: int) -> None:
    with db.connect() as con:
        con.execute(
            "INSERT INTO partners VALUES (?,?,?) ON CONFLICT(user_id) DO NOTHING",
            (user_id, secrets.token_urlsafe(12), time.time()),
        )


def dashboard(user_id: int) -> dict:
    with db.connect() as con:
        row = con.execute("SELECT code FROM partners WHERE user_id=?", (user_id,)).fetchone()
        balance = con.execute(
            "SELECT coalesce(sum(kopecks),0) FROM commissions WHERE partner=? AND payout IS NULL", (user_id,)
        ).fetchone()[0]
        count = con.execute("SELECT count(*) FROM referrals WHERE partner=?", (user_id,)).fetchone()[0]
        history = [
            dict(r)
            for r in con.execute(
                "SELECT id,kopecks,status,reference,at FROM payouts WHERE partner=? ORDER BY id DESC", (user_id,)
            )
        ]
    return {
        "code": row[0] if row else "",
        "percent": site.read()["billing"].get("partner_percent", 15),
        "available": balance,
        "sbp": payout_gateway.enabled(),
        "buyers": count,
        "payouts": history,
    }


def request_payout(user_id: int, details: str, method: str = "manual") -> None:
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        total = con.execute(
            "SELECT sum(kopecks) FROM commissions WHERE partner=? AND payout IS NULL", (user_id,)
        ).fetchone()[0]
        if not total:
            raise api_error(409, "empty_balance", "Нет доступных начислений")
        if method == "sbp" and not 100 <= total <= 50_000_000:
            raise api_error(422, "sbp_limit", "Для этой суммы выберите перевод по реквизитам")
        payout = con.execute(
            "INSERT INTO payouts(partner,kopecks,details,at,method) VALUES (?,?,?,?,?)",
            (user_id, total, crypto.encrypt(details.encode(), "payout"), time.time(), method),
        ).lastrowid
        con.execute("UPDATE commissions SET payout=? WHERE partner=? AND payout IS NULL", (payout, user_id))


def requests() -> list:
    with db.connect() as con:
        rows = con.execute(
            "SELECT id,partner,kopecks,details,at,status,reference,method,provider_id FROM payouts"
            " ORDER BY (status='pending') DESC,id DESC"
        ).fetchall()
    result = []
    for row in rows:
        item = {**dict(row), "details": ""}
        if row["status"] == "pending":
            details = crypto.decrypt(row["details"], "payout").decode()
            if row["method"] == "sbp":
                recipient = json.loads(details)
                details = f"{recipient['bank']} · +{recipient['phone']}"
            item["details"] = details
        result.append(item)
    return result


def settle(payout: int, status: str, reference: str) -> None:
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        if (
            con.execute(
                "UPDATE payouts SET status=?,reference=?,details=X'' WHERE id=? AND status='pending'"
                " AND (method='manual' OR ?='declined')",
                (status, reference, payout, status),
            ).rowcount
            != 1
        ):
            raise api_error(409, "already_settled", "Заявка уже обработана или отсутствует")
        if status == "declined":
            con.execute("UPDATE commissions SET payout=NULL WHERE payout=?", (payout,))
