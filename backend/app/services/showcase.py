"""Витрина главной: карта внимания обложки примера и та же обложка в ленте среди конкурентов.

Считается заранее вместе с остальными результатами примера (services/precompute.py)."""

from __future__ import annotations

import numpy as np

from ..core import metrics, saliency
from ..core.imaging import cover, decode, encode_grid
from ..core.shelf import LAYOUTS, mosaic, shares
from . import site

FEED_COLS = 6
FEED_TILES = 12  # два полных ряда, как выдача на широком экране
TILE = LAYOUTS["mobile"].tile  # те же карточки, что в тесте полки
FEED_GAP = 12


def _load(example_id: str, image_id: str) -> np.ndarray:
    return decode(site.image_path(example_id, image_id).read_bytes())


def build(ex: dict) -> dict:
    hero = next((v for v in ex["variants"] if v["id"] == ex.get("hero")), ex["variants"][0])
    rgb = _load(ex["id"], hero["id"])
    dens = saliency.density(rgb)
    report = metrics.analyze(rgb, dens)
    card = {
        "url": site.image_url(ex["id"], hero["id"]),
        "title": hero.get("title", ""),
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
        "grid": encode_grid(dens),
        "fixations": metrics.fixations(dens),
        "index": report["index"],
        "scores": report["scores"],
        "area50": report["raw"]["area50"],
    }

    # лента: сначала конкуренты, потом другие варианты, при нехватке — по кругу
    pool = ex["competitors"] + [v for v in ex["variants"] if v["id"] != hero["id"]]
    order = [hero] + ([pool[i % len(pool)] for i in range(FEED_TILES - 1)] if pool else [])
    if len(order) > 3:  # не в углу и не под заголовком, а в первом ряду ближе к центру
        order.insert(2, order.pop(0))
    tiles = [cover(_load(ex["id"], t["id"]), *TILE) for t in order]
    canvas, rects = mosaic(tiles, min(FEED_COLS, len(tiles)), TILE, FEED_GAP, 0)  # без полей: картинку обрежет вёрстка
    feed_dens = saliency.density(canvas)
    feed_shares = shares(feed_dens, rects, canvas.shape[:2])
    target = order.index(hero)
    height, width = canvas.shape[:2]
    feed = {
        "tiles": [
            {"url": site.image_url(ex["id"], t["id"]), "x": x / width, "y": y / height, "w": w / width, "h": h / height}
            for t, (x, y, w, h) in zip(order, rects)
        ],
        "width": width,
        "height": height,
        "grid": encode_grid(feed_dens, 240),
        "target": target,
        "share": round(float(feed_shares[target]), 4),
        "fair": round(1 / len(order), 4),
    }
    return {"example": ex["id"], "card": card, "feed": feed}
