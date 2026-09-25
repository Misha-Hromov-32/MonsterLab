"""Улучшенная обложка: модель генерации картинок перерисовывает обложку по выводам разбора.

Исходная обложка уходит в /images/edits ProxyAPI вместе с инструкцией: что мешает (выводы
метрик и, если есть, замечания экспертов) и чего нельзя трогать (товар, бренд, смысл текстов).
"""

from __future__ import annotations

import base64
import io
import logging

import httpx
from PIL import Image

from .. import config
from . import expert

log = logging.getLogger(__name__)

TIMEOUT_S = 240  # генерация занимает 30–60 с, с запасом на очередь у провайдера
SIZE = "1024x1536"  # вертикаль 2:3 — ближе всего к карточке 3:4 из доступных размеров

PROMPT = """Улучши эту обложку карточки товара для маркетплейса (Wildberries, Ozon).
Покупатель видит её в выдаче на телефоне шириной около 170 пикселей и решает за секунду.

Сохрани без изменений: сам товар (форму, цвет, детали), бренд и смысл надписей.
Исправь то, что мешает:
{problems}

Требования: один крупный главный оффер, не больше трёх крупных преимуществ, чистая композиция,
товар хорошо отделён от фона. Весь текст — на русском, без ошибок, крупно и читаемо.
Вертикальный формат, товар — главный объект.{context}"""


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
                data={"model": config.IMAGE_MODEL, "prompt": prompt, "size": SIZE},
                files={"image": ("cover.jpg", jpeg, "image/jpeg")},
            )
    except httpx.HTTPError as exc:
        log.warning("Генерация обложки: сеть — %s", exc)
        raise ImproveError("Сервис генерации недоступен, попробуйте через минуту") from exc
    if r.status_code >= 400:
        log.warning("Генерация обложки: %s %s", r.status_code, r.text[:300])
        raise ImproveError("Не удалось сгенерировать обложку, попробуйте ещё раз")
    try:
        png = base64.b64decode(r.json()["data"][0]["b64_json"])
        img = Image.open(io.BytesIO(png)).convert("RGB")
    except (KeyError, IndexError, ValueError, OSError) as exc:
        raise ImproveError("Модель вернула пустой ответ, попробуйте ещё раз") from exc
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()
