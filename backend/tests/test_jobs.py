"""Очередь тяжёлых задач: приоритет тарифов, ограничение на покупателя, отмена и опрос по HTTP."""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import jobs
from app.services.accounts import User

from .conftest import jpeg_bytes, make_cover, verified_token

DEMO = User(1, "demo@example.com", 0, True, "s")
AGENCY = User(2, "agency@example.com", time.time() + 86400, True, "s", "agency")
PETYA = User(3, "petya@example.com", 0, True, "s")
MASHA = User(4, "masha@example.com", 0, True, "s")


def _one_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(jobs.LANES, "neural", jobs.LaneSpec("тест", 1, 1))


def _mark(order: list[str], name: str):
    async def work() -> None:
        order.append(name)

    return work


def test_plan_does_not_matter_first_come_first_served(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_worker(monkeypatch)

    async def scenario() -> list[str]:
        q = jobs.JobQueue()
        await q.start()
        gate, order = asyncio.Event(), []
        q.submit("neural", "занимает исполнителя", gate.wait)
        await asyncio.sleep(0.05)
        background = q.submit("neural", "фон", _mark(order, "фон"))
        demo = q.submit("neural", "демо", _mark(order, "демо"), user=DEMO)
        agency = q.submit("neural", "агентство", _mark(order, "агентство"), user=AGENCY)
        # тариф не даёт обгона: демо пришёл раньше — раньше и пойдёт; фон — в самом конце
        assert [q.position(j) for j in (demo, agency, background)] == [1, 2, 3]
        assert q.public(agency)["eta_s"] >= 1
        gate.set()
        for job in (demo, agency, background):
            assert await q.wait(job, 5)
        await q.stop()
        return order

    assert asyncio.run(scenario()) == ["демо", "агентство", "фон"]


def test_round_robin_between_customers(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_worker(monkeypatch)

    async def scenario() -> list[str]:
        q = jobs.JobQueue()
        await q.start()
        gate, order = asyncio.Event(), []
        q.submit("neural", "занимает исполнителя", gate.wait)
        await asyncio.sleep(0.05)
        petya = [q.submit("neural", f"Петя {i}", _mark(order, f"Петя {i}"), user=PETYA) for i in (1, 2, 3)]
        masha = q.submit("neural", "Маша", _mark(order, "Маша"), user=MASHA)
        # Маша пришла последней, но не ждёт все три задачи Пети
        assert q.position(masha) == 2 and q.position(petya[2]) == 4
        gate.set()
        for job in (*petya, masha):
            assert await q.wait(job, 5)
        await q.stop()
        return order

    assert asyncio.run(scenario()) == ["Петя 1", "Маша", "Петя 2", "Петя 3"]


def test_per_user_cap_and_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_worker(monkeypatch)
    monkeypatch.setattr(config, "QUEUE_PER_USER", 2)

    async def scenario() -> None:
        q = jobs.JobQueue()
        await q.start()
        gate = asyncio.Event()
        q.submit("neural", "занимает исполнителя", gate.wait)
        await asyncio.sleep(0.05)
        first = q.submit("neural", "1", gate.wait, user=DEMO)
        q.submit("neural", "2", gate.wait, user=DEMO)
        with pytest.raises(jobs.QueueFull) as exc:
            q.submit("neural", "3", gate.wait, user=DEMO)
        assert exc.value.code == "too_many_jobs"
        assert q.cancel(first) and first.status == "cancelled"
        q.submit("neural", "3", gate.wait, user=DEMO)  # место освободилось
        gate.set()
        await q.stop()

    asyncio.run(scenario())


def test_failed_job_reports_error_without_killing_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_worker(monkeypatch)

    async def scenario() -> tuple[dict, str]:
        q = jobs.JobQueue()
        await q.start()

        async def boom() -> None:
            raise ValueError("сбой")

        async def fine() -> str:
            return "ок"

        bad = q.submit("neural", "падает", boom)
        good = q.submit("neural", "работает", fine)
        await q.wait(bad, 5)
        await q.wait(good, 5)
        await q.stop()
        return bad.error, good.result

    error, result = asyncio.run(scenario())
    assert error["code"] == "internal" and result == "ок"


def test_http_job_polling_and_privacy(client: TestClient, anon: TestClient) -> None:
    files = {"file": ("c.jpg", jpeg_bytes(make_cover(11)), "image/jpeg")}
    r = client.post("/api/analyze", files=files, headers={"X-Wait": "0"})
    assert r.status_code == 202
    job = r.json()["job"]
    assert job["status"] in ("queued", "running", "done") and job["title"] == "Проверка обложки"

    for _ in range(40):
        job = client.get(f"/api/jobs/{job['id']}", params={"wait": 2}).json()["job"]
        if job["status"] == "done":
            break
    assert job["status"] == "done" and "index" in job["result"]

    stranger = {"Authorization": f"Bearer {verified_token(anon)}"}
    assert anon.get(f"/api/jobs/{job['id']}", headers=stranger).status_code == 404
    assert anon.get(f"/api/jobs/{job['id']}").status_code == 401


def test_admin_sees_queue(client: TestClient) -> None:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    snap = client.get("/api/admin/queue", headers={"Authorization": f"Bearer {token}"}).json()
    assert {lane["id"] for lane in snap["lanes"]} == {"neural", "ai", "image", "browser"}
    assert isinstance(snap["jobs"], list)
