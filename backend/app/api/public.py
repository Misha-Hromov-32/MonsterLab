"""Публичные данные главной: тексты, опубликованные примеры, файлы примеров и витрина."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services import showcase, site

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
    examples = await asyncio.to_thread(site.published_examples)
    if not examples:
        return None
    return await showcase.get(examples[0])
