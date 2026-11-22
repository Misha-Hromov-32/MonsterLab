import asyncio
import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, SecretStr

from ..core.imaging import BadImage, open_image
from ..errors import api_error
from ..ratelimit import analysis_limit
from ..services import accounts, card_rules, credits, db, wb_audit
from .deps import read_upload, require_user

router = APIRouter(prefix="/api")


@router.post("/card-rules", dependencies=[Depends(analysis_limit.dependency)])
async def card_check(
    market: Literal["wb", "ozon"] = Form(),
    title: str = Form("", max_length=500),
    description: str = Form("", max_length=18000),
    caption: str = Form("", max_length=5000),
    cover: UploadFile | None = File(None),
    user: accounts.User = Depends(require_user),
):
    if not (title.strip() or description.strip() or caption.strip() or cover):
        raise api_error(422, "empty", "Добавьте текст или изображение карточки")
    reserve = await asyncio.to_thread(credits.reserve, user, "rules")
    try:
        result = await inspect_fields(market, title, description, caption, cover)
    except BaseException:
        await asyncio.to_thread(credits.finish, reserve, False)
        raise
    await asyncio.to_thread(credits.finish, reserve, True)
    return result


async def inspect_fields(market, title, description, caption, cover):
    status = ""
    image_findings = []
    if cover:
        try:
            data = await read_upload(cover)
            image = await asyncio.to_thread(open_image, data, 1600)
            image_findings = await asyncio.to_thread(card_rules.inspect_cover, market, image, len(data))
            text, status = await asyncio.to_thread(card_rules.read_cover, image)
        except BadImage as exc:
            raise api_error(422, "bad_image", str(exc)) from exc
        caption += "\n" + text
    return {
        "findings": image_findings + card_rules.check(market, Название=title, Описание=description, Обложка=caption),
        "image_status": status,
        "source": card_rules.SOURCES[market],
    }


class Connection(BaseModel):
    token: SecretStr = Field(min_length=16, max_length=8192)


@router.post("/wb/audits", dependencies=[Depends(analysis_limit.dependency)])
def create(body: Connection, user: accounts.User = Depends(require_user)):
    return {"id": wb_audit.start(user.id, body.token.get_secret_value().strip())}


@router.get("/wb/audits")
def history(user: accounts.User = Depends(require_user)):
    with db.connect() as con:
        return [
            dict(r)
            for r in con.execute("SELECT id,status,created FROM wb_audits WHERE owner=? ORDER BY id DESC", (user.id,))
        ]


def owned(con, run, owner):
    row = con.execute("SELECT id,status,message,created FROM wb_audits WHERE id=? AND owner=?", (run, owner)).fetchone()
    if not row:
        raise api_error(404, "not_found", "Отчёт не найден")
    return dict(row)


@router.get("/wb/audits/{run}")
def report(run: int, offset: int = Query(0, ge=0), user: accounts.User = Depends(require_user)):
    with db.connect() as con:
        result = owned(con, run, user.id)
        summary = con.execute(
            "SELECT count(*) total,round(avg(score)) average_score,coalesce(sum(checked),0) checked,"
            " count(CASE WHEN findings<>'[]' THEN 1 END) flagged,"
            " count(CASE WHEN checked=1 AND image_status<>'Текст распознан' THEN 1 END) manual"
            " FROM wb_cards WHERE audit=?",
            (run,),
        ).fetchone()
        items = [
            dict(r)
            for r in con.execute(
                "SELECT nm,sku,title,score,findings,image_status FROM wb_cards WHERE audit=?"
                " ORDER BY nm LIMIT 40 OFFSET ?",
                (run, offset),
            )
        ]
    for item in items:
        item["findings"] = json.loads(item["findings"])
    return {**result, **dict(summary), "items": items}


def csv_report(run):
    yield "\ufeff"
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(
        [
            "Артикул WB",
            "Артикул продавца",
            "Название",
            "Индекс заметности",
            "Проверка обложки",
            "Поле",
            "Фрагмент",
            "Замечание",
            "Действие",
        ]
    )
    yield stream.getvalue()
    last = 0
    while True:
        with db.connect() as con:
            rows = con.execute(
                "SELECT * FROM wb_cards WHERE audit=? AND nm>? ORDER BY nm LIMIT 250", (run, last)
            ).fetchall()
        if not rows:
            return
        stream.seek(0)
        stream.truncate()
        for r in rows:
            for item in json.loads(r["findings"]) or [{}]:
                values = [
                    r["nm"],
                    r["sku"],
                    r["title"],
                    r["score"],
                    r["image_status"] or "Ожидает проверки",
                    *(item.get(k, "") for k in ("field", "match", "reason", "action")),
                ]
                writer.writerow(
                    [
                        "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
                        for v in values
                    ]
                )
        yield stream.getvalue()
        last = rows[-1]["nm"]


@router.get("/wb/audits/{run}/export")
def export(run: int, user: accounts.User = Depends(require_user)):
    with db.connect() as con:
        row = owned(con, run, user.id)
    if row["status"] in ("import", "photos"):
        raise api_error(409, "busy", "Дождитесь завершения проверки")
    return StreamingResponse(
        csv_report(run),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=wb-audit-{run}.csv"},
    )


@router.post("/wb/audits/{run}/cancel")
def cancel(run: int, user: accounts.User = Depends(require_user)):
    with db.connect() as con:
        owned(con, run, user.id)
        con.execute(
            "UPDATE wb_audits SET status='cancelled',token=NULL,message='Остановлено пользователем'"
            " WHERE id=? AND status IN ('import','photos')",
            (run,),
        )
        credits.finish_in(con, f"wb-{run}", False)
    return {"ok": True}
