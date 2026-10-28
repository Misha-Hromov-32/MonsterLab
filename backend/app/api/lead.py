"""Заявка «Создать карточку»: короткая форма на сайте пересылается во внешний приёмник
(бот ВК CollabX на сервере up-point). Имя, телефон и описание вводит посетитель, направление
подставляет сервер — так в общем чате видно, что заявка пришла именно с этого сайта."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import config
from ..errors import api_error
from ..ratelimit import lead_limit

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class LeadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=30)
    description: str = Field("", max_length=1000)


@router.post("/lead", dependencies=[Depends(lead_limit.dependency)])
async def create_lead(req: LeadRequest) -> dict:
    if not config.LEAD_FORWARD_URL:
        raise api_error(503, "lead_disabled", "Приём заявок сейчас недоступен.")
    name, phone = req.name.strip(), req.phone.strip()
    if not name or not phone:
        raise api_error(422, "invalid", "Укажите имя и телефон.")
    payload = {
        "name": name,
        "phone": phone,
        "direction": config.LEAD_DIRECTION,
        "description": req.description.strip(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(config.LEAD_FORWARD_URL, json=payload)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("Заявка «Создать карточку» не ушла: %s", exc)
        raise api_error(502, "lead_failed", "Не удалось отправить заявку. Попробуйте позже.") from exc
    return {"status": "ok"}
