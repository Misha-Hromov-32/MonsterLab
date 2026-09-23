"""Шаг 1: скачивает фото товаров с Unsplash и вырезает фон.

    python prepare_products.py

Фото берутся по id из sets.json (поле photos) в высоком разрешении и сохраняются в stock/,
вырезанные товары — в cut/<slug>-<номер>.png. Уже готовые файлы пропускаются.
Лицензия Unsplash разрешает бесплатное, в том числе коммерческое, использование.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from PIL import Image
from rembg import new_session, remove

HERE = Path(__file__).resolve().parent
STOCK, CUT = HERE / "stock", HERE / "cut"
PHOTO_URL = "https://images.unsplash.com/photo-{id}?w=3000&q=85&fm=jpg"


def download(photo_id: str) -> Path:
    path = STOCK / f"{photo_id}.jpg"
    if not path.exists():
        STOCK.mkdir(exist_ok=True)
        with urllib.request.urlopen(PHOTO_URL.format(id=photo_id)) as r:
            path.write_bytes(r.read())
    return path


def main() -> None:
    sets = json.loads((HERE / "sets.json").read_text("utf-8"))
    session = new_session("isnet-general-use")  # точнее базовой u2net на предметной съёмке
    CUT.mkdir(exist_ok=True)
    for slug, s in sets.items():
        for i, photo_id in enumerate(s["photos"]):
            out = CUT / f"{slug}-{i}.png"
            if out.exists():
                continue
            img = Image.open(download(photo_id)).convert("RGB")
            cut = remove(img, session=session, post_process_mask=True)
            # обрезаем прозрачные поля, чтобы товар в шаблоне занимал всю отведённую область
            bbox = cut.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox()
            cut.crop(bbox).save(out)
            print(out.name, flush=True)


if __name__ == "__main__":
    main()
