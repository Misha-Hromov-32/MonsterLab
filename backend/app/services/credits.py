"""Единый баланс импульсов. Резерв и списание привязаны к тому периоду, в котором началась работа."""

from __future__ import annotations

import time
from uuid import uuid4

from .. import config
from . import db, site

COST = {"analyze": 3, "shelf": 5, "expert": 45, "choice": 40, "improve": 85, "competitors": 8, "rules": 2, "wb": 20}
PACKS = {"start": 1000, "pro": 3200, "agency": 7000}
DEMO = 30


def plan_grant(plan):
    explicit = plan.get("credits")
    if explicit is not None:
        return int(explicit)
    return PACKS.get(plan["id"], max(50, round(plan["price_rub"] / 50) * 50))


def weighted(counts):
    return counts.get("credits", 0) + sum(max(0, counts.get(k, 0)) * price for k, price in COST.items())


def allowance(user):
    import json

    from . import accounts

    billing = site.read()["billing"]
    if user.plan == accounts.DEMO:
        return billing.get("demo_credits", DEMO)
    # Действующие на момент перехода подписки сохраняют эквивалент прежних квот.
    previous = json.loads(user.quota_json) if user.quota_json else accounts.limits(user)
    return previous["credits"] if "credits" in previous else weighted(previous)


def snapshot(con, user):
    from . import accounts

    period = accounts.usage_period(user)
    grant = allowance(user)
    welcome = con.execute("SELECT signup,email FROM welcome_rewards WHERE buyer=?", (user.id,)).fetchone()
    earned = 0
    if welcome:
        earned = welcome["signup"] + (welcome["email"] if user.email and user.verified else 0)
        if user.plan == accounts.DEMO:
            grant = 0
    old = con.execute("SELECT feature,count FROM usage WHERE user_id=? AND day=?", (user.id, period))
    # Снимок прежнего расхода создаётся один раз до первого нового списания.
    con.execute("INSERT OR IGNORE INTO credit_opening VALUES(?,?,?)", (user.id, period, weighted(dict(old))))
    opening = con.execute("SELECT used FROM credit_opening WHERE buyer=? AND period=?", (user.id, period)).fetchone()[0]
    rows = con.execute("SELECT feature,balance FROM user_bonus WHERE user_id=?", (user.id,))
    social = con.execute("SELECT amount FROM social_claims WHERE buyer=? AND status='approved'", (user.id,)).fetchone()
    bonus = earned + weighted(dict(rows)) + (social["amount"] if social else 0)
    spent, extra = con.execute(
        "SELECT coalesce(sum(CASE WHEN period=? THEN base ELSE 0 END),0),coalesce(sum(extra),0) "
        "FROM credit_charges WHERE buyer=? AND (settled=1 OR expiry IS NULL OR expiry>?)",
        (period, user.id, time.time()),
    ).fetchone()
    left = max(0, grant - opening - spent)
    remaining_bonus = max(0, bonus - extra)
    return {"grant": grant, "remaining": left + remaining_bonus, "period_remaining": left, "bonus": remaining_bonus}


def wallet(user):
    with db.connect() as con:
        return snapshot(con, user)


def ensure(user, amount):
    if wallet(user)["remaining"] < amount:
        from .accounts import LimitReached

        raise LimitReached("credits", amount, user.plan)


def reserve_in(con, user, feature, amount, reference, persistent=False):
    from . import accounts

    balance = snapshot(con, user)
    if balance["remaining"] < amount:
        raise accounts.LimitReached("credits", amount, user.plan)
    base = min(balance["period_remaining"], amount)
    expiry = None if persistent else time.time() + config.QUEUE_JOB_TIMEOUT_S + 120
    con.execute(
        "INSERT INTO credit_charges(id,buyer,period,action,base,extra,expiry) VALUES(?,?,?,?,?,?,?)",
        (reference, user.id, accounts.usage_period(user), feature, base, amount - base, expiry),
    )


def reserve(user, feature, amount=None):
    from . import accounts

    reference = uuid4().hex
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        actual = accounts._row(con.execute("SELECT * FROM users WHERE id=?", (user.id,)).fetchone())
        if not actual:
            raise accounts.AccountError("Аккаунт недоступен")
        reserve_in(con, actual, feature, COST[feature] if amount is None else amount, reference)
    return reference


def finish_in(con, reference, success):
    if not success:
        con.execute("DELETE FROM credit_charges WHERE id=? AND settled=0", (reference,))
        return
    row = con.execute(
        "SELECT buyer,period,action FROM credit_charges WHERE id=? AND settled=0", (reference,)
    ).fetchone()
    if row is None:
        return
    con.execute("UPDATE credit_charges SET settled=1,expiry=NULL WHERE id=?", (reference,))
    con.execute(
        "INSERT INTO usage(user_id,day,feature,count) VALUES(?,?,?,1) "
        "ON CONFLICT(user_id,feature,day) DO UPDATE SET count=count+1",
        tuple(row),
    )
    con.execute("INSERT INTO events(ts,user_id,feature) VALUES(?,?,?)", (time.time(), row["buyer"], row["action"]))


def finish(reference, success):
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        finish_in(con, reference, success)
