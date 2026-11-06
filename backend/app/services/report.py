"""Отчёт владельцам в ВК: пользователи, оплаты, запуски, нейросети и здоровье сервиса.

Запускается по расписанию на сервере (deploy/monstorelab-report.timer — дважды в день):
    docker exec monster-lab-backend-1 python -m app.services.report            # собрать и отправить
    docker exec monster-lab-backend-1 python -m app.services.report --dry-run  # только показать текст

Почта покупателей в отчёте замаскирована (xd***@mail.ru): полный список — в админке.
Наверху — «Внимание»: то, что требует действий (ошибки нейросетей, модель пропала из каталога,
кончается баланс, сайт не отвечает, заканчивается тариф у покупателя).
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx

from .. import config
from . import accounts, aicost, billing, db, expert, site, stats

MSK = timezone(timedelta(hours=3))  # в Москве нет перехода на летнее время
DAY = 86400
LOW_BALANCE_RUB = 300  # ниже — предупреждаем: «Выбор покупателя» и разбор скоро встанут
LOW_DISK_GB = 5
EXPIRING_DAYS = 5
BACKUP_STALE_H = 26  # бэкап раз в сутки (deploy/monstorelab-backup.timer) — старше суток с запасом = не сделался
VK_API = "https://api.vk.com/method/messages.send"
VK_LIMIT = 4000  # ВК режет сообщения длиннее 4096 символов

FEATURE_SHORT = {
    "analyze": "Проверка",
    "shelf": "Полка",
    "expert": "Разбор",
    "choice": "Выбор покупателя",
    "improve": "Генерация",
    "competitors": "Конкуренты",
}


def mask(email: str) -> str:
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"


def _rub(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " ₽"


def _dt(ts: float, fmt: str = "%d.%m %H:%M") -> str:
    return datetime.fromtimestamp(ts, MSK).strftime(fmt)


def _backup_line(now: float, alerts: list[str]) -> str:
    """Итог ночного бэкапа: его пишет deploy/backup.sh в backup-status.json тома data."""
    try:
        st = json.loads((config.DATA_DIR / "backup-status.json").read_text("utf-8"))
    except FileNotFoundError:
        alerts.append("Автобэкап ещё ни разу не выполнялся")
        return "бэкапа нет"
    except ValueError:
        alerts.append("Файл статуса бэкапа повреждён")
        return "бэкап: статус не прочитать"
    age_h = (now - float(st.get("at", 0))) / 3600
    if not st.get("ok"):
        alerts.append(f"Бэкап {_dt(st.get('at', 0))} не удался: {st.get('error') or 'причина в journalctl'}")
        return "бэкап НЕ удался"
    if age_h > BACKUP_STALE_H:
        alerts.append(f"Последний бэкап был {age_h:.0f} ч назад — ночной не сделался")
    remote = {"ok": "копия на втором сервере", "failed": "копия на второй сервер НЕ ушла", "off": "без второго сервера"}
    if st.get("remote") == "failed":
        alerts.append("Бэкап сделан, но копия на второй сервер не ушла")
    return (
        f"бэкап {_dt(st['at'])} ({st.get('users', '?')} польз., {st.get('size_mb', '?')} МБ, "
        f"{remote.get(st.get('remote'), st.get('remote', ''))})"
    )


def _live_checks(alerts: list[str]) -> list[str]:
    """Сайт снаружи, баланс и каталог моделей ProxyAPI — каждая проверка сама по себе, сбой одной не мешает другим."""
    lines = []
    try:
        r = httpx.get(f"{config.PUBLIC_URL.rstrip('/')}/api/health", timeout=15)
        ok = r.status_code == 200 and r.json().get("ok")
        lines.append("сайт отвечает" if ok else f"сайт: ответ {r.status_code}")
        if not ok:
            alerts.append(f"Сайт отвечает с ошибкой ({r.status_code})")
    except (httpx.HTTPError, ValueError) as exc:
        lines.append("сайт НЕ отвечает")
        alerts.append(f"Сайт не отвечает: {type(exc).__name__}")

    try:
        balance = aicost.fetch_balance()["balance"]
        lines.append(f"баланс ProxyAPI {_rub(balance)}")
        if balance < LOW_BALANCE_RUB:
            alerts.append(f"Баланс ProxyAPI {_rub(balance)} — пора пополнить")
    except aicost.BalanceError as exc:
        lines.append("баланс ProxyAPI не узнать")
        alerts.append(f"Баланс ProxyAPI: {exc.message}")

    cfg = expert.current_config()
    wanted = {config.VISUAL_MODEL: "разбор", config.IMAGE_MODEL: "генерация"}
    for m in cfg.models:
        wanted.setdefault(m, "выбор покупателя")
    if cfg.api_key:
        try:
            r = httpx.get(
                f"{cfg.base_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {cfg.api_key}"}, timeout=30
            )
            r.raise_for_status()
            catalog = {m.get("id") for m in r.json().get("data", [])}
            missing = [f"{m} ({what})" for m, what in wanted.items() if m not in catalog]
            lines.append("модели в каталоге ProxyAPI" if not missing else "часть моделей пропала из ProxyAPI")
            for m in missing:
                alerts.append(f"Модели нет в каталоге ProxyAPI: {m}")
        except (httpx.HTTPError, ValueError) as exc:
            lines.append("каталог ProxyAPI не проверить")
            alerts.append(f"Каталог моделей ProxyAPI недоступен: {type(exc).__name__}")
    return lines


def build(hours: float = 12, live: bool = True) -> str:
    now = time.time()
    since, week, month = now - hours * 3600, now - 7 * DAY, now - 30 * DAY
    titles = {p["id"]: p["title"] for p in accounts.plans()}
    with db.connect() as con:
        users = con.execute(
            "SELECT id, email_enc, created_at, verified_at, pro_until, plan_id FROM users ORDER BY id"
        ).fetchall()
        providers: dict[int, set[str]] = {}
        for r in con.execute("SELECT user_id, provider FROM user_identities"):
            providers.setdefault(r["user_id"], set()).add(r["provider"])
        payments = con.execute("SELECT user_id, amount, status, plan, created_at FROM payments").fetchall()
        events = con.execute("SELECT ts, user_id, feature FROM events WHERE ts >= ?", (week,)).fetchall()
        visits = dict(
            con.execute(
                "SELECT day, count FROM visits WHERE day >= ?", (time.strftime("%Y-%m-%d", time.localtime(week)),)
            ).fetchall()
        )
        calls = con.execute("SELECT model, ok, user_id, feature FROM ai_calls WHERE ts >= ?", (since,)).fetchall()
        before = con.execute(
            "SELECT balance FROM ai_balance WHERE ts <= ? ORDER BY ts DESC LIMIT 1", (since,)
        ).fetchone()
        latest = con.execute("SELECT balance FROM ai_balance ORDER BY ts DESC LIMIT 1").fetchone()

    email = {u["id"]: stats._email(u) for u in users}
    who = lambda uid: mask(email.get(uid, "—"))  # noqa: E731
    alerts: list[str] = []
    period = f"за {hours:g} ч" if hours < 48 else f"за {hours / 24:g} дн"
    out = [f"📊 MonStoreLab · {_dt(now)} МСК · {period}"]

    # ---------------------------------------------------------- пользователи
    new = [u for u in users if u["created_at"] >= since]
    new_week = sum(1 for u in users if u["created_at"] >= week)
    out += [
        "",
        f"👥 Пользователи: {len(users)} (новых {period}: {len(new)}, за 7 дн: {new_week})",
        f"почта подтверждена у {sum(1 for u in users if u['verified_at'])} · "
        f"через VK/Яндекс — {sum(1 for u in users if providers.get(u['id']))}",
    ]
    for u in new:
        how = ", ".join(sorted(providers.get(u["id"], set()))) or "почта"
        state = "подтвердил" if u["verified_at"] or providers.get(u["id"]) else "не подтвердил почту"
        out.append(f"  + {who(u['id'])} · {how} · {state} · {_dt(u['created_at'])}")

    # ---------------------------------------------------------- тарифы и деньги
    paying = [u for u in users if u["pro_until"] > now]
    out += ["", f"💳 Платные тарифы: {len(paying)}"]
    for u in sorted(paying, key=lambda u: u["pro_until"]):
        left = (u["pro_until"] - now) / DAY
        until = _dt(u["pro_until"], "%d.%m")
        out.append(f"  {titles.get(u['plan_id'] or '', 'Платный')} до {until} · {who(u['id'])}")
        if left <= EXPIRING_DAYS:
            alerts.append(f"У {who(u['id'])} тариф заканчивается {until} — напомнить о продлении")

    paid = [p for p in payments if p["status"] in billing.PAID_STATUSES]
    paid_new = [p for p in paid if p["created_at"] >= since]
    out.append(
        f"💰 Выручка: {period} {_rub(sum(float(p['amount']) for p in paid_new))} · "
        f"30 дн {_rub(sum(float(p['amount']) for p in paid if p['created_at'] >= month))} · "
        f"всего {_rub(sum(float(p['amount']) for p in paid))}"
    )
    for p in paid_new:
        out.append(f"  + {_rub(float(p['amount']))} · {titles.get(p['plan'] or '', p['plan'])} · {who(p['user_id'])}")
    started = [p for p in payments if p["created_at"] >= since and p["status"] not in billing.PAID_STATUSES]
    if started:
        out.append(f"  начали оплату и не завершили: {len(started)}")

    # ---------------------------------------------------------- запуски и посещаемость
    runs_now = Counter(e["feature"] for e in events if e["ts"] >= since)
    runs_week = Counter(e["feature"] for e in events)
    out += ["", f"▶️ Запуски {period} / за 7 дн:"]
    out += [f"  {FEATURE_SHORT[f]}: {runs_now.get(f, 0)} / {runs_week.get(f, 0)}" for f in accounts.FEATURES]
    active_now = Counter(e["user_id"] for e in events if e["ts"] >= since)
    out.append(f"активных {period}: {len(active_now)} · за 7 дн: {len({e['user_id'] for e in events})}")
    if active_now:
        out.append("  самые активные: " + ", ".join(f"{who(u)} ({n})" for u, n in active_now.most_common(3)))
    today = time.strftime("%Y-%m-%d")
    out.append(f"👀 Визиты на сайт: сегодня {visits.get(today, 0)} · за 7 дн {sum(visits.values())}")

    # ---------------------------------------------------------- нейросети
    failed = [c for c in calls if not c["ok"]]
    out += ["", f"🤖 Нейросети {period}: запросов {len(calls)}, ошибок {len(failed)}"]
    if before and latest:
        out.append(f"  потрачено ≈ {_rub(max(0.0, before['balance'] - latest['balance']))}")
    if failed:
        by_model = Counter(c["model"] for c in failed)
        users_hit = {c["user_id"] for c in failed if c["user_id"]}
        detail = ", ".join(f"{m} — {n}" for m, n in by_model.most_common())
        alerts.append(f"Ошибки нейросетей {period}: {detail} (пострадало пользователей: {len(users_hit)})")

    # ---------------------------------------------------------- сервер
    free_gb = shutil.disk_usage(config.DATA_DIR).free / 1024**3
    health = [
        _backup_line(now, alerts),
        f"свободно на диске {free_gb:.0f} ГБ",
        f"примеров на главной {len(site.published_examples())}",
    ]
    if free_gb < LOW_DISK_GB:
        alerts.append(f"На диске сервера осталось {free_gb:.1f} ГБ")
    if live:
        health = _live_checks(alerts) + health
    out += ["", "🩺 Сервис: " + " · ".join(health)]

    head = ["⚠️ Внимание:"] + [f"• {a}" for a in alerts] if alerts else ["✅ Всё в порядке"]
    return "\n".join([out[0], "", *head, *out[1:]])


def _chunks(text: str) -> list[str]:
    parts, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > VK_LIMIT:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    return [*parts, cur] if cur else parts


def send(text: str) -> list[str]:
    """Отправляет каждому получателю; возвращает ошибки (пусто — всё ушло)."""
    if not config.VK_REPORT_TOKEN or not config.VK_REPORT_PEERS:
        return ["не заданы VK_REPORT_TOKEN и VK_REPORT_PEERS"]
    errors = []
    with httpx.Client(timeout=20) as client:
        for peer in config.VK_REPORT_PEERS:
            for part in _chunks(text):
                params = {
                    "peer_id": peer,
                    "message": part,
                    "random_id": random.randint(1, 2**31 - 1),
                    "dont_parse_links": 1,
                    "access_token": config.VK_REPORT_TOKEN,
                    "v": "5.199",
                }
                try:
                    body = client.post(VK_API, data=params).json()
                except (httpx.HTTPError, ValueError) as exc:
                    errors.append(f"{peer}: {type(exc).__name__}")
                    break
                if "error" in body:
                    errors.append(f"{peer}: {body['error'].get('error_msg', body['error'])}")
                    break
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Отчёт MonStoreLab в ВК")
    ap.add_argument("--hours", type=float, default=12, help="за какой период, часов (по умолчанию 12)")
    ap.add_argument("--dry-run", action="store_true", help="только показать текст, не отправлять")
    args = ap.parse_args()
    text = build(args.hours)
    print(text)
    if args.dry_run:
        return 0
    errors = send(text)
    for e in errors:
        print(f"не отправлено: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
