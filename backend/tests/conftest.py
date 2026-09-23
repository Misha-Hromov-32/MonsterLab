"""Общие фикстуры. Окружение задаётся до импорта приложения: config читает его один раз."""

from __future__ import annotations

import io
import os
import shutil
import tempfile

import numpy as np
import pytest
from PIL import Image

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="monster-lab-test-")
os.environ["ENGINE"] = "classic"  # тесты не зависят от torch и весов DeepGaze
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ.pop("STATIC_DIR", None)
os.environ.pop("PROXYAPI_KEY", None)
os.environ.pop("TRUST_PROXY", None)

from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
    shutil.rmtree(os.environ["DATA_DIR"], ignore_errors=True)


@pytest.fixture(autouse=True)
def _fresh_limits() -> None:
    """Лимиты частоты общие на процесс — сбрасываем, чтобы тесты не влияли друг на друга."""
    for limiter in (ratelimit.analysis_limit, ratelimit.expert_limit, ratelimit.login_limit):
        limiter._hits.clear()


def make_cover(seed: int = 0, size: tuple[int, int] = (360, 480)) -> np.ndarray:
    """Обложка-заглушка: светлый фон, цветной «товар» и тёмная плашка с «текстом»."""
    rng = np.random.default_rng(seed)
    w, h = size
    img = np.full((h, w, 3), 240, np.uint8)
    color = rng.integers(20, 230, 3)
    img[h // 4 : h * 3 // 4, w // 4 : w * 3 // 4] = color
    img[20:60, 20 : w - 20] = 30
    return img


def jpeg_bytes(rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=90)
    return buf.getvalue()
