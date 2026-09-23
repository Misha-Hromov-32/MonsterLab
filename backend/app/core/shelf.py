"""Тест полки: обложку ставят в сетку выдачи среди конкурентов на разные позиции и меряют,
какую долю внимания она забирает относительно «честной» доли 1/N (stop power)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from . import saliency
from .imaging import cover, data_url, encode_grid, to_jpeg

Rect = tuple[int, int, int, int]  # x, y, w, h в пикселях мозаики


@dataclass(frozen=True)
class Layout:
    cols: int
    slots: int  # сколько карточек в сетке максимум
    tile: tuple[int, int]  # ширина, высота карточки
    gap: int
    pad: int


LAYOUTS = {
    "mobile": Layout(cols=2, slots=6, tile=(240, 320), gap=10, pad=12),  # мобильное приложение
    "desktop": Layout(cols=5, slots=10, tile=(200, 267), gap=14, pad=16),  # сайт на компьютере
}
MAX_POSITIONS = 4  # на скольких позициях проверяем каждый вариант


def mosaic(
    tiles: list[np.ndarray], cols: int, tile: tuple[int, int], gap: int, pad: int
) -> tuple[np.ndarray, list[Rect]]:
    """Собирает сетку выдачи на белом фоне."""
    tw, th = tile
    rows = math.ceil(len(tiles) / cols)
    width = pad * 2 + cols * tw + (cols - 1) * gap
    height = pad * 2 + rows * th + (rows - 1) * gap
    canvas = np.full((height, width, 3), 255, np.uint8)
    rects = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = pad + c * (tw + gap), pad + r * (th + gap)
        canvas[y : y + th, x : x + tw] = cover(t, tw, th)
        rects.append((x, y, tw, th))
    return canvas, rects


def shares(dens: np.ndarray, rects: list[Rect], size: tuple[int, int]) -> np.ndarray:
    """Доля внимания, которая приходится на каждый прямоугольник (сумма = 1)."""
    height, width = size
    sx, sy = dens.shape[1] / width, dens.shape[0] / height
    mass = np.array(
        [dens[round(y * sy) : round((y + h) * sy), round(x * sx) : round((x + w) * sx)].sum() for x, y, w, h in rects]
    )
    return mass / (mass.sum() or 1.0)


def _positions(n: int) -> list[int]:
    if n <= MAX_POSITIONS:
        return list(range(n))
    # равномерно по сетке: первая, последняя и между ними
    return sorted({round(i * (n - 1) / (MAX_POSITIONS - 1)) for i in range(MAX_POSITIONS)})


# ---------------------------------------------------------------- непохожесть на соседей


def _features(rgb: np.ndarray) -> np.ndarray:
    """Короткий «отпечаток» обложки: средний цвет, разброс, насыщенность, детализация, оттенки."""
    work = cover(rgb, 96, 128)
    lab = cv2.cvtColor(work, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    mean, std = lab.mean(0), lab.std(0)
    r, g, b = (work[..., i].astype(np.float32) for i in range(3))
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = math.hypot(rg.std(), yb.std()) + 0.3 * math.hypot(rg.mean(), yb.mean())  # Hasler & Süsstrunk
    edges = float((cv2.Canny(cv2.cvtColor(work, cv2.COLOR_RGB2GRAY), 60, 150) > 0).mean())
    hsv = cv2.cvtColor(work, cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(np.float32)
    hues = np.bincount((hsv[:, 0] // 15).astype(int), weights=hsv[:, 1] / 255, minlength=12)[:12]
    hues = hues / (hues.sum() or 1.0) * min(1.0, colorful / 60)
    return np.concatenate(
        [
            [mean[0] / 255, (mean[1] - 128) / 64, (mean[2] - 128) / 64],
            std / 96,
            [colorful / 100, edges * 4],
            hues,
        ]
    )


def distinctiveness(target: np.ndarray, others: list[np.ndarray]) -> int:
    """Насколько обложка непохожа на соседей, 0–100.

    Расстояние меряем относительно того, насколько соседи различаются между собой: если вся
    выдача пёстрая, выделиться сложнее. 0.8 «типичного» расстояния -> 0, 2.2 -> 100.
    """
    if not others:
        return 0
    ft = _features(target)
    fo = [_features(o) for o in others]
    dist = float(np.mean([np.linalg.norm(ft - f) for f in fo]))
    pairs = [np.linalg.norm(a - b) for i, a in enumerate(fo) for b in fo[i + 1 :]]
    typical = float(np.mean(pairs)) if pairs else 0.0
    if typical <= 0.15:  # соседей мало или они одинаковые — берём типичное значение для выдачи
        typical = 0.6
    return round(min(100.0, max(0.0, (dist / typical - 0.8) / 1.4 * 100)))


# ---------------------------------------------------------------- прогон


def _pack(
    canvas: np.ndarray, dens: np.ndarray, rects: list[Rect], target: int | None, order: list[str] | None = None
) -> dict:
    height, width = canvas.shape[:2]
    return {
        "image": data_url(to_jpeg(canvas, 84)),
        "width": width,
        "height": height,
        "grid": encode_grid(dens, 200),
        "rects": [{"x": x / width, "y": y / height, "w": w / width, "h": h / height} for x, y, w, h in rects],
        "target": target,
        "order": order,
    }


def _vs_competitors(variants: dict[str, np.ndarray], competitors: list[np.ndarray], cfg: Layout):
    n = min(cfg.slots, len(competitors) + 1)
    results, mosaics = {}, {}
    for key, rgb in variants.items():
        acc = []
        for run, pos in enumerate(_positions(n)):
            # конкуренты сдвигаются по кругу целыми блоками: за прогоны на полке побывают все,
            # и результат не зависит от конкретного соседства
            comp = [competitors[(run * (n - 1) + j) % len(competitors)] for j in range(n - 1)]
            canvas, rects = mosaic([*comp[:pos], rgb, *comp[pos:]], cfg.cols, cfg.tile, cfg.gap, cfg.pad)
            dens = saliency.density(canvas)
            acc.append(shares(dens, rects, canvas.shape[:2])[pos])
            if run == 0:
                mosaics[key] = _pack(canvas, dens, rects, pos)
        results[key] = {
            "share": float(np.mean(acc)),
            "fair": 1 / n,
            "runs": len(acc),
            "distinct": distinctiveness(rgb, competitors),
        }
    return results, mosaics


def _vs_each_other(variants: dict[str, np.ndarray], cfg: Layout):
    keys = list(variants)
    n = len(keys)
    acc: dict[str, list[float]] = {k: [] for k in keys}
    mosaics = {}
    for shift in range(n):  # каждый вариант побывает на каждой позиции
        order = keys[shift:] + keys[:shift]
        canvas, rects = mosaic([variants[k] for k in order], cfg.cols, cfg.tile, cfg.gap, cfg.pad)
        dens = saliency.density(canvas)
        for k, share in zip(order, shares(dens, rects, canvas.shape[:2])):
            acc[k].append(share)
        if shift == 0:
            mosaics["_all"] = _pack(canvas, dens, rects, None, order)
    results = {
        k: {
            "share": float(np.mean(acc[k])),
            "fair": 1 / n,
            "runs": n,
            "distinct": distinctiveness(variants[k], [variants[o] for o in keys if o != k]),
        }
        for k in keys
    }
    return results, mosaics


def run(variants: dict[str, np.ndarray], competitors: list[np.ndarray], layout: str) -> dict:
    cfg = LAYOUTS.get(layout) or LAYOUTS["mobile"]
    if competitors:
        results, mosaics = _vs_competitors(variants, competitors, cfg)
    else:
        results, mosaics = _vs_each_other(variants, cfg)
    for r in results.values():
        r["stop_power"] = round(r["share"] / r["fair"], 3)
        r["share"] = round(r["share"], 4)
        r["fair"] = round(r["fair"], 4)
    return {
        "mode": "competitors" if competitors else "variants",
        "layout": layout if layout in LAYOUTS else "mobile",
        "results": results,
        "mosaics": mosaics,
    }
