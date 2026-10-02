"""Логотип MonStoreLab: растр → векторные контуры для сайта, фавиконки и писем.

Исходник — квадратный логотип с рамкой и тремя строками «MON / STORE / LAB» (tools/brand/logo-source.png).
Из него собираются:
  - полный логотип (рамка + три строки) — для страниц и документации;
  - горизонтальная строка «MON STORE LAB» с одинаковой высотой букв — для шапки сайта;
  - знак «O с рожками» — для фавиконки и маленьких мест.

Контуры ищутся на увеличенной в 4 раза маске (гладкие края), рисуются с fill-rule="evenodd":
внутренности букв и рамки остаются пустыми без отдельной разметки «дырок».

Запуск (из корня репозитория): python tools/brand/vectorize.py
Результат: frontend/src/lib/brand.ts, frontend/public/favicon.svg, docs/images/logo.svg.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("logo-source.png")
COLOR = "#c81fb2"
SCALE = 4  # увеличение перед поиском контуров
EPS = 1.1  # упрощение контура, пиксели увеличенной маски

# строки текста и колонки, по которым меряется высота прописных (рамку и рожки не учитываем)
ROWS = {"MON": (179, 516), "STORE": (541, 762), "LAB": (789, 1086)}
CAP_COLUMNS = {"MON": (205, 265), "STORE": (365, 520), "LAB": (200, 285)}
INSIDE_X = (150, 1115)  # внутри рамки
MARK_BOX = (485, 175, 780, 516)  # «O с рожками»: x0, y0, x1, y1
WORD_GAP = 0.34  # расстояние между словами в горизонтальной версии, доля высоты прописной
LF = "\n"  # файлы — с переводами строк LF и на Windows (иначе git и prettier видят изменения)


def load_mask() -> np.ndarray:
    src = Image.open(SOURCE).convert("RGBA")
    flat = Image.new("RGBA", src.size, (255, 255, 255, 255))
    flat.alpha_composite(src)  # прозрачный фон исходника → белый
    rgb = np.asarray(flat.convert("RGB")).astype(np.float32)
    ink = 255 - rgb[..., 1]  # белый фон → 0, маджента (G≈31) → ~224
    big = cv2.resize(ink, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    return (big > 112).astype(np.uint8)


def contours(mask: np.ndarray) -> list[np.ndarray]:
    found, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in found:
        if cv2.contourArea(c) < 40 * SCALE * SCALE:  # соринки
            continue
        out.append(cv2.approxPolyDP(c, EPS, True)[:, 0, :].astype(np.float64) / SCALE)
    return out


def to_path(polys: list[np.ndarray], dx: float = 0, dy: float = 0, k: float = 1) -> str:
    parts = []
    for p in polys:
        pts = [f"{(x + dx) * k:.1f} {(y + dy) * k:.1f}" for x, y in p]
        parts.append("M" + "L".join(pts) + "Z")
    return "".join(parts)


def crop(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
    m = np.zeros_like(mask)
    m[y0 * SCALE : y1 * SCALE, x0 * SCALE : x1 * SCALE] = mask[y0 * SCALE : y1 * SCALE, x0 * SCALE : x1 * SCALE]
    return m


def cap(mask: np.ndarray, row: str) -> tuple[float, float]:
    """Верх и низ прописных строки (по колонке первой буквы), в пикселях исходника."""
    y0, y1 = ROWS[row]
    x0, x1 = CAP_COLUMNS[row]
    ys = np.nonzero(mask[y0 * SCALE : y1 * SCALE, x0 * SCALE : x1 * SCALE].any(axis=1))[0]
    return y0 + ys.min() / SCALE, y0 + (ys.max() + 1) / SCALE


def bbox(polys: list[np.ndarray]) -> tuple[float, float, float, float]:
    allp = np.vstack(polys)
    return allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max()


def main() -> None:
    mask = load_mask()

    # полный логотип
    full = contours(mask)
    x0, y0, x1, y1 = bbox(full)
    logo = {"viewBox": f"0 0 {x1 - x0:.0f} {y1 - y0:.0f}", "d": to_path(full, -x0, -y0)}

    # знак «O с рожками»
    mark = contours(crop(mask, *MARK_BOX))
    mx0, my0, mx1, my1 = bbox(mark)
    pad = 4
    mark_out = {
        "viewBox": f"0 0 {mx1 - mx0 + 2 * pad:.0f} {my1 - my0 + 2 * pad:.0f}",
        "d": to_path(mark, -mx0 + pad, -my0 + pad),
    }

    # горизонтальная строка: каждое слово масштабируем к одной высоте прописных и ставим на одну линию
    H = 100.0
    parts, cursor, top, bottom = [], 0.0, 0.0, 0.0
    for row, (ry0, ry1) in ROWS.items():
        polys = contours(crop(mask, INSIDE_X[0], ry0, INSIDE_X[1], ry1))
        c_top, c_base = cap(mask, row)
        k = H / (c_base - c_top)
        bx0, by0, bx1, by1 = bbox(polys)
        parts.append(to_path(polys, -bx0 + cursor / k, -c_base, k))
        top = min(top, (by0 - c_base) * k)
        bottom = max(bottom, (by1 - c_base) * k)  # круглые буквы чуть ниже линии строки
        cursor += (bx1 - bx0) * k + WORD_GAP * H
    width = cursor - WORD_GAP * H
    # координаты по y — от линии строки вверх (отрицательные); сдвигаем, чтобы viewBox начинался с 0
    word = {"viewBox": f"0 {top:.1f} {width:.1f} {bottom - top:.1f}", "d": "".join(parts)}

    brand_ts = ROOT / "frontend" / "src" / "lib" / "brand.ts"
    brand_ts.write_text(
        "// Логотип MonStoreLab в векторе — сгенерировано tools/brand/vectorize.py из tools/brand/logo-source.png.\n"
        "// Не правьте вручную: поменяйте исходник и запустите скрипт заново.\n\n"
        f"export const BRAND_COLOR = '{COLOR}'\n\n"
        "/** Знак «O с рожками»: фавиконка, маленькие места, индикатор анализа. */\n"
        f"export const MARK = {json.dumps(mark_out)}\n\n"
        "/** Горизонтальная строка «MON STORE LAB» — шапка сайта. */\n"
        f"export const WORDMARK = {json.dumps(word)}\n\n"
        "/** Полный квадратный логотип с рамкой. */\n"
        f"export const LOGO = {json.dumps(logo)}\n",
        "utf-8",
        newline=LF,
    )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"><path fill="{c}" fill-rule="evenodd" d="{d}"/></svg>\n'
    )
    (ROOT / "frontend" / "public" / "favicon.svg").write_text(
        svg.format(vb=mark_out["viewBox"], c=COLOR, d=mark_out["d"]), "utf-8", newline=LF
    )
    (ROOT / "docs" / "images" / "logo.svg").write_text(
        svg.format(vb=logo["viewBox"], c=COLOR, d=logo["d"]), "utf-8", newline=LF
    )
    sizes = {k: len(v["d"]) for k, v in {"mark": mark_out, "wordmark": word, "logo": logo}.items()}
    print("готово, символов в путях:", sizes, "· строка:", word["viewBox"])


if __name__ == "__main__":
    main()
