"""Промокоды: админ создаёт, покупатель активирует в аккаунте и получает бонусы.

Промокод может прибавить или убавить запуски любых функций (бонусный баланс user_bonus, сверх квоты тарифа)
и выдать тариф на N дней. Ограничения: срок действия, общее число активаций, один покупатель — один раз.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time

from . import accounts, db

CODE_RE = re.compile(r"^[A-Z0-9А-ЯЁ_-]{3,32}$")
MAX_DELTA = 10_000


class PromoError(ValueError):
    """Понятная причина: такого кода нет, истёк, закончился, уже активирован."""


def normalize(code: str) -> str:
    return code.strip().upper()


def _out(row: sqlite3.Row, uses: int) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "note": row["note"],
        "bonus": json.loads(row["bonus"] or "{}"),
        "plan_id": row["plan_id"] or None,
        "plan_days": row["plan_days"],
        "max_uses": row["max_uses"],
        "expires_at": row["expires_at"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "uses": uses,
    }


def listing() -> list[dict]:
    with db.connect() as con:
        rows = con.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM promo_redemptions r WHERE r.code_id = p.id) AS uses "
            "FROM promo_codes p ORDER BY p.created_at DESC, p.id DESC"
        ).fetchall()
    return [_out(r, r["uses"]) for r in rows]


def _clean(data: dict) -> dict:
    """Проверка и нормализация полей промокода (границы дублируют проверку в api/admin.py)."""
    code = normalize(data.get("code", ""))
    if not CODE_RE.match(code):
        raise PromoError("Код — 3–32 символа: буквы, цифры, - и _")
    bonus = {}
    for feature, delta in (data.get("bonus") or {}).items():
        if feature not in accounts.FEATURES:
            raise PromoError(f"Неизвестная функция: {feature}")
        delta = int(delta)
        if abs(delta) > MAX_DELTA:
            raise PromoError(f"Не больше {MAX_DELTA} запусков за раз")
        if delta:
            bonus[feature] = delta
    plan_id = data.get("plan_id") or None
    plan_days = int(data.get("plan_days") or 0)
    if plan_id and accounts.find_plan(plan_id) is None:
        raise PromoError("Такого тарифа нет")
    if bool(plan_id) != (plan_days > 0):
        raise PromoError("Для тарифа укажите и тариф, и число дней")
    if not bonus and not plan_id:
        raise PromoError("Промокод ничего не даёт — добавьте запуски или тариф")
    return {
        "code": code,
        "note": (data.get("note") or "").strip()[:200],
        "bonus": json.dumps(bonus, ensure_ascii=False),
        "plan_id": plan_id,
        "plan_days": plan_days,
        "max_uses": max(0, int(data.get("max_uses") or 0)),
        "expires_at": data.get("expires_at") or None,
        "active": int(bool(data.get("active", True))),
    }


def save(data: dict, promo_id: int | None = None) -> None:
    v = _clean(data)
    try:
        with db.connect() as con:
            if promo_id is None:
                con.execute(
                    "INSERT INTO promo_codes (code, note, bonus, plan_id, plan_days, max_uses, expires_at, active,"
                    " created_at) VALUES (:code, :note, :bonus, :plan_id, :plan_days, :max_uses, :expires_at,"
                    " :active, :now)",
                    {**v, "now": time.time()},
                )
            elif (
                con.execute(
                    "UPDATE promo_codes SET code = :code, note = :note, bonus = :bonus, plan_id = :plan_id,"
                    " plan_days = :plan_days, max_uses = :max_uses, expires_at = :expires_at, active = :active"
                    " WHERE id = :id",
                    {**v, "id": promo_id},
                ).rowcount
                != 1
            ):
                raise PromoError("Промокод не найден")
    except sqlite3.IntegrityError as exc:
        raise PromoError("Такой код уже есть") from exc


def delete(promo_id: int) -> None:
    with db.connect() as con:
        con.execute("DELETE FROM promo_redemptions WHERE code_id = ?", (promo_id,))
        if con.execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,)).rowcount != 1:
            raise PromoError("Промокод не найден")


def redeem(user: accounts.User, code: str) -> dict:
    """Активация промокода покупателем. Возвращает, что начислено: {"bonus": {...}, "plan_id", "plan_days"}."""
    code = normalize(code)
    now = time.time()
    with db.connect() as con:
        row = con.execute("SELECT * FROM promo_codes WHERE code = ?", (code,)).fetchone()
        if row is None or not row["active"]:
            raise PromoError("Промокод не найден")
        if row["expires_at"] and row["expires_at"] < now:
            raise PromoError("Срок действия промокода истёк")
        if row["max_uses"]:
            uses = con.execute("SELECT COUNT(*) FROM promo_redemptions WHERE code_id = ?", (row["id"],)).fetchone()[0]
            if uses >= row["max_uses"]:
                raise PromoError("Промокод закончился")
        try:
            con.execute(
                "INSERT INTO promo_redemptions (code_id, user_id, at) VALUES (?, ?, ?)", (row["id"], user.id, now)
            )
        except sqlite3.IntegrityError as exc:
            raise PromoError("Вы уже активировали этот промокод") from exc
        bonus = json.loads(row["bonus"] or "{}")
        for feature, delta in bonus.items():
            # убавить можно только до нуля: отрицательного баланса не бывает
            con.execute(
                "INSERT OR IGNORE INTO user_bonus (user_id, feature, balance) VALUES (?, ?, 0)", (user.id, feature)
            )
            con.execute(
                "UPDATE user_bonus SET balance = MAX(0, balance + ?) WHERE user_id = ? AND feature = ?",
                (delta, user.id, feature),
            )
    plan_id, days = row["plan_id"], row["plan_days"]
    if plan_id and days:
        # действующий платный тариф только продлеваем — не меняем его на тариф из промокода
        if user.plan != accounts.DEMO:
            accounts.extend(user.id, days)
        else:
            accounts.activate(user.id, plan_id, days)
    return {"bonus": bonus, "plan_id": plan_id or None, "plan_days": days if plan_id else 0}
