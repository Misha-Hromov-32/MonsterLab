"""Статистика для админки: воронка, выручка, тарифы, запуски функций и траты на нейросети.

Источники — те же таблицы app.sqlite: users, payments, events (каждый успешный запуск функции)
и visits (открытия сайта по дням). Email покупателей расшифровываются только здесь, для админа.
"""

from __future__ import annotations

import time
from collections import Counter

from . import accounts, crypto, db

DAY = 86400
DAYS = 30  # глубина графиков и «за 30 дней»

# Себестоимость одного запуска на ProxyAPI, ₽ (замеры 30.09.2026): для оценки трат в админке.
# Выбор покупателя — как для 2–3 вариантов; анализ, полка и конкуренты работают на своём сервере.
COST_RUB = {"expert": 7.8, "improve": 13.7, "choice": 4.0}


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def record_visit() -> None:
    """Открытие сайта (главная запрашивает /api/public/site один раз за загрузку)."""
    with db.connect() as con:
        con.execute(
            "INSERT INTO visits (day, count) VALUES (?, 1) ON CONFLICT (day) DO UPDATE SET count = count + 1",
            (_day(time.time()),),
        )


NO_EMAIL = "— без почты (VK ID) —"


def _email(row) -> str:
    try:
        return crypto.decrypt(row["email_enc"], "email").decode() or NO_EMAIL
    except crypto.CryptoError:
        return "— не расшифровать —"


def overview() -> dict:
    now = time.time()
    since = now - DAYS * DAY
    week = now - 7 * DAY
    days = [_day(now - i * DAY) for i in range(DAYS - 1, -1, -1)]
    titles = {p["id"]: p["title"] for p in accounts.plans()}

    with db.connect() as con:
        users = con.execute(
            "SELECT id, email_enc, created_at, verified_at, pro_until, plan_id FROM users ORDER BY id DESC"
        ).fetchall()
        payments = con.execute(
            "SELECT id, user_id, amount, status, plan, created_at FROM payments ORDER BY created_at DESC"
        ).fetchall()
        events = con.execute("SELECT ts, user_id, feature FROM events WHERE ts >= ?", (since,)).fetchall()
        totals = dict(con.execute("SELECT feature, COUNT(*) FROM events GROUP BY feature").fetchall())
        visits = dict(con.execute("SELECT day, count FROM visits WHERE day >= ?", (days[0],)).fetchall())
        runs_by_user = dict(con.execute("SELECT user_id, COUNT(*) FROM events GROUP BY user_id").fetchall())

    paid = [p for p in payments if p["status"] == "succeeded"]
    paid_30 = [p for p in paid if p["created_at"] >= since]
    revenue_30 = sum(float(p["amount"]) for p in paid_30)
    paying = [u for u in users if u["pro_until"] > now]
    by_plan = Counter(u["plan_id"] or "pro" for u in paying)

    runs_30 = Counter(e["feature"] for e in events)
    runs_7 = Counter(e["feature"] for e in events if e["ts"] >= week)
    runs_today = Counter(e["feature"] for e in events if _day(e["ts"]) == days[-1])
    ai_cost_30 = sum(COST_RUB.get(f, 0) * n for f, n in runs_30.items())

    reg_by_day = Counter(_day(u["created_at"]) for u in users if u["created_at"] >= since)
    runs_by_day = Counter(_day(e["ts"]) for e in events)
    pay_by_day = Counter()
    for p in paid_30:
        pay_by_day[_day(p["created_at"])] += float(p["amount"])

    new_30 = [u for u in users if u["created_at"] >= since]
    emails = {u["id"]: _email(u) for u in users[:200]}
    for p in payments[:30]:
        if p["user_id"] not in emails:
            row = next((u for u in users if u["id"] == p["user_id"]), None)
            emails[p["user_id"]] = _email(row) if row else "—"

    return {
        "generated_at": now,
        "users": {
            "total": len(users),
            "verified": sum(1 for u in users if u["verified_at"]),
            "new_7": sum(1 for u in users if u["created_at"] >= week),
            "new_30": len(new_30),
            "paying": len(paying),
            "by_plan": [{"id": k, "title": titles.get(k, k), "count": v} for k, v in by_plan.most_common()],
        },
        "revenue": {
            "total": round(sum(float(p["amount"]) for p in paid), 2),
            "last_30": round(revenue_30, 2),
            "payments_30": len(paid_30),
            "ai_cost_30": round(ai_cost_30),
        },
        "funnel_30": {
            "visits": sum(visits.values()),
            "registered": len(new_30),
            "verified": sum(1 for u in new_30 if u["verified_at"]),
            "active": len({e["user_id"] for e in events}),
            "paid": len({p["user_id"] for p in paid_30}),
        },
        "features": [
            {
                "feature": f,
                "today": runs_today.get(f, 0),
                "week": runs_7.get(f, 0),
                "month": runs_30.get(f, 0),
                "total": totals.get(f, 0),
                "cost_30": round(COST_RUB.get(f, 0) * runs_30.get(f, 0)),
            }
            for f in accounts.FEATURES
        ],
        "daily": [
            {
                "day": d,
                "visits": visits.get(d, 0),
                "registered": reg_by_day.get(d, 0),
                "runs": runs_by_day.get(d, 0),
                "revenue": round(pay_by_day.get(d, 0), 2),
            }
            for d in days
        ],
        "payments": [
            {
                "created_at": p["created_at"],
                "email": emails.get(p["user_id"], "—"),
                "plan": titles.get(p["plan"] or "", p["plan"] or "—"),
                "amount": float(p["amount"]),
                "status": p["status"],
            }
            for p in payments[:30]
        ],
        "latest_users": [
            {
                "email": emails[u["id"]],
                "created_at": u["created_at"],
                "verified": bool(u["verified_at"]),
                "plan": titles.get(u["plan_id"] or "pro", "Платный") if u["pro_until"] > now else "Демо",
                "pro_until": u["pro_until"] if u["pro_until"] > now else None,
                "runs": runs_by_user.get(u["id"], 0),
            }
            for u in users[:200]
        ],
    }


def users() -> dict:
    """Раздел «Пользователи»: все покупатели и всё, что о них известно. Несколько запросов на всю базу —
    без запроса на каждого покупателя."""
    now = time.time()
    titles = {p["id"]: p["title"] for p in accounts.plans()}
    with db.connect() as con:
        rows = con.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
        identities = con.execute("SELECT user_id, provider, created_at FROM user_identities").fetchall()
        usage = con.execute("SELECT user_id, feature, day, count FROM usage").fetchall()
        bonus = con.execute("SELECT user_id, feature, balance FROM user_bonus WHERE balance > 0").fetchall()
        runs = con.execute(
            "SELECT user_id, feature, COUNT(*) AS n, MAX(ts) AS last FROM events GROUP BY user_id, feature"
        ).fetchall()
        payments = con.execute(
            "SELECT user_id, amount, status, plan, created_at FROM payments ORDER BY created_at DESC"
        ).fetchall()
        promos = con.execute(
            "SELECT r.user_id, r.at, c.code FROM promo_redemptions r JOIN promo_codes c ON c.id = r.code_id "
            "ORDER BY r.at DESC"
        ).fetchall()
        covers = dict(con.execute("SELECT user_id, COUNT(*) FROM personal_covers GROUP BY user_id").fetchall())
        ai = dict(con.execute("SELECT user_id, COUNT(*) FROM ai_calls WHERE user_id IS NOT NULL GROUP BY user_id"))

    def group(items, key="user_id") -> dict[int, list]:
        out: dict[int, list] = {}
        for r in items:
            out.setdefault(r[key], []).append(r)
        return out

    by_identity, by_usage, by_bonus = group(identities), group(usage), group(bonus)
    by_runs, by_payment, by_promo = group(runs), group(payments), group(promos)

    items = []
    for row in rows:
        user = accounts.User(
            row["id"], "", row["pro_until"], row["verified_at"] is not None, row["stamp"],
            row["plan_id"] or "", row["period_start"] or 0,
        )  # fmt: skip
        period = "demo" if user.plan == accounts.DEMO else f"p{int(user.period_start)}"
        used = {r["feature"]: r["count"] for r in by_usage.get(user.id, []) if r["day"] == period}
        user_runs = by_runs.get(user.id, [])
        paid = [p for p in by_payment.get(user.id, []) if p["status"] == "succeeded"]
        email = _email(row)
        items.append(
            {
                "id": user.id,
                "email": "" if email == NO_EMAIL else email,
                "providers": sorted({i["provider"] for i in by_identity.get(user.id, [])}),
                "created_at": row["created_at"],
                "verified": user.verified,
                "contested": bool(row["contested"]),
                "legal_version": row["legal_version"] or "",
                "consent_at": row["pd_consent_at"],
                "plan": user.plan,
                "plan_title": titles.get(user.plan, "Платный") if user.plan != accounts.DEMO else "Демо",
                "pro_until": user.pro_until if user.plan != accounts.DEMO else None,
                "period_start": user.period_start if user.plan != accounts.DEMO else None,
                "usage": {f: used.get(f, 0) for f in accounts.FEATURES},
                "limits": accounts.limits(user),
                "bonus": {r["feature"]: r["balance"] for r in by_bonus.get(user.id, [])},
                "runs": {r["feature"]: r["n"] for r in user_runs},
                "runs_total": sum(r["n"] for r in user_runs),
                "last_active": max((r["last"] for r in user_runs), default=None),
                "paid_total": round(sum(float(p["amount"]) for p in paid), 2),
                "payments": [
                    {
                        "created_at": p["created_at"],
                        "amount": float(p["amount"]),
                        "status": p["status"],
                        "plan": titles.get(p["plan"] or "", p["plan"] or "—"),
                    }
                    for p in by_payment.get(user.id, [])[:20]
                ],
                "promos": [{"code": p["code"], "at": p["at"]} for p in by_promo.get(user.id, [])],
                "covers": covers.get(user.id, 0),
                "ai_calls": ai.get(user.id, 0),
            }
        )

    return {
        "generated_at": now,
        "summary": {
            "total": len(items),
            "verified": sum(1 for u in items if u["verified"]),
            "paying": sum(1 for u in items if u["plan"] != accounts.DEMO),
            "vk": sum(1 for u in items if "vk" in u["providers"]),
            "yandex": sum(1 for u in items if "yandex" in u["providers"]),
            "no_email": sum(1 for u in items if not u["email"]),
            "active_30": sum(1 for u in items if u["last_active"] and u["last_active"] >= now - DAYS * DAY),
        },
        "items": items,
    }
