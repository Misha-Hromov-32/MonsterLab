"""Расходы на нейросети (ProxyAPI): журнал запросов и баланс в рублях.

ProxyAPI не отдаёт ни историю списаний, ни цену отдельного запроса — только токены в ответе и текущий
баланс (GET /proxyapi/balance; у ключа должно быть включено разрешение «Запрос баланса»). Поэтому:
- каждый запрос к моделям пишется в ai_calls — кто, какая функция, модель, токены;
- баланс запоминается в ai_balance вскоре после запросов и раз в 15 минут без них. Падение баланса между
  двумя замерами — списание, рост — пополнение. Списание делится между запросами за этот промежуток
  пропорционально оценке их цены (stats.COST_RUB) — так видно, на что ушли деньги.
"""

from __future__ import annotations

import asyncio
import bisect
import itertools
import logging
import sqlite3
import threading
import time
from collections import defaultdict
from contextvars import ContextVar
from urllib.parse import urlparse

import httpx

from . import crypto, db

log = logging.getLogger(__name__)

# Кто сейчас обращается к модели: (id покупателя или None, функция). Ставит очередь задач перед запуском
# (и проверка ключа в админке); asyncio.to_thread и дочерние задачи наследуют значение.
CALLER: ContextVar[tuple[int | None, str]] = ContextVar("ai_caller", default=(None, "other"))

WATCH_EVERY_S = 60
SETTLE_S = 10  # баланс в ProxyAPI обновляется не мгновенно — замеряем, когда запросы стихли
IDLE_SNAPSHOT_S = 15 * 60
CACHE_S = 30
DAY = 86400
HISTORY_DAYS = 90
RECENT_CALLS = 150
RECENT_CHANGES = 200

# доля одного запроса при дележе списания: оценка цены запуска функции, ₽ (как в статистике)
_WEIGHT = {"expert": 7.8 / 4, "choice": 4.0 / 3, "improve": 13.7, "check": 0.05}

_dirty = threading.Event()
_state = {"last_call": 0.0, "last_snapshot": 0.0}
_cache: dict = {}


class BalanceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _tokens(usage: dict, *keys: str) -> int:
    for k in keys:
        v = usage.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    return 0


def record(model: str, usage: object, ok: bool) -> None:
    """Запрос к модели состоялся (ok — ответ без ошибки). Сбой записи журнала работу не ломает."""
    user_id, feature = CALLER.get()
    u = usage if isinstance(usage, dict) else {}
    try:
        with db.connect() as con:
            con.execute(
                "INSERT INTO ai_calls (ts, user_id, feature, model, prompt_tokens, completion_tokens, ok) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    user_id,
                    feature,
                    model[:80],
                    _tokens(u, "prompt_tokens", "input_tokens"),
                    _tokens(u, "completion_tokens", "output_tokens"),
                    int(ok),
                ),
            )
    except sqlite3.Error:
        log.exception("Не удалось записать запрос к модели в журнал")
    _state["last_call"] = time.time()
    _dirty.set()


# ---------------------------------------------------------------- баланс


def _balance_url(base_url: str) -> str:
    host = urlparse(base_url).netloc
    if not (host == "proxyapi.ru" or host.endswith(".proxyapi.ru")):
        raise BalanceError("unsupported", "Баланс показываем только для ProxyAPI")
    return f"https://{host}/proxyapi/balance"


def fetch_balance() -> dict:
    """Текущий баланс: {"balance": ₽, "budget": {...} | None}. BalanceError — ключа нет или нет разрешения."""
    from . import expert  # expert сам пишет сюда журнал запросов

    cfg = expert.current_config()
    if not cfg.api_key:
        raise BalanceError("no_key", "Ключ ProxyAPI не задан — раздел «Нейросети»")
    try:
        r = httpx.get(
            _balance_url(cfg.base_url), headers={"Authorization": f"Bearer {cfg.api_key}"}, timeout=httpx.Timeout(15)
        )
    except httpx.HTTPError as exc:
        raise BalanceError("network", "ProxyAPI не отвечает, попробуйте позже") from exc
    if r.status_code in (401, 403):
        raise BalanceError(
            "forbidden",
            "У ключа не включено разрешение «Запрос баланса»: ProxyAPI → Ключи API → ваш ключ → разрешения.",
        )
    if r.status_code >= 400:
        raise BalanceError("error", f"ProxyAPI ответил ошибкой {r.status_code}")
    try:
        data = r.json()
        balance = float(data["balance"])
    except (ValueError, KeyError, TypeError) as exc:
        raise BalanceError("error", "ProxyAPI вернул непонятный ответ") from exc
    budget = data.get("budget") if isinstance(data.get("budget"), dict) else None
    return {"balance": round(balance, 2), "budget": budget}


def snapshot() -> dict:
    """Спросить баланс и запомнить, если он изменился с прошлого замера."""
    data = fetch_balance()
    now = time.time()
    with db.connect() as con:
        last = con.execute("SELECT balance FROM ai_balance ORDER BY ts DESC LIMIT 1").fetchone()
        if last is None or abs(last["balance"] - data["balance"]) >= 0.005:
            con.execute("INSERT INTO ai_balance (ts, balance) VALUES (?, ?)", (now, data["balance"]))
    _state["last_snapshot"] = now
    _cache.update(at=now, data=data)
    return data


def _due(now: float) -> bool:
    if _dirty.is_set():
        return now - _state["last_call"] >= SETTLE_S
    return now - _state["last_snapshot"] >= IDLE_SNAPSHOT_S


async def watch() -> None:
    """Фоновый замер баланса: вскоре после запросов к моделям и раз в 15 минут без них."""
    while True:
        await asyncio.sleep(WATCH_EVERY_S)
        if not _due(time.time()):
            continue
        _dirty.clear()
        try:
            await asyncio.to_thread(snapshot)
        except BalanceError:
            _state["last_snapshot"] = time.time()  # нет ключа или разрешения — не долбим ProxyAPI каждую минуту
        except Exception:
            log.exception("Замер баланса ProxyAPI не удался")


# ---------------------------------------------------------------- для админки


def _emails(con: sqlite3.Connection, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    out = {}
    for row in con.execute(f"SELECT id, email_enc FROM users WHERE id IN ({marks})", tuple(ids)):
        try:
            out[row["id"]] = crypto.decrypt(row["email_enc"], "email").decode() or "без почты (VK ID)"
        except crypto.CryptoError:
            out[row["id"]] = "—"
    return out


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def overview() -> dict:
    now = time.time()
    since = now - HISTORY_DAYS * DAY

    if _cache and now - _cache["at"] < CACHE_S:
        current: dict = {**_cache["data"], "checked_at": _cache["at"]}
    else:
        try:
            current = {**snapshot(), "checked_at": time.time()}
        except BalanceError as exc:
            current = {"error": {"code": exc.code, "message": exc.message}}

    with db.connect() as con:
        # замер до начала окна — чтобы первое изменение в окне было с чем сравнить
        first = con.execute(
            "SELECT ts, balance FROM ai_balance WHERE ts < ? ORDER BY ts DESC LIMIT 1", (since,)
        ).fetchall()
        points = (
            first + con.execute("SELECT ts, balance FROM ai_balance WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
        )
        calls = con.execute(
            "SELECT rowid, ts, user_id, feature, model, prompt_tokens, completion_tokens, ok FROM ai_calls "
            "WHERE ts >= ? ORDER BY ts",
            (min([since] + [p["ts"] for p in points[:1]]),),
        ).fetchall()
        recent = calls[-RECENT_CALLS:]
        emails = _emails(con, {c["user_id"] for c in recent if c["user_id"] is not None})

    stamps = [c["ts"] for c in calls]
    rub: dict[int, float] = {}  # rowid запроса -> его доля списания, ₽
    changes = []
    for prev, cur in itertools.pairwise(points):
        delta = round(cur["balance"] - prev["balance"], 2)
        between = calls[bisect.bisect_right(stamps, prev["ts"]) : bisect.bisect_right(stamps, cur["ts"])]
        by_feature: dict[str, dict] = defaultdict(lambda: {"calls": 0, "rub": 0.0})
        paid = [c for c in between if c["ok"]]
        weights = {c["rowid"]: _WEIGHT.get(c["feature"], 1.0) for c in paid}
        total = sum(weights.values())
        for c in between:
            by_feature[c["feature"]]["calls"] += 1
        if delta < 0 and total:
            for c in paid:
                share = -delta * weights[c["rowid"]] / total
                rub[c["rowid"]] = share
                by_feature[c["feature"]]["rub"] += share
        changes.append(
            {
                "ts": cur["ts"],
                "from_ts": prev["ts"],
                "delta": delta,
                "balance": cur["balance"],
                "calls": len(between),
                "by_feature": [
                    {"feature": f, "calls": v["calls"], "rub": round(v["rub"], 2)} for f, v in by_feature.items()
                ],
            }
        )

    def spent(after: float) -> float:
        return round(-sum(c["delta"] for c in changes if c["delta"] < 0 and c["ts"] >= after), 2)

    month = now - 30 * DAY
    features: dict[str, dict] = defaultdict(lambda: {"calls": 0, "failed": 0, "tokens": 0, "rub": 0.0})
    models: dict[str, dict] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    daily: dict[str, dict] = {_day(now - i * DAY): {"spent": 0.0, "calls": 0} for i in range(29, -1, -1)}
    for c in calls:
        if c["ts"] < month:
            continue
        tokens = c["prompt_tokens"] + c["completion_tokens"]
        f = features[c["feature"]]
        f["calls"] += 1
        f["failed"] += 0 if c["ok"] else 1
        f["tokens"] += tokens
        f["rub"] += rub.get(c["rowid"], 0.0)
        models[c["model"]]["calls"] += 1
        models[c["model"]]["tokens"] += tokens
        if _day(c["ts"]) in daily:
            daily[_day(c["ts"])]["calls"] += 1
    for ch in changes:
        if ch["delta"] < 0 and _day(ch["ts"]) in daily:
            daily[_day(ch["ts"])]["spent"] += -ch["delta"]

    midnight = time.mktime((*time.localtime(now)[:3], 0, 0, 0, 0, 0, -1))
    return {
        "generated_at": now,
        "current": current,
        "spent": {"today": spent(midnight), "week": spent(now - 7 * DAY), "month": spent(month)},
        "topups_30": round(sum(c["delta"] for c in changes if c["delta"] > 0 and c["ts"] >= month), 2),
        "tracking_since": points[0]["ts"] if points else None,
        "features": sorted(
            ({"feature": k, **v, "rub": round(v["rub"], 2)} for k, v in features.items()), key=lambda x: -x["rub"]
        ),
        "models": sorted(({"model": k, **v} for k, v in models.items()), key=lambda x: -x["calls"]),
        "daily": [{"day": d, "spent": round(v["spent"], 2), "calls": v["calls"]} for d, v in daily.items()],
        "changes": list(reversed(changes))[:RECENT_CHANGES],
        "calls": [
            {
                "ts": c["ts"],
                "email": emails.get(c["user_id"], "—") if c["user_id"] is not None else "",
                "feature": c["feature"],
                "model": c["model"],
                "prompt_tokens": c["prompt_tokens"],
                "completion_tokens": c["completion_tokens"],
                "ok": bool(c["ok"]),
                "rub": round(rub[c["rowid"]], 2) if c["rowid"] in rub else None,
            }
            for c in reversed(recent)
        ],
    }
