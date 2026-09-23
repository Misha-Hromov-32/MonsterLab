"""Админ-панель: вход по паролю, тексты главной, примеры, экспертный разбор."""

from __future__ import annotations

import asyncio
from pathlib import PurePath
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from .. import config
from ..core.imaging import BadImage
from ..errors import api_error
from ..ratelimit import client_ip, login_limit
from ..schemas import ProductContext
from ..services import auth, expert, site
from .deps import read_upload, require_admin

router = APIRouter(prefix="/api/admin")
guarded = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


def _get_example(data: dict, example_id: str) -> dict:
    ex = site.find_example(data, example_id)
    if ex is None:
        raise api_error(404, "not_found", "Пример не найден")
    return ex


def _check_role(role: str) -> None:
    if role not in site.ROLES:
        raise api_error(422, "bad_role", "Неизвестный тип картинок: нужны варианты или конкуренты")


# ---------------------------------------------------------------- вход


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> dict:
    ip = client_ip(request)
    login_limit.check(ip)  # засчитываем только неудачные попытки
    if not auth.check_password(body.password):
        login_limit.hit(ip)
        await asyncio.sleep(0.8)  # притормаживаем перебор
        raise api_error(401, "bad_password", "Неверный пароль")
    return {"token": auth.make_token()}


# ---------------------------------------------------------------- настройки


def _expert_out() -> dict:
    """Настройки разбора без самого ключа — только подсказка, чей он и чем заканчивается."""
    saved = site.read()["expert"]
    cfg = expert.current_config()
    key = cfg.api_key
    return {
        "has_key": bool(key),
        "key_hint": f"••••{key[-4:]}" if len(key) >= 8 else ("задан" if key else ""),
        "key_source": "admin" if saved.get("api_key") else ("env" if key else ""),
        "base_url": cfg.base_url,
        "models": cfg.models,
    }


@guarded.get("/settings")
def get_settings() -> dict:
    data = site.read()
    return {
        "landing": data["landing"],
        "examples": [site.example_out(e) for e in data["examples"]],
        "expert": _expert_out(),
        "designs": list(site.DESIGNS),
    }


class Step(BaseModel):
    title: str = Field(max_length=80)
    text: str = Field(max_length=400)


class Landing(BaseModel):
    design: str
    eyebrow: str = Field("", max_length=80)
    title: str = Field(max_length=120)
    title_muted: str = Field("", max_length=160)
    lead: str = Field("", max_length=600)
    cta: str = Field("Загрузить обложки", max_length=40)
    steps: list[Step] = Field(min_length=3, max_length=3)


@guarded.put("/landing")
def put_landing(body: Landing) -> dict:
    if body.design not in site.DESIGNS:
        raise api_error(422, "bad_design", "Неизвестный вариант дизайна")
    site.update(lambda d: d.__setitem__("landing", body.model_dump()))
    return {"ok": True}


class ExpertSettings(BaseModel):
    api_key: str | None = Field(None, max_length=300)  # None — не менять, "" — удалить
    base_url: str = Field("", max_length=300)
    models: list[str] = Field(default_factory=list, max_length=config.MAX_EXPERT_MODELS)


@guarded.put("/expert")
def put_expert(body: ExpertSettings) -> dict:
    base_url = body.base_url.strip()
    if base_url and (urlparse(base_url).scheme != "https" or not urlparse(base_url).netloc):
        raise api_error(422, "bad_url", "Адрес API должен начинаться с https://")

    def apply(d: dict) -> None:
        saved = d["expert"]
        if body.api_key is not None:
            saved["api_key"] = body.api_key.strip()
        saved["base_url"] = base_url
        saved["models"] = [m.strip() for m in body.models if m.strip()]

    site.update(apply)
    return _expert_out()


@guarded.post("/expert/check")
async def check_expert() -> dict:
    try:
        return {"results": await expert.check()}
    except expert.ExpertError as exc:
        raise api_error(400, "no_key", str(exc)) from exc


# ---------------------------------------------------------------- примеры


class ExampleIn(BaseModel):
    title: str = Field(max_length=80)
    description: str = Field("", max_length=300)
    context: ProductContext = Field(default_factory=ProductContext)
    published: bool = True
    hero: str | None = Field(None, max_length=32)  # вариант, который показываем на главной


@guarded.post("/examples")
def create_example(body: ExampleIn) -> dict:
    # у нового примера ещё нет вариантов — выбирать обложку для главной не из чего
    ex = {"id": site.new_id(), **body.model_dump(), "hero": None, "variants": [], "competitors": []}
    site.update(lambda d: d["examples"].append(ex))
    return site.example_out(ex)


@guarded.put("/examples/{example_id}")
def update_example(example_id: str, body: ExampleIn) -> dict:
    def apply(d: dict) -> None:
        ex = _get_example(d, example_id)
        if body.hero and all(v["id"] != body.hero for v in ex["variants"]):
            raise api_error(422, "bad_hero", "Для главной можно выбрать только вариант этого примера")
        ex.update(body.model_dump())

    return site.example_out(_get_example(site.update(apply), example_id))


@guarded.delete("/examples/{example_id}")
def delete_example(example_id: str) -> dict:
    def apply(d: dict) -> None:
        _get_example(d, example_id)
        d["examples"] = [e for e in d["examples"] if e["id"] != example_id]

    site.update(apply)
    site.delete_example_files(example_id)
    return {"ok": True}


class Order(BaseModel):
    ids: list[str] = Field(max_length=500)


@guarded.put("/examples-order")
def order_examples(body: Order) -> dict:
    def apply(d: dict) -> None:
        pos = {i: n for n, i in enumerate(body.ids)}
        d["examples"].sort(key=lambda e: pos.get(e["id"], len(pos)))

    site.update(apply)
    return {"ok": True}


@guarded.post("/examples/{example_id}/images")
async def add_images(example_id: str, role: str = Form(...), files: list[UploadFile] = File(...)) -> dict:
    _check_role(role)
    limit = site.ROLES[role]
    current = await asyncio.to_thread(site.read)
    room = limit - len(_get_example(current, example_id)[role])
    if room <= 0:
        noun = "варианта" if role == "variants" else "конкурентов"  # «4 варианта», «12 конкурентов»
        raise api_error(422, "limit", f"Максимум {limit} {noun}")

    added: list[dict] = []
    kept: list[dict] = []  # что реально попало в настройки; всё остальное из added — удалить с диска
    try:
        for f in files[:room]:
            content = await read_upload(f)
            try:
                meta = await asyncio.to_thread(site.store_image, example_id, content)
            except BadImage as exc:
                raise api_error(422, "bad_image", f"Не удалось прочитать {f.filename}") from exc
            title = PurePath(f.filename or "").stem[:60] if role == "variants" else ""
            added.append({**meta, "title": title})

        def apply(d: dict) -> None:
            images = _get_example(d, example_id)[role]
            fit = max(0, limit - len(images))  # пока шла загрузка, могли добавить картинки из другой вкладки
            images.extend(added[:fit])

        data = await asyncio.to_thread(site.update, apply)
        kept = [i for i in _get_example(data, example_id)[role] if i in added]
    finally:
        for meta in added:
            if meta not in kept:
                await asyncio.to_thread(site.delete_image_file, example_id, meta["id"])
    # файлы сверх лимита не сохраняются — говорим админке, сколько пропущено
    return {**site.example_out(_get_example(data, example_id)), "skipped": len(files) - len(kept)}


class ImagePatch(BaseModel):
    title: str = Field("", max_length=60)


def _image_list(ex: dict, image_id: str) -> list[dict]:
    for role in site.ROLES:
        if any(i["id"] == image_id for i in ex[role]):
            return ex[role]
    raise api_error(404, "not_found", "Картинка не найдена")


@guarded.patch("/examples/{example_id}/images/{image_id}")
def patch_image(example_id: str, image_id: str, body: ImagePatch) -> dict:
    def apply(d: dict) -> None:
        for img in _image_list(_get_example(d, example_id), image_id):
            if img["id"] == image_id:
                img["title"] = body.title.strip()

    return site.example_out(_get_example(site.update(apply), example_id))


@guarded.delete("/examples/{example_id}/images/{image_id}")
def delete_image(example_id: str, image_id: str) -> dict:
    def apply(d: dict) -> None:
        ex = _get_example(d, example_id)
        images = _image_list(ex, image_id)
        images[:] = [i for i in images if i["id"] != image_id]
        if ex.get("hero") == image_id:
            ex["hero"] = None

    data = site.update(apply)
    site.delete_image_file(example_id, image_id)
    return site.example_out(_get_example(data, example_id))


class ImagesOrder(BaseModel):
    role: str
    ids: list[str] = Field(max_length=50)


@guarded.put("/examples/{example_id}/images-order")
def order_images(example_id: str, body: ImagesOrder) -> dict:
    _check_role(body.role)

    def apply(d: dict) -> None:
        pos = {i: n for n, i in enumerate(body.ids)}
        _get_example(d, example_id)[body.role].sort(key=lambda i: pos.get(i["id"], len(pos)))

    return site.example_out(_get_example(site.update(apply), example_id))
