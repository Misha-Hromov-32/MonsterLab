"""Общие зависимости HTTP-слоя: чтение загрузок, вход в админку, покупатель и лимиты платных функций."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np
from fastapi import Depends, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from .. import config
from ..core.imaging import BadImage, decode
from ..errors import api_error
from ..services import accounts, auth, jobs


async def read_upload(file: UploadFile) -> bytes:
    """Читает файл не больше лимита: лишнее даже не попадает в память."""
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        mb = config.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise api_error(413, "too_large", f"Файл «{file.filename}» больше {mb} МБ")
    return data


async def read_image(file: UploadFile) -> np.ndarray:
    data = await read_upload(file)
    try:
        return await asyncio.to_thread(decode, data)
    except BadImage as exc:
        raise api_error(422, "bad_image", f"{exc}: {file.filename}") from exc


def require_admin(authorization: str | None = Header(None)) -> None:
    """Зависимость для всех ручек админки."""
    if not auth.verify_token((authorization or "").removeprefix("Bearer ").strip()):
        raise api_error(401, "unauthorized", "Войдите заново")


def current_user(authorization: str | None = Header(None)) -> accounts.User | None:
    """Покупатель с подтверждённой почтой по токену входа или None."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    return accounts.user_from_token(token) if token.startswith(f"{accounts.TOKEN_PREFIX}.") else None


def require_user(user: accounts.User | None = Depends(current_user)) -> accounts.User:
    """Все функции сервиса — только после входа: без него открыты лишь главная с витриной и тарифы."""
    if user is None:
        raise api_error(401, "login_required", "Войдите или зарегистрируйтесь, чтобы проверять обложки")
    return user


def paid(feature: str):
    """Зависимость для платной функции: нужен вход и неисчерпанный дневной лимит тарифа.
    Сам запуск списывается в обработчике после успеха — сбой модели лимит не тратит."""

    def dependency(user: accounts.User = Depends(require_user)) -> accounts.User:
        try:
            accounts.check(user, feature)
        except accounts.LimitReached as exc:
            raise api_error(403, "limit_reached", str(exc)) from exc
        return user

    return dependency


SYNC_WAIT_S = 900  # синхронный режим (X-Wait: 1) ждёт не дольше, чем задача может простоять в очереди


async def enqueue(
    request: Request,
    lane: str,
    title: str,
    work: Callable[[], Awaitable[Any]],
    user: accounts.User,
    feature: str,
) -> Any:
    """Ставит тяжёлую работу в очередь. По умолчанию — сразу 202 {"job": …}, клиент опрашивает
    /api/jobs/{id}. С заголовком X-Wait: 1 ждёт результат и возвращает его как обычная ручка
    (удобно для внешних API-клиентов и тестов)."""
    try:
        job = jobs.queue.submit(lane, title, work, user=user, feature=feature)
    except jobs.QueueFull as exc:
        raise api_error(429, exc.code, exc.message) from exc
    if request.headers.get("x-wait") == "1":
        if not await jobs.queue.wait(job, SYNC_WAIT_S):
            raise api_error(504, "timeout", "Очередь не успела дойти до задачи. Попробуйте позже.")
        if job.status == "done":
            return job.result
        err = job.error or {"status": 500, "code": "internal", "message": "Что-то пошло не так"}
        raise api_error(err["status"], err["code"], err["message"])
    return JSONResponse(status_code=202, content={"job": jobs.queue.public(job)})
