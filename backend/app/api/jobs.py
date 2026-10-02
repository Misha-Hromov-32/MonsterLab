"""Задачи очереди: статус, место в очереди, результат и отмена."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Query

from ..errors import api_error
from ..services import accounts, jobs
from .deps import require_user

router = APIRouter(prefix="/api/jobs")

LONG_POLL_STEP_S = 0.25


def _own(job_id: str, user: accounts.User) -> jobs.Job:
    job = jobs.queue.jobs.get(job_id)
    if job is None or job.user is None or job.user.id != user.id:
        raise api_error(404, "job_not_found", "Задача не найдена — запустите её заново")
    return job


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    wait: float = Query(0, ge=0, le=20, description="подождать изменения до N секунд (long polling)"),
    user: accounts.User = Depends(require_user),
) -> dict:
    """Статус задачи. С wait=N отвечает, как только задача завершилась или сдвинулась в очереди, —
    клиенту хватает редких запросов, а результат приходит без задержки."""
    job = _own(job_id, user)
    seen = (job.status, jobs.queue.position(job))
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline and job.status in ("queued", "running"):
        if (job.status, jobs.queue.position(job)) != seen:
            break
        await asyncio.sleep(LONG_POLL_STEP_S)
    return {"job": jobs.queue.public(job)}


@router.delete("/{job_id}")
def cancel_job(job_id: str, user: accounts.User = Depends(require_user)) -> dict:
    """Снять задачу, которая ещё ждёт (покупатель заменил картинку или ушёл со страницы)."""
    return {"cancelled": jobs.queue.cancel(_own(job_id, user))}
