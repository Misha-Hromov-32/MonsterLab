"""Платные инструменты: улучшенная обложка и подбор конкурентов из выдачи Wildberries."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import config
from ..core.imaging import data_url, decode
from ..core.report import cover_report
from ..errors import api_error
from ..schemas import ProductContext
from ..services import accounts, credits, image_models, improve, library, marketplace
from ..services.uploads import store
from .deps import enqueue, paid, read_image, require_user

router = APIRouter(prefix="/api")

_KEY = re.compile(r"^[0-9a-f]{16}$")
_PRODUCT = re.compile(r"^\d{4,12}$")


class ImproveRequest(BaseModel):
    model: str = Field("", max_length=100)
    prompt: str = Field("", max_length=1800)
    id: str = Field(max_length=32)
    context: ProductContext = Field(default_factory=ProductContext)
    # замечания экспертного разбора, если он уже был: «проблема — как исправить»
    issues: list[str] = Field(default_factory=list, max_length=6)


def generation_terms(model, user):
    selected = model or image_models.default_id()
    if selected not in image_models.MODELS:
        raise api_error(422, "unknown_model", "Выберите модель из списка")
    cost = image_models.cost(selected)
    try:
        credits.ensure(user, cost)
    except accounts.LimitReached as exc:
        raise api_error(403, "limit_reached", str(exc)) from exc
    return selected, cost


async def generate_cover(request, user, model, custom, jpeg, notes, issues, context, baseline):
    selected, cost = generation_terms(model, user)
    prompt = improve.build_prompt(notes, issues, context)
    if custom.strip():
        prompt += (
            "\n\nЗадание продавца для нового варианта. Следуй пожеланиям по фону, стилю и композиции."
            " Сохрани товар и его свойства.\n"
            + custom.strip()
        )

    async def work():
        try:
            result = await asyncio.to_thread(improve.generate, jpeg, prompt, selected)
        except improve.ImproveError as exc:
            raise api_error(502, "improve_failed", str(exc)) from exc
        saved = await asyncio.to_thread(
            library.save, user.id, decode(result), "Сгенерированная обложка", None, "generated", baseline
        )
        return {"image": data_url(result), "model": selected, "cost": cost, **saved}

    return await enqueue(request, "image", "Генерация обложки", work, user, "improve", cost)


@router.post("/improve")
async def improve_cover(request: Request, req: ImproveRequest, user: accounts.User = Depends(require_user)):
    jpeg = store.jpeg(req.id)
    report = await asyncio.to_thread(lambda: cover_report(decode(jpeg)))
    return await generate_cover(
        request,
        user,
        req.model,
        req.prompt,
        jpeg,
        report["notes"],
        [i[:200] for i in req.issues],
        req.context.model_dump(),
        report["index"],
    )


@router.post("/improve/from-photo")
async def from_photo(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("", max_length=100),
    prompt: str = Form("", max_length=1800),
    user: accounts.User = Depends(require_user),
):
    from ..core.imaging import to_jpeg

    image = await read_image(file)
    jpeg = await asyncio.to_thread(to_jpeg, image)
    return await generate_cover(request, user, model, prompt, jpeg, [], [], {}, None)


@router.get("/competitors")
async def competitors(
    request: Request,
    query: str = Query(min_length=2, max_length=120),
    limit: int = Query(8, ge=1, le=config.MAX_COMPETITORS),
    user: accounts.User = Depends(paid("competitors")),
):
    async def work() -> dict:
        try:
            items = await marketplace.search(query, limit)
        except marketplace.MarketplaceError as exc:
            raise api_error(502, "marketplace_failed", str(exc)) from exc
        key = marketplace.query_key(query)
        return {
            "query": query,
            "items": [{**i, "url": f"/api/competitors/files/{key}/{i['id']}.jpg"} for i in items],
        }

    return await enqueue(request, "browser", "Подбор конкурентов", work, user, "competitors")


@router.get("/competitors/files/{key}/{name}")
def competitor_file(key: str, name: str) -> FileResponse:
    product_id = name.removesuffix(".jpg")
    if not (_KEY.match(key) and _PRODUCT.match(product_id)):
        raise HTTPException(404)
    path = marketplace.image_path(key, product_id)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
