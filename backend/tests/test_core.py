"""Алгоритмы: карта внимания, метрики, полка, рейтинг Брэдли–Терри."""

from __future__ import annotations

import numpy as np
import pytest

from app.core import imaging, metrics, saliency, shelf
from app.services.expert import _extract_json, bradley_terry

from .conftest import jpeg_bytes, make_cover


def test_density_is_normalized_and_same_aspect() -> None:
    rgb = make_cover()
    dens = saliency.density(rgb)
    assert dens.sum() == pytest.approx(1.0, abs=1e-4)
    assert dens.min() >= 0
    assert dens.shape[0] / dens.shape[1] == pytest.approx(rgb.shape[0] / rgb.shape[1], rel=0.02)


def test_mass_area_extremes() -> None:
    uniform = np.full((100, 100), 1.0)
    assert metrics.mass_area(uniform, 0.5) == pytest.approx(0.5, abs=0.01)
    peak = np.zeros((100, 100))
    peak[50, 50] = 1.0
    assert metrics.mass_area(peak, 0.5) == pytest.approx(1 / 10_000)


def test_scale_is_linear_and_clamped() -> None:
    assert metrics.scale(0.22, 0.22, 0.04) == 0
    assert metrics.scale(0.04, 0.22, 0.04) == 100
    assert metrics.scale(0.13, 0.22, 0.04) == 50
    assert metrics.scale(1.0, 0.22, 0.04) == 0


def test_analyze_report_shape() -> None:
    rgb = make_cover()
    report = metrics.analyze(rgb, saliency.density(rgb))
    assert set(report) == {"index", "scores", "raw", "notes"}
    assert set(report["scores"]) == set(metrics.WEIGHTS)
    assert all(0 <= v <= 100 for v in report["scores"].values())
    assert 0 <= report["index"] <= 100


def test_small_text_loses_on_thumbnail() -> None:
    big = np.full((800, 600, 3), 255, np.uint8)
    big[300:500, 100:500] = 0  # крупная форма
    tiny = np.full((800, 600, 3), 255, np.uint8)
    tiny[::6, ::2] = 0  # мелкая «строка текста»
    assert metrics.thumbnail_survival(big) > metrics.thumbnail_survival(tiny)


def test_shelf_shares_sum_to_one() -> None:
    variants = {"A": make_cover(1), "B": make_cover(2)}
    result = shelf.run(variants, [], "mobile")
    total = sum(r["share"] for r in result["results"].values())
    assert total == pytest.approx(1.0, abs=0.01)
    assert result["mode"] == "variants"


def test_shelf_with_competitors_checks_several_positions() -> None:
    result = shelf.run({"A": make_cover(1)}, [make_cover(i) for i in range(2, 9)], "mobile")
    assert result["results"]["A"]["runs"] == shelf.MAX_POSITIONS
    assert result["results"]["A"]["fair"] == pytest.approx(1 / 6, abs=1e-3)


def test_decode_handles_transparency_and_rejects_garbage() -> None:
    rgb = imaging.decode(jpeg_bytes(make_cover()))
    assert rgb.dtype == np.uint8 and rgb.shape[2] == 3
    with pytest.raises(imaging.BadImage):
        imaging.decode(b"not an image")


def test_bradley_terry_orders_by_wins() -> None:
    games = [("A", "B", 1.0), ("A", "C", 1.0), ("B", "C", 1.0)] * 2
    strength = bradley_terry(["A", "B", "C"], games)
    assert strength["A"] > strength["B"] > strength["C"]
    assert sum(strength.values()) == pytest.approx(1.0)


def test_extract_json_from_fenced_answer() -> None:
    assert _extract_json('```json\n{"winner": 2}\n```') == {"winner": 2}
    with pytest.raises(ValueError):
        _extract_json("не знаю")
