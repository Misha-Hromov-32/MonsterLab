"""Личный кабинет: чтение и удаление только собственных обложек."""

import json

from fastapi import APIRouter, Depends, Query, Response

from ..core.imaging import data_url, decode
from ..services import accounts, library
from ..services.uploads import store
from .deps import require_user

router = APIRouter(prefix="/api/library")


@router.get("")
def covers(
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=48),
    user: accounts.User = Depends(require_user),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return library.listing(user.id, offset, limit)


@router.get("/{key}")
def cover(key: str, response: Response, user: accounts.User = Depends(require_user)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    row = library.get(user.id, key)
    report = json.loads(row["report"]) if row["report"] else None
    if report is not None:
        report = {**report, "id": store.put(decode(row["jpeg"]))}
    return {
        "id": key,
        "name": row["name"],
        "image": data_url(row["jpeg"]),
        "analysis": report,
        "generated_baseline": row["baseline"],
    }


@router.get("/{key}/download")
def download(key: str, user: accounts.User = Depends(require_user)) -> Response:
    row = library.get(user.id, key)
    return Response(row["jpeg"], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.delete("/{key}")
def delete(key: str, user: accounts.User = Depends(require_user)) -> dict:
    library.remove(user.id, key)
    return {"ok": True}
