"""Полный отчёт по одной обложке — всё, что показывает вкладка «Разбор»."""

from __future__ import annotations

import numpy as np

from . import metrics, saliency
from .imaging import encode_grid


def cover_report(rgb: np.ndarray) -> dict:
    """Карта внимания, порядок взгляда, палитра, оценки и выводы."""
    dens = saliency.density(rgb)
    return {
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
        "grid": encode_grid(dens),
        "fixations": metrics.fixations(dens),
        "palette": metrics.palette(rgb),
        **metrics.analyze(rgb, dens),
    }
