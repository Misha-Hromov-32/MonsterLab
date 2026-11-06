"""Отчёт владельцам в ВК и учёт оплат Точки в статистике админки."""

from __future__ import annotations

import json
import re
import time
import urllib.parse

import httpx
from fastapi.testclient import TestClient

from app import config
from app.services import accounts, db, report, stats

from .conftest import verified_token


def _paid_buyer(client: TestClient, email: str) -> int:
    verified_token(client, email)
    uid = accounts.find(email).id
    accounts.activate(uid, "start", 30)
    with db.connect() as con:
        con.execute(
            "INSERT INTO payments (id, user_id, amount, status, applied, created_at, plan) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (f"pay-{uid}", uid, "990.00", "APPROVED", time.time(), "start"),
        )
    return uid


def test_mask_hides_most_of_email() -> None:
    assert report.mask("xdashax11@mail.ru") == "xd***@mail.ru"
    assert report.mask(stats.NO_EMAIL) == stats.NO_EMAIL


def test_tochka_payment_counts_as_revenue(client: TestClient) -> None:
    uid = _paid_buyer(client, "tochka-buyer@example.com")
    assert stats.overview()["revenue"]["total"] >= 990  # статус Точки APPROVED — тоже оплата
    row = next(u for u in stats.users()["items"] if u["id"] == uid)
    assert row["paid_total"] == 990


def test_report_lists_users_money_and_alerts(client: TestClient) -> None:
    uid = _paid_buyer(client, "report-buyer@example.com")
    with db.connect() as con:
        con.execute("INSERT INTO events (ts, user_id, feature) VALUES (?, ?, 'analyze')", (time.time(), uid))
        con.execute(
            "INSERT INTO ai_calls (ts, user_id, feature, model, prompt_tokens, completion_tokens, ok) "
            "VALUES (?, ?, 'choice', 'google/gemini-x', 0, 0, 0)",
            (time.time(), uid),
        )

    text = report.build(hours=12, live=False)
    assert "⚠️ Внимание" in text and "google/gemini-x" in text  # ошибка нейросети — наверху
    assert "re***@example.com" in text and "report-buyer@" not in text  # почта замаскирована
    assert "Выручка" in text and "990 ₽" in text
    assert re.search(r"Проверка: [1-9]", text)  # другие тесты тоже запускают проверки — их больше одной


def test_send_goes_to_every_peer(monkeypatch) -> None:
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(dict(urllib.parse.parse_qsl(request.content.decode())))
        return httpx.Response(200, json={"response": 1})

    monkeypatch.setattr(config, "VK_REPORT_TOKEN", "token")
    monkeypatch.setattr(config, "VK_REPORT_PEERS", ["1", "2"])
    real = httpx.Client
    monkeypatch.setattr(report.httpx, "Client", lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))

    assert report.send("строка\n" * 900) == []  # длинный текст делится на части по лимиту ВК
    assert {s["peer_id"] for s in sent} == {"1", "2"}
    assert all(len(s["message"]) <= report.VK_LIMIT for s in sent) and len(sent) >= 4


def test_send_reports_vk_error(monkeypatch) -> None:
    monkeypatch.setattr(config, "VK_REPORT_TOKEN", "token")
    monkeypatch.setattr(config, "VK_REPORT_PEERS", ["1"])
    real = httpx.Client
    reply = httpx.Response(200, json={"error": {"error_msg": "Can't send messages for users without permission"}})
    monkeypatch.setattr(report.httpx, "Client", lambda **kw: real(**kw, transport=httpx.MockTransport(lambda r: reply)))
    assert report.send("привет") == ["1: Can't send messages for users without permission"]


def _backup_status(**st) -> None:
    (config.DATA_DIR / "backup-status.json").write_text(json.dumps(st), "utf-8")


def test_backup_status_in_report(client: TestClient) -> None:
    status = config.DATA_DIR / "backup-status.json"
    try:
        status.unlink(missing_ok=True)
        assert "Автобэкап ещё ни разу не выполнялся" in report.build(live=False)

        fresh = {"at": time.time() - 3600, "ok": True, "users": 21, "size_mb": 30, "error": ""}
        _backup_status(**fresh, remote="ok")
        text = report.build(live=False)
        assert "21 польз., 30 МБ, копия на втором сервере" in text and "бэкап" not in text.split("🩺")[0]

        _backup_status(**fresh, remote="failed")
        assert "копия на второй сервер не ушла" in report.build(live=False)

        _backup_status(**{**fresh, "at": time.time() - 30 * 3600}, remote="ok")
        assert "ночной не сделался" in report.build(live=False)

        _backup_status(at=time.time(), ok=False, users=0, size_mb=0, remote="none", error="снимок базы в контейнере")
        assert "не удался: снимок базы в контейнере" in report.build(live=False)
    finally:
        status.unlink(missing_ok=True)
