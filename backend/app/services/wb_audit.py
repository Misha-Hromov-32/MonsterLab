"""Возобновляемая проверка каталога. Курсор и страница результатов фиксируются одной транзакцией."""

import asyncio
import base64
import json
import logging
import os
import re
import sqlite3
import time
from urllib.parse import urlsplit

import httpx
import numpy as np

from ..core import metrics, saliency
from ..core.imaging import BadImage, open_image, resize_long
from ..errors import api_error
from . import accounts, credits, crypto, db
from .card_rules import check, finding, inspect_cover, read_cover

log = logging.getLogger(__name__)
CARDS_URL = "https://content-api.wildberries.ru/content/v2/get/cards/list"
PAGE_SIZE = 100
IMPORT = "import"
PHOTOS = "photos"


def start(owner: int, token: str) -> int:
    try:
        if not re.fullmatch(r"[\w-]+\.[\w-]+\.[\w-]+", token, re.ASCII):
            raise ValueError
        claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
        if (
            not isinstance(claims, dict)
            or claims.get("acc") not in (1, 4)
            or (claims.get("acc") == 1 and claims.get("for") is not None)
            or claims.get("t")
            or claims.get("exp", 0) <= time.time()
        ):
            raise ValueError
        mask = claims.get("s", 0)
        if not mask & 2 or not mask & (1 << 30):
            raise ValueError
    except (ValueError, TypeError, UnicodeError) as exc:
        raise api_error(
            422, "wb_token", "Нужен действующий базовый или сервисный токен WB с доступом «Контент», только чтение."
        ) from exc
    if claims["acc"] == 4 and (
        not os.getenv("WB_CLIENT_SECRET") or claims.get("for") != "asid:" + os.getenv("WB_SERVICE_ID", "")
    ):
        raise api_error(422, "wb_service", "Сервисный токен должен быть выпущен для подключённого сервиса MonStoreLab.")
    user = accounts.get(owner)
    if user is None:
        raise api_error(401, "login_required", "Войдите для проверки каталога")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            run = con.execute(
                "INSERT INTO wb_audits(owner,token,status,created) VALUES(?,?,?,?)",
                (owner, crypto.encrypt(token.encode(), f"wb/{owner}"), IMPORT, time.time()),
            ).lastrowid
            credits.reserve_in(con, user, "wb", credits.COST["wb"], f"wb-{run}", persistent=True)
            return run
        except sqlite3.IntegrityError as exc:
            raise api_error(409, "in_progress", "Проверка каталога уже идёт") from exc


def set_error(run: int, message: str) -> None:
    with db.connect() as con:
        con.execute(
            "UPDATE wb_audits SET status='error',token=NULL,message=? WHERE id=? AND status IN ('import','photos')",
            (message, run),
        )
        credits.finish_in(con, f"wb-{run}", False)


def card_record(run: int, card: dict):
    nm = int(card["nmID"])
    title = card.get("title") or ""
    description = card.get("description") or ""
    issues = check("wb", Название=title, Описание=description)
    photo_list = card.get("photos") or []
    for field, value in (("Название", title), ("Описание", description), ("Фотографии", photo_list)):
        if not value:
            issues.append(finding(field, "", "Поле не заполнено", f"Заполните поле «{field}».", "missing"))
    photo = photo_list[0] if photo_list else {}
    url = photo.get("big") or photo.get("c516x688") or ""
    return (
        run,
        nm,
        card.get("vendorCode") or "",
        title,
        url,
        json.dumps(issues, ensure_ascii=False),
        int(not url),
        "" if url else "Нет доступной обложки",
    )


def import_page(run, client):
    cursor = json.loads(run["cursor"])
    headers = {
        "Authorization": crypto.decrypt(run["token"], f"wb/{run['owner']}").decode(),
        "User-Agent": "MonStoreLab/1.0",
    }
    if secret := os.getenv("WB_CLIENT_SECRET"):
        headers["X-Client-Secret"] = secret
    response = client.post(
        CARDS_URL,
        headers=headers,
        json={"settings": {"cursor": {**cursor, "limit": PAGE_SIZE}, "filter": {"withPhoto": 0}}},
    )
    response.raise_for_status()
    data = response.json()
    cards, returned = data["cards"], data["cursor"]
    if not isinstance(cards, list) or not isinstance(returned, dict) or int(returned["total"]) != len(cards):
        raise ValueError("Неполный ответ WB")
    more = len(cards) >= PAGE_SIZE
    following = {"nmID": int(returned["nmID"]), "updatedAt": returned["updatedAt"]} if more else {}
    if more and (not following["updatedAt"] or following == cursor):
        raise ValueError("Курсор WB не изменился")
    rows = [card_record(run["id"], c) for c in cards]
    with db.connect() as con:
        changed = con.execute(
            "UPDATE wb_audits SET status=?,cursor=?,failures=0,message='',next_at=?,"
            "token=CASE WHEN ? THEN token ELSE NULL END WHERE id=? AND status='import'",
            (IMPORT if more else PHOTOS, json.dumps(following), time.time() + 1, more, run["id"]),
        ).rowcount
        if changed:
            con.executemany(
                "INSERT OR IGNORE INTO wb_cards(audit,nm,sku,title,photo,findings,checked,image_status)"
                " VALUES(?,?,?,?,?,?,?,?)",
                rows,
            )


def image_bytes(client, url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.port not in (None, 443)
        or not host.endswith((".wbbasket.ru", ".wbcontent.net", ".wb.ru"))
    ):
        raise ValueError
    with client.stream("GET", url) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes(65536):
            data.extend(chunk)
            if len(data) > 12_000_000:
                raise ValueError
        return bytes(data)


def analyze_next(run, client):
    with db.connect() as con:
        row = con.execute(
            "SELECT * FROM wb_cards WHERE audit=? AND checked=0 ORDER BY nm LIMIT 1", (run["id"],)
        ).fetchone()
        if not row:
            changed = con.execute(
                "UPDATE wb_audits SET status='done',message='' WHERE id=? AND status='photos'", (run["id"],)
            ).rowcount
            if changed:
                credits.finish_in(con, f"wb-{run['id']}", True)
            return
    findings = json.loads(row["findings"])
    score = None
    try:
        data = image_bytes(client, row["photo"])
        image = open_image(data, 1600)
        rgb = resize_long(np.asarray(image), 640)
        visual = metrics.analyze(rgb, saliency.classic_density(rgb))
        score = visual["index"]
        findings.extend(
            finding("Дизайн", "", note["title"], note["text"], "design")
            for note in visual["notes"]
            if note["level"] != "good"
        )
        findings.extend(inspect_cover("wb", image, len(data)))
        text, status = read_cover(image)
        findings.extend(check("wb", Обложка=text))
    except (httpx.HTTPError, ValueError, BadImage):
        status = "Не удалось проверить изображение. Откройте фото вручную."
    with db.connect() as con:
        con.execute(
            "UPDATE wb_cards SET findings=?,checked=1,image_status=?,score=? WHERE audit=? AND nm=?"
            " AND EXISTS (SELECT 1 FROM wb_audits WHERE id=? AND status='photos')",
            (json.dumps(findings, ensure_ascii=False), status, score, run["id"], row["nm"], run["id"]),
        )
        con.execute("UPDATE wb_audits SET next_at=? WHERE id=?", (time.time(), run["id"]))


def step(client) -> bool:
    with db.connect() as con:
        run = con.execute(
            "SELECT * FROM wb_audits WHERE status IN ('import','photos') AND next_at<=? ORDER BY next_at,id LIMIT 1",
            (time.time(),),
        ).fetchone()
    if not run:
        return False
    try:
        if run["status"] == IMPORT:
            import_page(run, client)
        else:
            analyze_next(run, client)
    except httpx.HTTPError as exc:
        response = getattr(exc, "response", None)
        status = response.status_code if response is not None else 0
        if status in (401, 402, 403):
            set_error(
                run["id"], "WB отклонил доступ. Проверьте токен, права категории «Контент» и условия доступа WB API."
            )
        elif (not status or status == 429 or status >= 500) and run["failures"] < 8:
            delay = min(300, 2 ** (run["failures"] + 1))
            if response is not None:
                for name in ("Retry-After", "X-Ratelimit-Retry"):
                    value = response.headers.get(name, "")
                    if value.isdigit():
                        delay = max(delay, int(value))
            with db.connect() as con:
                con.execute(
                    "UPDATE wb_audits SET next_at=?,failures=failures+1,message=? WHERE id=?",
                    (time.time() + delay, "Ожидаем повторного запроса к WB", run["id"]),
                )
        else:
            set_error(run["id"], "WB не вернул каталог. Сохранена уже полученная часть отчёта.")
    except (ValueError, KeyError, TypeError, crypto.CryptoError):
        set_error(run["id"], "Не удалось прочитать ответ WB. Отчёт неполный.")
    return True


async def worker():
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        while True:
            try:
                active = await asyncio.to_thread(step, client)
            except Exception:
                log.exception("Ошибка обработки очереди каталогов")
                active = False
            await asyncio.sleep(0.1 if active else 3)
