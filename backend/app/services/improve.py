"""Улучшенная обложка: модель генерации картинок перерисовывает обложку по выводам разбора.

Исходная обложка уходит в /images/edits ProxyAPI вместе с инструкцией: доработать, сохранив стиль — фон, сцену,
цвета, настроение, товар, бренд и надписи остаются, улучшаются товар (крупнее, отделён от фона), вёрстка
надписей, углы под интерфейс WB и чистота. Плюс что мешает по выводам метрик и экспертов. Полный редизайн
(«новый дизайн, не копию») пробовали 14.10.2026 — модель выбрасывала фон и атмосферу, обложки становились хуже.
Ответ 2:3 доводится до карточки 3:4 полями по бокам.
"""

from __future__ import annotations

import base64
import io
import logging

import httpx
from PIL import Image, ImageFilter

from .. import config
from . import aicost, expert

log = logging.getLogger(__name__)

TIMEOUT_S = 240  # генерация занимает 30–60 с, с запасом на очередь у провайдера
SIZE = "1024x1536"  # вертикаль 2:3 — ближе всего к карточке 3:4 из доступных размеров
COVER_RATIO = 3 / 4  # карточки WB и Ozon — 3:4; результат 2:3 доводим до него полями по бокам

PROMPT = """Ты — ретушёр и верстальщик карточек Wildberries и Ozon. Доработай эту обложку, сохранив её стиль.
Это доработка, а не новый дизайн: покупатель должен узнать ту же обложку, только аккуратнее и дороже.

Сохрани как есть: фон и сцену, цветовую гамму, освещение и настроение, сам товар (форма, цвет, детали),
логотип и бренд, смысл и факты всех главных надписей. Не добавляй новых свойств, цифр, цен и обещаний.
Замечания ниже — советы по оформлению, они не подтверждают свойства товара.

Улучши:
1. Товар — немного крупнее (на 10–20%), резче, с аккуратным контровым светом, чтобы чётко отделялся от фона.
2. Надписи — ясная иерархия: главный заголовок самый крупный, преимущества ровной колонкой с одинаковыми
   отступами, единый шрифт, ровное выравнивание. Мелкие второстепенные надписи можно убрать.
3. Если важная надпись стоит в левом нижнем углу (там WB ставит плашку скидки) или в правом верхнем
   (сердечко) — сдвинь её ближе к центру, сохранив стиль.
4. Чистота и качество: резкость, без артефактов и грязи, премиальный вид.

Что ещё мешает по анализу:
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
    """Доводит вертикаль 2:3 до карточки 3:4, ничего не обрезая: по бокам дорисовываем размытое продолжение
    краёв фона. Обрезка по высоте срезала бы заголовок — модель часто ставит его у самого края."""
    w, h = img.size
    want_w = round(h * COVER_RATIO)
    if w >= want_w:
        return img
    pad = want_w - w
    left, right = pad // 2, pad - pad // 2
    canvas = Image.new("RGB", (want_w, h))
    edge = max(8, w // 32)  # полоса края, которую растягиваем в поле
    for x, size, box in ((0, left, (0, 0, edge, h)), (left + w, right, (w - edge, 0, w, h))):
        if size:
            strip = img.crop(box).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((size, h))
            canvas.paste(strip.filter(ImageFilter.GaussianBlur(max(4, size // 3))), (x, 0))
    canvas.paste(img, (left, 0))
    return canvas
