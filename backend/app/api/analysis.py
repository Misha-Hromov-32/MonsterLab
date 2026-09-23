"""Анализ обложки и тест полки."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import __version__, config
from ..core import saliency, shelf
from ..core.report import cover_report
from ..errors import api_error
from ..ratelimit import analysis_limit
from ..services import expert
from ..services.uploads import store
from .deps import read_image

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    cfg = expert.current_config()
    return {
        "ok": True,
        "version": __version__,
        "neural": saliency.deepgaze.ready,
        "expert": {"enabled": cfg.enabled, "models": cfg.models},
    }


@router.post("/analyze", dependencies=[Depends(analysis_limit.dependency)])
async def analyze(file: UploadFile = File(...)) -> dict:
    rgb = await read_image(file)
    image_id = await asyncio.to_thread(store.put, rgb)
    return {"id": image_id, **await asyncio.to_thread(cover_report, rgb)}


def _parse_variants(raw: str) -> dict[str, str]:
    try:
        ids = json.loads(raw)
    except ValueError:
        ids = None
    if not isinstance(ids, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in ids.items()):
        raise api_error(422, "bad_request", "Некорректный список вариантов")
    if len(ids) > config.MAX_VARIANTS:
        raise api_error(422, "too_many", f"Не больше {config.MAX_VARIANTS} вариантов")
    return ids


@router.post("/shelf", dependencies=[Depends(analysis_limit.dependency)])
async def run_shelf(
    variants: str = Form(..., description='JSON: {"A": "<id загруженной обложки>", …}'),
    layout: str = Form("mobile"),
    competitors: list[UploadFile] = File(default=[]),
) -> dict:
    ids = _parse_variants(variants)
    if len(competitors) > config.MAX_COMPETITORS:
        raise api_error(422, "too_many", f"Не больше {config.MAX_COMPETITORS} конкурентов")
    images = {k: await asyncio.to_thread(store.rgb, v) for k, v in ids.items()}
    rivals = [await read_image(f) for f in competitors]
    if not images or (not rivals and len(images) < 2):
        raise api_error(422, "need_more", "Нужно два варианта или хотя бы один конкурент")
    started = time.perf_counter()
    result = await asyncio.to_thread(shelf.run, images, rivals, layout)
    return {**result, "timing": round(time.perf_counter() - started, 1)}
