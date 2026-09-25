"""Платные инструменты: улучшенная обложка и подбор конкурентов из выдачи Wildberries."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import config
from ..core.imaging import data_url, decode
from ..core.report import cover_report
from ..errors import api_error
from ..schemas import ProductContext
from ..services import accounts, improve, marketplace
from ..services.uploads import store
from .deps import paid

router = APIRouter(prefix="/api")

_KEY = re.compile(r"^[0-9a-f]{16}$")
_PRODUCT = re.compile(r"^\d{4,12}$")


class ImproveRequest(BaseModel):
    id: str = Field(max_length=32)
    context: ProductContext = Field(default_factory=ProductContext)
    # замечания экспертного разбора, если он уже был: «проблема — как исправить»
    issues: list[str] = Field(default_factory=list, max_length=6)


def _prepare(image_id: str, issues: list[str], ctx: dict) -> tuple[bytes, str]:
    jpeg = store.jpeg(image_id)
    notes = cover_report(decode(jpeg))["notes"]
    return jpeg, improve.build_prompt(notes, [i[:200] for i in issues], ctx)


@router.post("/improve")
async def improve_cover(req: ImproveRequest, user: accounts.User = Depends(paid("improve"))) -> dict:
    jpeg, prompt = await asyncio.to_thread(_prepare, req.id, req.issues, req.context.model_dump())
    try:
        result = await asyncio.to_thread(improve.generate, jpeg, prompt)
    except improve.ImproveError as exc:
        raise api_error(502, "improve_failed", str(exc)) from exc
    await asyncio.to_thread(accounts.spend, user, "improve")
    return {"image": data_url(result)}


@router.get("/competitors")
async def competitors(
    query: str = Query(min_length=2, max_length=120),
    limit: int = Query(8, ge=1, le=config.MAX_COMPETITORS),
    user: accounts.User = Depends(paid("competitors")),
) -> dict:
    try:
        items = await marketplace.search(query, limit)
    except marketplace.MarketplaceError as exc:
        raise api_error(502, "marketplace_failed", str(exc)) from exc
    await asyncio.to_thread(accounts.spend, user, "competitors")
    key = marketplace.query_key(query)
    return {
        "query": query,
        "items": [{**i, "url": f"/api/competitors/files/{key}/{i['id']}.jpg"} for i in items],
    }


@router.get("/competitors/files/{key}/{name}")
def competitor_file(key: str, name: str) -> FileResponse:
    product_id = name.removesuffix(".jpg")
    if not (_KEY.match(key) and _PRODUCT.match(product_id)):
        raise HTTPException(404)
    path = marketplace.image_path(key, product_id)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
