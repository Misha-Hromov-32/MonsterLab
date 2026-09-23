"""Экспертный разбор: платные запросы к моделям, поэтому с лимитом частоты."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import config
from ..errors import api_error
from ..ratelimit import expert_limit
from ..schemas import ProductContext
from ..services import expert
from ..services.uploads import store

log = logging.getLogger(__name__)

# Подробности сбоя (коды провайдера, названия моделей) — в журнал, пользователю — понятная фраза.
FAILED = "Эксперты сейчас не ответили. Попробуйте ещё раз через минуту."

router = APIRouter(prefix="/api/expert", dependencies=[Depends(expert_limit.dependency)])


class CritiqueRequest(BaseModel):
    id: str = Field(max_length=32)
    context: ProductContext = Field(default_factory=ProductContext)


class CompareRequest(BaseModel):
    variants: dict[str, str] = Field(min_length=2, max_length=config.MAX_VARIANTS)
    context: ProductContext = Field(default_factory=ProductContext)


def _require_enabled() -> None:
    if not expert.current_config().enabled:
        raise api_error(503, "expert_disabled", "Экспертный разбор не подключён")


@router.post("/critique")
async def critique(req: CritiqueRequest) -> dict:
    _require_enabled()
    image = await asyncio.to_thread(store.data_url, req.id)
    try:
        return await expert.critique(image, req.context.model_dump())
    except expert.ExpertError as exc:
        log.warning("Экспертный разбор не удался: %s", exc)
        raise api_error(502, "expert_failed", FAILED) from exc


@router.post("/compare")
async def compare(req: CompareRequest) -> dict:
    _require_enabled()
    images = {k: await asyncio.to_thread(store.data_url, v) for k, v in req.variants.items()}
    try:
        return await expert.compare(images, req.context.model_dump())
    except expert.ExpertError as exc:
        log.warning("Экспертный разбор не удался: %s", exc)
        raise api_error(502, "expert_failed", FAILED) from exc
