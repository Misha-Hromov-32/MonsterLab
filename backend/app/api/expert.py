"""Экспертный разбор: платные запросы к моделям — только после входа, в пределах дневного лимита тарифа."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError

from .. import config
from ..core.imaging import data_url, resize_long, to_jpeg
from ..errors import api_error
from ..ratelimit import expert_limit
from ..schemas import ProductContext
from ..services import accounts, expert
from ..services.uploads import store
from .deps import paid, read_image

log = logging.getLogger(__name__)

# Подробности сбоя (коды провайдера, названия моделей) — в журнал, пользователю — понятная фраза.
FAILED = "Эксперты сейчас не ответили. Попробуйте ещё раз через минуту."

router = APIRouter(prefix="/api/expert", dependencies=[Depends(expert_limit.dependency)])


RIVAL_SIDE = 512  # конкурентам хватает 512 px: модель сравнивает подачу, а не мелкие детали


class CompareRequest(BaseModel):
    variants: dict[str, str] = Field(min_length=2, max_length=config.MAX_VARIANTS)
    context: ProductContext = Field(default_factory=ProductContext)


def _require_enabled() -> None:
    if not expert.current_config().enabled:
        raise api_error(503, "expert_disabled", "Экспертный разбор не подключён")


def _context(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
    except ValueError as exc:
        raise api_error(422, "bad_request", "Некорректные данные о товаре") from exc
    try:
        return ProductContext.model_validate(data).model_dump()
    except ValidationError as exc:  # общий обработчик назовёт поле по-русски: «Проверьте поле «цена»»
        raise RequestValidationError(exc.errors()) from exc


@router.post("/critique")
async def critique(
    id: str = Form(..., max_length=32),
    context: str = Form("{}", max_length=2000),
    competitors: list[UploadFile] = File(default=[]),
    user: accounts.User = Depends(paid("expert")),
) -> dict:
    """Визуальный разбор обложки; competitors — до трёх обложек из выдачи, чтобы оценить её рядом с ними."""
    ctx = _context(context)  # сначала ошибки ввода, потом — подключён ли разбор
    _require_enabled()
    image = await asyncio.to_thread(store.data_url, id)
    rivals = []
    for f in competitors[: config.VISUAL_MAX_RIVALS]:
        rgb = await read_image(f)
        rivals.append(await asyncio.to_thread(lambda x: data_url(to_jpeg(resize_long(x, RIVAL_SIDE))), rgb))
    try:
        result = await expert.critique(image, rivals, ctx)
    except expert.ExpertError as exc:
        log.warning("Экспертный разбор не удался: %s", exc)
        raise api_error(502, "expert_failed", FAILED) from exc
    await asyncio.to_thread(accounts.spend, user, "expert")
    return result


@router.post("/compare")
async def compare(req: CompareRequest, user: accounts.User = Depends(paid("choice"))) -> dict:
    _require_enabled()
    images = {k: await asyncio.to_thread(store.data_url, v) for k, v in req.variants.items()}
    try:
        result = await expert.compare(images, req.context.model_dump())
    except expert.ExpertError as exc:
        log.warning("Экспертный разбор не удался: %s", exc)
        raise api_error(502, "expert_failed", FAILED) from exc
    await asyncio.to_thread(accounts.spend, user, "choice")
    return result
