"""Всё, что правится из админ-панели: тексты главной, примеры, настройки экспертного разбора.

Хранится в DATA_DIR: settings.json + картинки примеров в examples/<example_id>/<image_id>.jpg.
Запись атомарная (через временный файл), чтение — из кэша в памяти.
"""

from __future__ import annotations

import copy
import json
import logging
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from .. import config
from ..core.imaging import open_image

log = logging.getLogger(__name__)

SETTINGS_FILE = config.DATA_DIR / "settings.json"
EXAMPLES_DIR = config.DATA_DIR / "examples"
EXAMPLE_MAX_SIDE = 1600

DESIGNS = ("editorial", "split", "feed")
ROLES = {"variants": config.MAX_VARIANTS, "competitors": config.MAX_COMPETITORS}

DEFAULTS: dict = {
    "landing": {
        "design": "split",
        "eyebrow": "Предиктивный тест обложек",
        "title": "Куда посмотрит покупатель —",
        "title_muted": "до того, как карточка выйдет в выдачу.",
        "lead": "Загрузите от одной до четырёх обложек. Покажем, куда упадёт взгляд в первые секунды, "
        "что потеряется в маленькой карточке в ленте и какой вариант заметнее среди конкурентов.",
        "cta": "Загрузить обложки",
        "steps": [
            {
                "title": "Карта внимания",
                "text": "Прогноз построен на записях реального движения глаз. Тепловая карта, туман, изолинии "
                "и порядок, в котором покупатель рассматривает обложку.",
            },
            {
                "title": "Понятные метрики",
                "text": "«Половина внимания — на 9% площади», сколько взгляда получают товар и оффер "
                "и читается ли текст в ленте телефона.",
            },
            {
                "title": "Полка среди конкурентов",
                "text": "Вариант ставится в выдачу рядом с конкурентами на разные позиции — сразу видно, "
                "заметят его или он сольётся с остальными.",
            },
        ],
    },
    "examples": [],
    "expert": {"api_key": "", "base_url": "", "models": []},
    "seeded": {},  # {slug встроенного примера: ревизия}
}

_lock = threading.RLock()
_cache: dict | None = None


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _read_file() -> dict | None:
    """Содержимое settings.json; None — файла нет. Битый файл откладываем в сторону, а не падаем."""
    if not SETTINGS_FILE.exists():
        return None
    try:
        raw = json.loads(SETTINGS_FILE.read_text("utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("корень должен быть объектом")
        return raw
    except ValueError as exc:
        backup = SETTINGS_FILE.with_name(f"settings.broken-{int(time.time())}.json")
        SETTINGS_FILE.replace(backup)
        log.error("settings.json повреждён (%s), сохранён как %s — начинаю с настроек по умолчанию", exc, backup.name)
        return None


def read() -> dict:
    """Текущие настройки без копирования — только для чтения. Менять — через update()."""
    return _cache if _cache is not None else _init()


def _init() -> dict:
    load()
    assert _cache is not None
    return _cache


def load() -> dict:
    """Копия текущих настроек. Первый вызов создаёт файл и раскладывает встроенные примеры."""
    global _cache
    with _lock:
        if _cache is None:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            raw = _read_file()
            data = _merge(DEFAULTS, raw or {})
            if _seed(data) or raw is None:
                _write(data)
            _cache = data
        return copy.deepcopy(_cache)


def _write(data: dict) -> None:
    """Сохраняет на диск и подменяет кэш целиком: читатели read() видят либо старую, либо новую версию."""
    global _cache
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(SETTINGS_FILE)
    _cache = data


def update(fn: Callable[[dict], None]) -> dict:
    """Атомарно меняет настройки: fn(data) правит копию на месте; исключение — ничего не сохраняется.
    Возвращает новую версию — только для чтения."""
    with _lock:
        data = load()
        fn(data)
        _write(data)
        return data


def find_example(data: dict, example_id: str) -> dict | None:
    return next((e for e in data["examples"] if e["id"] == example_id), None)


def published_examples() -> list[dict]:
    return [e for e in read()["examples"] if e.get("published") and e["variants"]]


def example_out(ex: dict) -> dict:
    """Пример для API: картинки сразу с адресами — админке и публичной части одинаково."""

    def img(i: dict) -> dict:
        return {**i, "url": image_url(ex["id"], i["id"])}

    return {**ex, "variants": [img(i) for i in ex["variants"]], "competitors": [img(i) for i in ex["competitors"]]}


# ---------------------------------------------------------------- картинки примеров


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def store_image(example_id: str, data: bytes) -> dict:
    """Нормализует картинку (EXIF, прозрачность, размер) и сохраняет как JPEG. BadImage — не картинка."""
    img = open_image(data, EXAMPLE_MAX_SIDE)
    image_id = new_id()
    folder = EXAMPLES_DIR / example_id
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{image_id}.jpg", quality=88, optimize=True)
    return {"id": image_id, "width": img.width, "height": img.height}


def image_path(example_id: str, image_id: str) -> Path:
    return EXAMPLES_DIR / example_id / f"{image_id}.jpg"


def image_url(example_id: str, image_id: str) -> str:
    return f"/api/public/files/{example_id}/{image_id}.jpg"


def delete_image_file(example_id: str, image_id: str) -> None:
    image_path(example_id, image_id).unlink(missing_ok=True)


def delete_example_files(example_id: str) -> None:
    shutil.rmtree(EXAMPLES_DIR / example_id, ignore_errors=True)


# ---------------------------------------------------------------- встроенные примеры


def _seed(data: dict) -> bool:
    """Раскладывает примеры из backend/seed. data["seeded"] = {slug: ревизия}:

    - примера ещё нет — добавляем;
    - в сиде вышла новая ревизия — пример пересобирается целиком: картинки, название, описание
      и данные о товаре берутся из сида, правки этого примера в админке теряются;
    - пример удалён в админке — не возвращаем.
    """
    manifest_file = config.SEED_DIR / "manifest.json"
    if not manifest_file.exists():
        return False
    seeded: dict = data["seeded"]
    changed = False
    for item in json.loads(manifest_file.read_text("utf-8")):
        slug, rev = item["slug"], int(item.get("rev", 1))
        prev = seeded.get(slug)
        if prev is not None and prev >= rev:
            continue
        existing = next((e for e in data["examples"] if e.get("seed") == slug), None)
        seeded[slug] = rev
        changed = True
        if prev is not None and existing is None:
            continue  # удалён в админке — уважаем
        ex = existing or {"id": new_id(), "published": True}
        delete_example_files(ex["id"])
        ex.update({k: item[k] for k in ("title", "description", "context")})
        ex.update({"seed": slug, "hero": None, "variants": [], "competitors": []})
        for role in ROLES:
            for it in item[role]:
                meta = store_image(ex["id"], (config.SEED_DIR / it["file"]).read_bytes())
                ex[role].append({**meta, "title": it.get("title", "")})
        if existing is None:
            data["examples"].append(ex)
        log.info("Встроенный пример «%s» разложен (ревизия %s)", item["title"], rev)
    return changed
