"""Параметры процесса из переменных окружения — единственное место, где читается os.environ.

Значения читаются один раз при импорте. Всё, что меняется во время работы (тексты главной,
примеры, ключ экспертного разбора), хранится не здесь, а в services/site.py.
"""

from __future__ import annotations

import os
from pathlib import Path


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Переменная {name} должна быть целым числом, сейчас: {raw!r}") from exc


BACKEND_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- хранение

# Docker задаёт /data (том). Локально по умолчанию — backend/data рядом с кодом.
DATA_DIR = Path(os.getenv("DATA_DIR") or BACKEND_DIR / "data")
SEED_DIR = BACKEND_DIR / "seed"
# Собранный фронтенд (frontend/dist): бэкенд отдаёт его сам, если запускать без nginx.
# В Docker переменная не задаётся — фронтенд отдаёт nginx.
STATIC_DIR = os.getenv("STATIC_DIR") or None

# ---------------------------------------------------------------- движок внимания

ENGINE = os.getenv("ENGINE", "auto")  # auto — DeepGaze, если он установлен; classic — без нейросети
DEEPGAZE_SIDE = _int("DEEPGAZE_SIDE", 768)  # длинная сторона картинки для нейросети, px
TORCH_THREADS = _int("TORCH_THREADS", 0)  # 0 — подобрать автоматически

# ---------------------------------------------------------------- лимиты

MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_MB", 25) * 1024 * 1024
MAX_VARIANTS = 4
MAX_COMPETITORS = 12
MAX_EXPERT_MODELS = 6

# Бэкенд стоит за своим nginx и может верить X-Real-IP (задаётся в docker-compose.yml).
TRUST_PROXY = _flag("TRUST_PROXY")

# ---------------------------------------------------------------- админка и экспертный разбор

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

PROXYAPI_KEY = os.getenv("PROXYAPI_KEY", "").strip()
PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "").strip() or "https://api.proxyapi.ru/v1"
if not PROXYAPI_BASE_URL.startswith("https://"):
    raise RuntimeError("PROXYAPI_BASE_URL должен начинаться с https:// — по нему уходит ключ API")
# JURY_MODELS — прежнее имя переменной, поддерживается для старых .env
_DEFAULT_MODELS = "google/gemini-2.5-flash,anthropic/claude-haiku-4-5"
_models = os.getenv("EXPERT_MODELS") or os.getenv("JURY_MODELS") or _DEFAULT_MODELS
EXPERT_MODELS = [m.strip() for m in _models.split(",") if m.strip()]
EXPERT_CONCURRENCY = _int("EXPERT_CONCURRENCY", 6)
