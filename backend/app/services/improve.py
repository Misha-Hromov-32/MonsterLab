"""Улучшенная обложка: модель генерации картинок перерисовывает обложку по выводам разбора.

Исходная обложка уходит в /images/edits ProxyAPI вместе с инструкцией: сделать новый, более сильный дизайн
(крупный товар, меньше и крупнее текст, свободные углы под интерфейс WB), что мешает по выводам метрик и
экспертов и чего нельзя трогать (товар, бренд, факты в надписях). Ответ 2:3 обрезается до карточки 3:4.
"""

from __future__ import annotations

import base64
import io
import logging

import httpx
import numpy as np
from PIL import Image

from .. import config
from . import aicost, expert

log = logging.getLogger(__name__)

TIMEOUT_S = 240  # генерация занимает 30–60 с, с запасом на очередь у провайдера
SIZE = "1024x1536"  # вертикаль 2:3 — ближе всего к карточке 3:4 из доступных размеров
COVER_RATIO = 3 / 4  # карточки WB и Ozon — 3:4; результат 2:3 обрезаем до него

PROMPT = """Ты — сильный дизайнер карточек Wildberries и Ozon. Перед тобой обложка товара. Сделай НОВЫЙ,
заметно более сильный вариант дизайна этой обложки — не копию.

Можно и нужно менять: композицию, фон, размер и расположение товара, размер, стиль и расположение надписей,
цвета. Нельзя менять: сам товар (форма, цвет, детали) и факты в надписях. Логотип или название бренда сохрани.
Не придумывай новых свойств, цифр, сертификатов, цен и обещаний — бери только надписи с исходной обложки.
Замечания ниже — советы по оформлению, они не подтверждают свойства товара.

Обязательно:
1. Товар крупный и главный: 60–70% высоты кадра, резко отделён от фона светом и контрастом.
2. Текста меньше и он крупнее: название, не больше двух преимуществ и объём или размер, если они есть.
   Остальные надписи убери. Шрифт — такой, чтобы читался в превью шириной 170 пикселей.
3. Углы свободны — их закрывает интерфейс маркетплейса: левый верхний (бейджи), правый верхний (сердечко),
   левый нижний — около 40% ширины и 20% высоты (скидка и промо), правый нижний (корзина).
   В этих углах только фон: ни текста, ни товара.
4. Один акцентный цвет для главного, спокойный фон без мелких деталей.
5. Верхние и нижние 6% кадра будут обрезаны до формата 3:4 — ничего важного у краёв.

Что мешает на исходной обложке:
{problems}

Весь текст — на русском, без ошибок.{context}"""


class ImproveError(RuntimeError):
    """Понятная пользователю причина сбоя генерации."""


def build_prompt(notes: list[dict], issues: list[str], ctx: dict) -> str:
    lines = [f"— {n['title']}: {n['text']}" for n in notes if n.get("level") in ("bad", "warn")]
    lines += [f"— {i}" for i in issues]
    problems = "\n".join(lines[:8]) or "— сделай обложку заметнее и понятнее в маленьком превью"
    extra = []
    if ctx.get("query"):
        extra.append(f"Покупатель ищет: «{ctx['query']}».")
    if ctx.get("category"):
        extra.append(f"Категория: {ctx['category']}.")
    return PROMPT.format(problems=problems, context=("\n" + " ".join(extra)) if extra else "")


def generate(jpeg: bytes, prompt: str) -> bytes:
    """Возвращает улучшенную обложку в JPEG."""
    cfg = expert.current_config()
    if not cfg.enabled:
        raise ImproveError("Генерация не подключена")
    try:
        with httpx.Client(base_url=cfg.base_url, timeout=httpx.Timeout(TIMEOUT_S, connect=15)) as client:
            r = client.post(
                "/images/edits",
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                data={"model": config.IMAGE_MODEL, "prompt": prompt, "size": SIZE, "quality": config.IMAGE_QUALITY},
                files={"image": ("cover.jpg", jpeg, "image/jpeg")},
            )
    except httpx.HTTPError as exc:
        log.warning("Генерация обложки: сеть — %s", exc)
        raise ImproveError("Сервис генерации недоступен, попробуйте через минуту") from exc
    aicost.record(config.IMAGE_MODEL, expert._usage(r), r.status_code < 400)
    if r.status_code >= 400:
        log.warning("Генерация обложки: %s %s", r.status_code, r.text[:300])
        raise ImproveError("Не удалось сгенерировать обложку, попробуйте ещё раз")
    try:
        png = base64.b64decode(r.json()["data"][0]["b64_json"])
        img = Image.open(io.BytesIO(png)).convert("RGB")
    except (KeyError, IndexError, ValueError, OSError) as exc:
        raise ImproveError("Модель вернула пустой ответ, попробуйте ещё раз") from exc
    out = io.BytesIO()
    to_cover_ratio(img).save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def to_cover_ratio(img: Image.Image) -> Image.Image:
    """Обрезает вертикаль 2:3 до 3:4. Срезаем сверху и снизу там, где меньше всего деталей (перепадов яркости
    между строками): у краёв обычно фон, а надписи и товар остаются целыми."""
    w, h = img.size
    want = round(w / COVER_RATIO)
    if h <= want:
        return img
    cut = h - want
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    detail = np.concatenate([np.abs(np.diff(gray, axis=0)).sum(axis=1), [0.0]])
    acc = np.concatenate([[0.0], np.cumsum(detail)])
    # сверху срезаем top строк, снизу — cut - top; ищем, где потеряем меньше всего деталей
    top = min(range(cut + 1), key=lambda t: acc[t] + acc[h] - acc[h - (cut - t)])
    return img.crop((0, top, w, top + want))
