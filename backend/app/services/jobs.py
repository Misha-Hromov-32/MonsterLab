"""Очередь тяжёлых задач: нейросеть внимания, языковые модели, генерация обложек, браузер для WB.

Каждая задача попадает в свою полосу (lane) с ограниченным числом одновременных исполнителей —
так сервер не захлёбывается, сколько бы покупателей ни нажали кнопку одновременно.
Внутри полосы очередь равная для всех тарифов и идёт по кругу между покупателями: следующей
запускается задача того, кого обслуживали давнее всех, — тот, кто отправил десять обложек разом,
не заставляет остальных ждать все десять. Свои задачи у каждого идут в порядке отправки;
фоновый пересчёт примеров — в самом конце.

Квота функции проверяется ещё раз прямо перед запуском (пока задача ждала, квоту могли израсходовать
другие задачи того же покупателя) и списывается только после успеха: сбой модели квоту не тратит.

HTTP: тяжёлая ручка ставит задачу и сразу отвечает 202 {"job": …}; клиент опрашивает
GET /api/jobs/{id} — место в очереди и оценку ожидания, потом результат или ошибку.
Всё живёт в памяти процесса (uvicorn --workers 1): после перезапуска очередь пустая.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import logging
import secrets
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from .. import config
from . import accounts, aicost
from .uploads import ImageExpired

log = logging.getLogger(__name__)

CUSTOMER = 0  # все покупатели равны, независимо от тарифа
BACKGROUND = 9  # фоновые задачи — после всех покупателей
KEEP_FINISHED_S = 15 * 60  # результат ждёт клиента 15 минут
STATS_WINDOW_S = 60 * 60


@dataclass(frozen=True)
class LaneSpec:
    title: str
    workers: int
    typical_s: float  # оценка длительности, пока нет своей статистики


LANES: dict[str, LaneSpec] = {
    "neural": LaneSpec("Нейросеть внимания", config.QUEUE_NEURAL_WORKERS, 3),
    "ai": LaneSpec("Языковые модели", config.QUEUE_AI_WORKERS, 20),
    "image": LaneSpec("Генерация обложек", config.QUEUE_IMAGE_WORKERS, 35),
    "browser": LaneSpec("Браузер для WB", config.QUEUE_BROWSER_WORKERS, 15),
}


class QueueFull(Exception):
    """Очередь переполнена или у покупателя слишком много задач — понятная фраза для пользователя."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class Job:
    id: str
    lane: str
    title: str
    work: Callable[[], Awaitable[Any]] = field(repr=False)
    user: accounts.User | None = None
    feature: str | None = None
    priority: int = BACKGROUND
    seq: int = 0
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    status: str = "queued"  # queued | running | done | error | cancelled
    result: Any = None
    error: dict | None = None
    done_event: threading.Event = field(default_factory=threading.Event, repr=False)
    done_async: asyncio.Event | None = field(default=None, repr=False)
    waiter_loop: asyncio.AbstractEventLoop | None = field(default=None, repr=False)


def priority_for(user: accounts.User | None) -> int:
    return BACKGROUND if user is None else CUSTOMER


def _error_of(exc: BaseException) -> dict:
    """Ошибка задачи в формате API: {status, code, message}."""
    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
        return {"status": exc.status_code, **exc.detail}
    if isinstance(exc, ImageExpired):
        return {"status": 404, "code": "image_expired", "message": "Изображение не найдено, загрузите его заново"}
    if isinstance(exc, accounts.LimitReached):
        return {"status": 403, "code": "limit_reached", "message": str(exc)}
    if isinstance(exc, asyncio.TimeoutError | TimeoutError):
        return {
            "status": 504,
            "code": "timeout",
            "message": "Обработка заняла слишком много времени. Попробуйте ещё раз.",
        }
    log.exception("Задача очереди упала", exc_info=exc)
    return {"status": 500, "code": "internal", "message": "Что-то пошло не так. Попробуйте ещё раз."}


class JobQueue:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._waiting: dict[str, list[str]] = {lane: [] for lane in LANES}  # id задач в порядке постановки
        self._served: dict[int, float] = {}  # покупатель → когда последний раз запускали его задачу
        self._running: dict[str, int] = dict.fromkeys(LANES, 0)
        self._seq = itertools.count()
        self._stats: deque[tuple[float, str, float, float, bool]] = deque(maxlen=5000)  # ts, lane, wait, run, ok
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: dict[str, asyncio.Event] = {}
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------ жизненный цикл

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = {lane: asyncio.Event() for lane in LANES}
        for lane, spec in LANES.items():
            for i in range(max(1, spec.workers)):
                self._tasks.append(asyncio.create_task(self._worker(lane), name=f"queue-{lane}-{i}"))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        self._loop = None

    @property
    def running(self) -> bool:
        return self._loop is not None

    # ------------------------------------------------------------ постановка

    def submit(
        self,
        lane: str,
        title: str,
        work: Callable[[], Awaitable[Any]],
        user: accounts.User | None = None,
        feature: str | None = None,
        priority: int | None = None,
    ) -> Job:
        """Ставит задачу (вызывать из event loop). QueueFull — если ставить некуда."""
        self._cleanup()
        waiting = len(self._waiting[lane])
        if user is not None and waiting >= config.QUEUE_MAX_WAITING:
            raise QueueFull("queue_full", "Сервис сейчас перегружен. Попробуйте через пару минут.")
        if user is not None:
            mine = sum(
                1 for j in self.jobs.values() if j.user and j.user.id == user.id and j.status in ("queued", "running")
            )
            if mine >= config.QUEUE_PER_USER:
                raise QueueFull("too_many_jobs", "У вас уже много задач в обработке — дождитесь, пока они закончатся.")
        job = Job(
            id=secrets.token_urlsafe(12),
            lane=lane,
            title=title,
            work=work,
            user=user,
            feature=feature,
            priority=priority_for(user) if priority is None else priority,
            seq=next(self._seq),
        )
        job.done_async = asyncio.Event()
        job.waiter_loop = asyncio.get_running_loop()
        self.jobs[job.id] = job
        self._waiting[lane].append(job.id)
        self._signal(self._loop, self._wake[lane].set)
        return job

    @staticmethod
    def _signal(loop: asyncio.AbstractEventLoop | None, fn: Callable[[], None]) -> None:
        """asyncio.Event будит только свой цикл: из чужого потока или цикла — через call_soon_threadsafe."""
        if loop is None or _in_loop(loop):
            fn()
        else:
            loop.call_soon_threadsafe(fn)

    def _finish(self, job: Job) -> None:
        job.done_event.set()
        if job.done_async is not None:
            self._signal(job.waiter_loop, job.done_async.set)

    async def wait(self, job: Job, timeout: float) -> bool:
        """Дождаться конца задачи (в event loop). False — не дождались за timeout."""
        if job.done_async is None or job.done_event.is_set():
            return job.done_event.is_set()
        try:
            await asyncio.wait_for(job.done_async.wait(), timeout)
            return True
        except TimeoutError:
            return False

    def run_blocking(self, lane: str, title: str, fn: Callable[[], Any], priority: int = BACKGROUND) -> Any:
        """Выполнить функцию через очередь из обычного потока (фоновый пересчёт примеров) и дождаться.
        Очередь не запущена (тесты, вызов из самого event loop) — функция выполняется сразу."""
        loop = self._loop
        if loop is None or _in_loop(loop):
            return fn()

        async def work() -> Any:
            return await asyncio.to_thread(fn)

        holder: dict[str, Job] = {}
        ready = threading.Event()

        def put() -> None:
            holder["job"] = self.submit(lane, title, work, priority=priority)
            ready.set()

        loop.call_soon_threadsafe(put)
        ready.wait()
        job = holder["job"]
        job.done_event.wait()
        if job.status != "done":
            raise RuntimeError((job.error or {}).get("message", "задача не выполнена"))
        return job.result

    def cancel(self, job: Job) -> bool:
        """Снимает задачу, которая ещё ждёт; запущенную не прерываем."""
        if job.status != "queued":
            return False
        self._waiting[job.lane].remove(job.id)
        job.status, job.finished = "cancelled", time.time()
        self._finish(job)
        return True

    # ------------------------------------------------------------ исполнение

    def _order(self, lane: str) -> list[Job]:
        """Ожидающие задачи полосы в порядке запуска: по кругу между покупателями.

        Ключ: фон — после покупателей; у кого меньше задач уже выполняется — раньше; кого обслуживали
        давнее — раньше (новичок, которого ещё не обслуживали, — сразу); свои задачи — в порядке отправки.
        """
        running: dict[int, int] = {}
        for j in self.jobs.values():
            if j.status == "running" and j.lane == lane and j.user is not None:
                running[j.user.id] = running.get(j.user.id, 0) + 1
        waiting = [self.jobs[i] for i in self._waiting[lane] if i in self.jobs]

        # у одного покупателя ключ растёт с каждой его задачей в очереди: вторая задача идёт после первых
        # задач остальных — для этого «обслуженность» считаем с учётом его же задач, стоящих раньше
        ahead: dict[int, int] = {}
        keyed = []
        for j in sorted(waiting, key=lambda x: x.seq):
            uid = j.user.id if j.user else -1
            rank = ahead.get(uid, 0)
            ahead[uid] = rank + 1
            keyed.append(((j.priority, rank + running.get(uid, 0), self._served.get(uid, 0.0), j.seq), j))
        return [j for _, j in sorted(keyed, key=lambda x: x[0])]

    async def _worker(self, lane: str) -> None:
        waiting, wake = self._waiting[lane], self._wake[lane]
        while True:
            while not waiting:
                wake.clear()
                await wake.wait()
            order = self._order(lane)
            if not order:
                waiting.clear()
                continue
            job = order[0]
            waiting.remove(job.id)
            if job.user is not None:
                self._served[job.user.id] = time.time()
            await self._run(job)

    async def _run(self, job: Job) -> None:
        job.status, job.started = "running", time.time()
        self._running[job.lane] += 1
        ok = False
        try:
            if job.created + config.QUEUE_MAX_WAIT_S < job.started:
                raise HTTPException(
                    503, {"code": "queue_timeout", "message": "Очередь слишком длинная. Попробуйте позже."}
                )
            if job.user is not None and job.feature:
                await asyncio.to_thread(accounts.check, job.user, job.feature)
            # журнал расходов на нейросети: чей запрос и какая функция (наследуется задачами и потоками)
            aicost.CALLER.set((job.user.id if job.user else None, job.feature or "background"))
            job.result = await asyncio.wait_for(job.work(), timeout=config.QUEUE_JOB_TIMEOUT_S)
            if job.user is not None and job.feature:
                await asyncio.to_thread(accounts.spend, job.user, job.feature)
            job.status, ok = "done", True
        except asyncio.CancelledError:
            job.status, job.error = "error", {"status": 503, "code": "restarting", "message": "Сервис перезапускается"}
            raise
        except Exception as exc:  # noqa: BLE001 — любая ошибка задачи идёт клиенту, исполнитель живёт дальше
            job.status, job.error = "error", _error_of(exc)
        finally:
            job.finished = time.time()
            self._running[job.lane] -= 1
            self._stats.append((job.finished, job.lane, job.started - job.created, job.finished - job.started, ok))
            job.work = _done  # замыкание держит картинки — отпускаем память сразу
            self._finish(job)

    def _cleanup(self) -> None:
        now = time.time()
        for job_id in [i for i, j in self.jobs.items() if j.finished and now - j.finished > KEEP_FINISHED_S]:
            del self.jobs[job_id]

    # ------------------------------------------------------------ состояние

    def _avg_run(self, lane: str) -> float:
        recent = [run for ts, ln, _, run, ok in self._stats if ln == lane and ok and time.time() - ts < STATS_WINDOW_S]
        return sum(recent[-50:]) / len(recent[-50:]) if recent else LANES[lane].typical_s

    def position(self, job: Job) -> int:
        """1 — следующая на запуск; 0 — уже не ждёт."""
        if job.status != "queued":
            return 0
        order = self._order(job.lane)
        return 1 + next((i for i, j in enumerate(order) if j.id == job.id), len(order))

    def public(self, job: Job) -> dict:
        """То, что видит покупатель: статус, место, оценка ожидания."""
        pos = self.position(job)
        avg = self._avg_run(job.lane)
        workers = max(1, LANES[job.lane].workers)
        if job.status == "queued":
            eta = ((pos - 1) // workers + 1) * avg
        elif job.status == "running":
            eta = max(1.0, avg - (time.time() - (job.started or time.time())))
        else:
            eta = 0
        out = {
            "id": job.id,
            "lane": job.lane,
            "title": job.title,
            "status": job.status,
            "position": pos,
            "eta_s": round(eta),
            "waited_s": round((job.started or time.time()) - job.created, 1),
        }
        if job.status == "done":
            out["result"] = job.result
        if job.error:
            out["error"] = job.error
        return out

    def snapshot(self) -> dict:
        """Для админки: загрузка полос и все задачи, которые ждут или выполняются."""
        now = time.time()
        lanes = []
        for lane, spec in LANES.items():
            recent = [(w, r, ok) for ts, ln, w, r, ok in self._stats if ln == lane and now - ts < STATS_WINDOW_S]
            done = [x for x in recent if x[2]]
            lanes.append(
                {
                    "id": lane,
                    "title": spec.title,
                    "workers": spec.workers,
                    "running": self._running[lane],
                    "waiting": len(self._waiting[lane]),
                    "done_1h": len(done),
                    "failed_1h": len(recent) - len(done),
                    "avg_wait_s": round(sum(w for w, _, _ in recent) / len(recent), 1) if recent else 0,
                    "avg_run_s": round(sum(r for _, r, _ in done) / len(done), 1) if done else 0,
                }
            )
        running = [j for j in self.jobs.values() if j.status == "running"]
        active = sorted(running, key=lambda j: (j.lane, j.started or 0)) + [
            j for lane in LANES for j in self._order(lane)
        ]
        return {
            "lanes": lanes,
            "jobs": [
                {
                    "lane": j.lane,
                    "title": j.title,
                    "status": j.status,
                    "user_id": j.user.id if j.user else None,
                    "plan": j.user.plan if j.user else "фон",
                    "position": self.position(j),
                    "waited_s": round((j.started or now) - j.created, 1),
                    "running_s": round(now - j.started, 1) if j.started else 0,
                }
                for j in active
            ],
        }


async def _done() -> None:
    return None


def _in_loop(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


queue = JobQueue()
