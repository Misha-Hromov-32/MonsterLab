"""Загруженные обложки живут в памяти, чтобы полка и экспертный разбор не требовали повторной загрузки.

Храним не массив пикселей, а JPEG до 1024 px по длинной стороне (~200 КБ вместо ~12 МБ):
для полки карточка всё равно ужимается до 240×320, а моделям больше 1024 px не нужно.

Очередь общая для всех посетителей: 256 обложек — это ~50 МБ памяти и запас на десятки
одновременных сессий. Вытесненную картинку фронтенд молча загружает заново (image_expired),
так что переполнение стоит лишь лишнего запроса, а не потерянной работы.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict

import numpy as np

from ..core.imaging import data_url, decode, resize_long, to_jpeg

STORE_SIZE = 256
STORED_SIDE = 1024


class ImageExpired(LookupError):
    """Картинки с таким id больше нет в памяти (перезапуск сервера или вытеснение)."""


class UploadStore:
    def __init__(self, size: int) -> None:
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def put(self, rgb: np.ndarray) -> str:
        jpeg = to_jpeg(resize_long(rgb, STORED_SIDE) if max(rgb.shape[:2]) > STORED_SIDE else rgb, 90)
        key = uuid.uuid4().hex[:12]
        with self._lock:
            self._items[key] = jpeg
            while len(self._items) > self._size:
                self._items.popitem(last=False)
        return key

    def jpeg(self, key: str) -> bytes:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                raise ImageExpired(key)
            self._items.move_to_end(key)
            return item

    def rgb(self, key: str) -> np.ndarray:
        return decode(self.jpeg(key))

    def data_url(self, key: str) -> str:
        return data_url(self.jpeg(key))


store = UploadStore(STORE_SIZE)
