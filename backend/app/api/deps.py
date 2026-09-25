"""Общие зависимости HTTP-слоя: чтение загрузок, вход в админку, покупатель и лимиты платных функций."""

from __future__ import annotations

import asyncio

import numpy as np
from fastapi import Depends, Header, UploadFile

from .. import config
from ..core.imaging import BadImage, decode
from ..errors import api_error
from ..services import accounts, auth


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
    """Покупатель по токену входа или None — для функций, доступных и без входа."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    return accounts.user_from_token(token) if token.startswith("u1.") else None


def paid(feature: str):
    """Зависимость для платной функции: нужен вход и неисчерпанный дневной лимит тарифа.
    Сам запуск списывается в обработчике после успеха — сбой модели лимит не тратит."""

    def dependency(user: accounts.User | None = Depends(current_user)) -> accounts.User:
        if user is None:
            raise api_error(401, "login_required", "Войдите, чтобы пользоваться этой функцией")
        try:
            accounts.check(user, feature)
        except accounts.LimitReached as exc:
            raise api_error(403, "limit_reached", str(exc)) from exc
        return user

    return dependency
