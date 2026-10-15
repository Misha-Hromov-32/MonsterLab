"""Улучшенная обложка: модель генерации картинок перерисовывает обложку по выводам разбора.

Исходная обложка уходит в /images/edits ProxyAPI вместе с инструкцией: доработать, сохранив стиль — фон, сцену,
цвета, настроение, товар, бренд и надписи остаются, улучшаются товар (крупнее, отделён от фона), вёрстка
надписей, углы под интерфейс WB и чистота. Плюс что мешает по выводам метрик и экспертов. Полный редизайн
(«новый дизайн, не копию») пробовали 14.10.2026 — модель выбрасывала фон и атмосферу, обложки становились хуже.
Исходник дополняется полями до 2:3 (модель рисует только так), после генерации поля срезаются —
формат и масштаб обложки сохраняются, надписи не мельчают.
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
CANVAS_RATIO = 2 / 3  # SIZE: исходник дополняем полями до этих пропорций, после генерации поля срезаем

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
5. Сверху и снизу (или по бокам) обложка дополнена размытым продолжением фона — это служебные поля, их
   обрежут. Всё содержимое оставь на тех же местах и в том же масштабе, в поля ничего не переноси.

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
    """Возвращает улучшенную обложку в JPEG — в пропорциях исходной."""
    cfg = expert.current_config()
    if not cfg.enabled:
        raise ImproveError("Генерация не подключена")
    canvas, box = pad_to_ratio(Image.open(io.BytesIO(jpeg)).convert("RGB"), CANVAS_RATIO)
    src = io.BytesIO()
    canvas.save(src, format="JPEG", quality=92)
    try:
        with httpx.Client(base_url=cfg.base_url, timeout=httpx.Timeout(TIMEOUT_S, connect=15)) as client:
            r = client.post(
                "/images/edits",
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                data={"model": config.IMAGE_MODEL, "prompt": prompt, "size": SIZE, "quality": config.IMAGE_QUALITY},
                files={"image": ("cover.jpg", src.getvalue(), "image/jpeg")},
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
    w, h = img.size
    out = io.BytesIO()
    img.crop((round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h))).save(
        out, format="JPEG", quality=90, optimize=True
    )
    return out.getvalue()


def pad_to_ratio(img: Image.Image, ratio: float) -> tuple[Image.Image, tuple[float, float, float, float]]:
    """Дополняет картинку до пропорций ratio (ширина / высота) размытым продолжением краёв — сверху и снизу
    или по бокам. Возвращает холст и где на нём исходник (доли: left, top, right, bottom).

    Модель рисует только 2:3: если отдать ей обложку 3:4 как есть, она вписывает всё в высокий холст и
    содержимое мельчает. С полями масштаб и места надписей сохраняются, а поля потом срезаем."""
    w, h = img.size
    if abs(w / h - ratio) < 0.01:
        return img, (0.0, 0.0, 1.0, 1.0)
    vertical = w / h > ratio  # шире нужного — добавляем поля сверху и снизу
    cw, ch = (w, round(w / ratio)) if vertical else (round(h * ratio), h)
    canvas = Image.new("RGB", (cw, ch))
    x0, y0 = (cw - w) // 2, (ch - h) // 2
    if vertical:
        edge, flip = max(8, h // 32), Image.Transpose.FLIP_TOP_BOTTOM
        fields = ((0, 0, w, y0, (0, 0, w, edge)), (0, y0 + h, w, ch - y0 - h, (0, h - edge, w, h)))
    else:
        edge, flip = max(8, w // 32), Image.Transpose.FLIP_LEFT_RIGHT
        fields = ((0, 0, x0, h, (0, 0, edge, h)), (x0 + w, 0, cw - x0 - w, h, (w - edge, 0, w, h)))
    for fx, fy, fw, fh, strip in fields:
        if fw > 0 and fh > 0:
            field = img.crop(strip).transpose(flip).resize((fw, fh))
            canvas.paste(field.filter(ImageFilter.GaussianBlur(max(4, min(fw, fh) // 3))), (fx, fy))
    canvas.paste(img, (x0, y0))
    return canvas, (x0 / cw, y0 / ch, (x0 + w) / cw, (y0 + h) / ch)
