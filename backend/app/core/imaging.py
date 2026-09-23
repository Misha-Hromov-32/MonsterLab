"""Загрузка, приведение и кодирование изображений."""

from __future__ import annotations

import base64
import io
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 2000  # больше для анализа не нужно, экономим память
MIN_SIDE = 32
MAX_PIXELS = 40_000_000  # защита от «бомб»: 40 Мп в памяти — это уже 120 МБ RGB
FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}  # MPO — JPEG с камер телефонов; как в интерфейсе
MAX_ASPECT = 8  # реальные обложки и баннеры не вытянутее 1:8; «иголки» вроде 32×2000 раздувают расчёт превью
# Pillow сам отказывает только выше 2 × MAX_IMAGE_PIXELS, а между порогами лишь предупреждает —
# поэтому свой порог проверяем явно в open_image, а предупреждение глушим
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("ignore", Image.DecompressionBombWarning)


class BadImage(ValueError):
    pass


def open_image(data: bytes, max_side: int = MAX_SIDE) -> Image.Image:
    """Байты файла -> RGB PIL. Учитывает EXIF-поворот, прозрачность кладёт на белый,
    длинную сторону ужимает до max_side ещё до полного декодирования (JPEG draft)."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in FORMATS:
            raise BadImage("Поддерживаются только JPG, PNG и WebP")
        if img.width * img.height > MAX_PIXELS:
            raise BadImage(f"Изображение слишком большое — до {MAX_PIXELS // 1_000_000} мегапикселей")
        if max(img.size) > MAX_ASPECT * min(img.size):
            raise BadImage(f"Слишком вытянутое изображение — стороны не больше 1 : {MAX_ASPECT}")
        img.draft("RGB", (max_side, max_side))  # JPEG декодируется сразу в уменьшенном масштабе
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    except BadImage:
        raise
    except Image.DecompressionBombError as exc:
        raise BadImage(f"Изображение слишком большое — до {MAX_PIXELS // 1_000_000} мегапикселей") from exc
    except Exception as exc:  # Pillow бросает десятки разных исключений
        raise BadImage("Не удалось прочитать изображение") from exc
    if img.mode in ("RGBA", "LA", "P", "PA"):
        rgba = img.convert("RGBA")
        img = Image.alpha_composite(Image.new("RGBA", rgba.size, (255, 255, 255, 255)), rgba)
    img = img.convert("RGB")
    if min(img.size) < MIN_SIDE:
        raise BadImage("Изображение слишком маленькое")
    return img


def decode(data: bytes) -> np.ndarray:
    """Байты файла -> RGB uint8 (H, W, 3)."""
    return np.asarray(open_image(data))


def resize_long(img: np.ndarray, long_side: int) -> np.ndarray:
    """Масштабирует так, чтобы длинная сторона стала long_side. Пропорции сохраняются."""
    h, w = img.shape[:2]
    k = long_side / max(h, w)
    size = (max(1, round(w * k)), max(1, round(h * k)))
    interp = cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR
    return cv2.resize(img, size, interpolation=interp)


def resize_to(img: np.ndarray, w: int, h: int) -> np.ndarray:
    interp = cv2.INTER_AREA if w * h < img.shape[0] * img.shape[1] else cv2.INTER_LINEAR
    return cv2.resize(img, (w, h), interpolation=interp)


def cover(img: np.ndarray, w: int, h: int) -> np.ndarray:
    """Кадрирует по центру под заданные пропорции (как object-fit: cover)."""
    ih, iw = img.shape[:2]
    if iw / ih > w / h:
        nw = round(ih * w / h)
        x0 = (iw - nw) // 2
        img = img[:, x0 : x0 + nw]
    else:
        nh = round(iw * h / w)
        y0 = (ih - nh) // 2
        img = img[y0 : y0 + nh]
    return resize_to(img, w, h)


def to_jpeg(rgb: np.ndarray | Image.Image, quality: int = 86) -> bytes:
    img = rgb if isinstance(rgb, Image.Image) else Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


def encode_grid(density: np.ndarray, long_side: int = 160) -> dict:
    """Карта плотности -> компактная сетка uint8 (максимум = 255) для отрисовки на клиенте."""
    grid = np.clip(resize_long(density.astype(np.float32), long_side), 0, None)
    grid = grid / (grid.max() or 1.0)
    data = np.round(grid * 255).astype(np.uint8)
    return {"w": int(data.shape[1]), "h": int(data.shape[0]), "data": base64.b64encode(data.tobytes()).decode()}
