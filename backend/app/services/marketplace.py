"""Конкуренты из выдачи Wildberries: топ карточек по поисковому запросу — для теста полки.

Wildberries отдаёт поиск только настоящему браузеру (антибот-проверка с токеном, привязанным
к отпечатку браузера), поэтому страница выдачи открывается в headless Chromium (Playwright),
а список товаров берётся из ответа поиска, который загружает сама страница. Картинки товаров
лежат на открытом CDN (basket-NN.wbbasket.ru) — адреса берём из карточек на странице.

Браузер запускается по одному запросу за раз и сразу закрывается — ~200 МБ памяти на время
поиска. Результат кэшируется на COMPETITORS_CACHE_HOURS, картинки хранятся в DATA_DIR/competitors.

Ozon закрыт строже (антибот-страница и для headless-браузера) — пока только Wildberries.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import logging
import re
import time
from urllib.parse import quote

import httpx
from PIL import Image

from .. import config
from . import db

log = logging.getLogger(__name__)

FILES_DIR = config.DATA_DIR / "competitors"
SEARCH_URL = "https://www.wildberries.ru/catalog/0/search.aspx?search={query}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
IMAGE_SIDE = 720
_browser_lock = asyncio.Lock()  # один браузер за раз: на слабом сервере два Chromium не поместятся
_ID = re.compile(r"^\d{4,12}$")


class MarketplaceError(RuntimeError):
    """Понятная пользователю причина: выдача недоступна, ничего не нашлось."""


def available() -> bool:
    """Есть ли на сервере браузер для открытия выдачи (Playwright ставится с NEURAL-образом)."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def query_key(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]


def image_path(key: str, product_id: str):
    return FILES_DIR / key / f"{product_id}.jpg"


def _cached(query: str) -> list[dict] | None:
    with db.connect() as con:
        row = con.execute("SELECT payload, fetched_at FROM competitor_cache WHERE query = ?", (query,)).fetchone()
    if row is None or time.time() - row["fetched_at"] > config.COMPETITORS_CACHE_HOURS * 3600:
        return None
    items = json.loads(row["payload"])
    key = query_key(query)
    return items if all(image_path(key, i["id"]).exists() for i in items) else None


async def _open_search(query: str, want: int) -> list[dict]:
    """Открывает выдачу в браузере; возвращает [{id, brand, name, image}] в порядке выдачи."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # образ собран без браузера
        raise MarketplaceError("Подбор конкурентов не подключён на этом сервере") from exc

    found: dict = {}

    async def on_response(response) -> None:
        if not found and "/u-search/exactmatch/" in response.url and response.status == 200:
            # не JSON (обрыв, антибот-страница) — просто ждём следующий ответ поиска
            with contextlib.suppress(Exception):
                found["data"] = await response.json()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            executable_path=config.BROWSER_PATH,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = await browser.new_page(user_agent=USER_AGENT, locale="ru-RU")
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
            page.on("response", on_response)
            url = SEARCH_URL.format(query=quote(query))
            # первая загрузка часто уходит на антибот-проверку — после неё страница открывается сама
            for _ in range(3):
                await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                for _ in range(20):
                    if found:
                        break
                    await asyncio.sleep(0.5)
                if found:
                    break
            if not found:
                raise MarketplaceError("Wildberries не отдал выдачу, попробуйте позже")
            # карточки грузят картинки лениво — прокручиваем, пока не наберётся нужное число
            images: dict[str, str] = {}
            for _ in range(8):
                images = await page.evaluate(
                    """() => Object.fromEntries([...document.querySelectorAll('article[data-nm-id]')]
                        .map(a => [a.dataset.nmId, a.querySelector('img')?.currentSrc || a.querySelector('img')?.src])
                        .filter(([, src]) => src && src.includes('wbbasket')))"""
                )
                if len(images) >= want:
                    break
                await page.mouse.wheel(0, 1600)
                await asyncio.sleep(0.8)
        finally:
            await browser.close()

    data = found["data"]
    products = data.get("products") or data.get("data", {}).get("products") or []
    items = []
    for p in products:
        pid = str(p.get("id", ""))
        if pid in images and _ID.match(pid):
            items.append({"id": pid, "brand": p.get("brand", ""), "name": p.get("name", ""), "image": images[pid]})
    return items


async def _download(client: httpx.AsyncClient, key: str, item: dict) -> bool:
    # в выдаче маленькие превью — берём ту же картинку в размере карточки товара
    url = re.sub(r"/images/[^/]+/", "/images/c516x688/", item["image"])
    try:
        r = await client.get(url)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
    except (httpx.HTTPError, OSError):
        return False
    img.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
    path = image_path(key, item["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=88)
    return True


async def search(query: str, limit: int) -> list[dict]:
    """Топ выдачи Wildberries по запросу: [{id, brand, name}], картинки — в image_path()."""
    query = query.strip()
    if len(query) < 2:
        raise MarketplaceError("Введите поисковый запрос")
    cached = await asyncio.to_thread(_cached, query)
    if cached is not None:
        return cached[:limit]
    async with _browser_lock:
        cached = await asyncio.to_thread(_cached, query)  # пока ждали, мог найти соседний запрос
        if cached is not None:
            return cached[:limit]
        started = time.perf_counter()
        items = await _open_search(query, want=limit)
        key = query_key(query)
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=20) as client:
            ok = await asyncio.gather(*(_download(client, key, i) for i in items[: limit + 4]))
        items = [{k: i[k] for k in ("id", "brand", "name")} for i, good in zip(items, ok) if good]
        if not items:
            raise MarketplaceError("По этому запросу ничего не нашлось")
        log.info("Выдача WB «%s»: %s карточек за %.1f с", query, len(items), time.perf_counter() - started)

    def save() -> None:
        with db.connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO competitor_cache (query, payload, fetched_at) VALUES (?, ?, ?)",
                (query, json.dumps(items, ensure_ascii=False), time.time()),
            )

    await asyncio.to_thread(save)
    return items[:limit]
