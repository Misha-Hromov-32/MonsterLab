"""Публичные данные главной: тексты, опубликованные примеры, их файлы и заранее посчитанные результаты."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..core.imaging import decode
from ..ratelimit import analysis_limit
from ..services import precompute, site
from ..services.uploads import store

router = APIRouter(prefix="/api/public")

_ID = re.compile(r"^[0-9a-f]{1,32}$")


PUBLIC_FIELDS = ("id", "title", "description", "context", "variants", "competitors")


def _example_out(ex: dict) -> dict:
    full = site.example_out(ex)
    return {k: full.get(k, "") for k in PUBLIC_FIELDS}


@router.get("/site")
def get_site() -> dict:
    return {
        "landing": site.read()["landing"],
        "examples": [_example_out(e) for e in site.published_examples()],
    }


@router.get("/files/{example_id}/{name}")
def get_file(example_id: str, name: str) -> FileResponse:
    image_id = name.removesuffix(".jpg")
    if not (_ID.match(example_id) and _ID.match(image_id)):
        raise HTTPException(404)
    path = site.image_path(example_id, image_id)
    if not path.is_file():
        raise HTTPException(404)
    # id картинки меняется при каждой замене, поэтому кэш можно держать долго
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800, immutable"})


@router.get("/showcase")
async def get_showcase() -> dict | None:
    """Витрина главной — из заранее посчитанного первого примера; пока расчёт идёт — null."""
    examples = await asyncio.to_thread(site.published_examples)
    if not examples:
        return None
    payload = await asyncio.to_thread(precompute.load, examples[0])
    return payload["showcase"] if payload else None


def _register(ex: dict, payload: dict) -> dict:
    """Кладёт обложки примера в очередь загрузок, как будто их только что прислали, — чтобы
    экспертный разбор и полка с другими конкурентами работали без повторного расчёта."""
    out = {}
    for image_id, report in payload["variants"].items():
        rgb = decode(site.image_path(ex["id"], image_id).read_bytes())
        out[image_id] = {**report, "id": store.put(rgb)}
    return out


@router.get("/examples/{example_id}/results", dependencies=[Depends(analysis_limit.dependency)])
async def get_results(example_id: str) -> dict:
    """Готовый разбор обложек и тест полки для примера — без нейросети на каждый показ."""
    ex = next((e for e in await asyncio.to_thread(site.published_examples) if e["id"] == example_id), None)
    if ex is None:
        raise HTTPException(404)
    payload = await asyncio.to_thread(precompute.load, ex)
    if payload is None:
        return {"ready": False}
    variants = await asyncio.to_thread(_register, ex, payload)
    return {"ready": True, "keys": payload["keys"], "variants": variants, "shelf": payload["shelf"]}
