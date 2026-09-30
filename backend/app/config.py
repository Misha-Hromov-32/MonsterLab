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

# ---------------------------------------------------------------- шифрование, см. services/crypto.py

# Мастер-ключ: 64 hex-символа (openssl rand -hex 32). Пусто — ключ генерируется в DATA_DIR/.master_key.
_master = os.getenv("MASTER_KEY", "").strip()
try:
    MASTER_KEY = bytes.fromhex(_master) if _master else b""
except ValueError:
    MASTER_KEY = b""
if _master and len(MASTER_KEY) != 32:
    raise RuntimeError("MASTER_KEY — 64 hex-символа (32 байта), например из `openssl rand -hex 32`")

# ---------------------------------------------------------------- почта (подтверждение email, сброс пароля)

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _int("SMTP_PORT", 465)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
# ssl — сразу TLS (порт 465), starttls — обычно порт 587, none — без шифрования (только для отладки)
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "").strip().lower() or ("ssl" if SMTP_PORT == 465 else "starttls")
if SMTP_SECURITY not in ("ssl", "starttls", "none"):
    raise RuntimeError("SMTP_SECURITY: ssl, starttls или none")
MAIL_FROM = os.getenv("MAIL_FROM", "").strip() or SMTP_USER
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "").strip() or "Monster Lab"

# ---------------------------------------------------------------- правила сервиса (страница /legal)

# Оператор персональных данных — как в документах: «ИП Иванов Иван Иванович, ИНН …, ОГРНИП …, адрес …»
# или «Иванов Иван Иванович (самозанятый), ИНН …, адрес …»
LEGAL_OPERATOR = os.getenv("LEGAL_OPERATOR", "").strip()
# Адрес для обращений: отзыв согласия, удаление аккаунта, вопросы по данным
LEGAL_EMAIL = os.getenv("LEGAL_EMAIL", "").strip() or MAIL_FROM

PROXYAPI_KEY = os.getenv("PROXYAPI_KEY", "").strip()
PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "").strip() or "https://api.proxyapi.ru/v1"
if not PROXYAPI_BASE_URL.startswith("https://"):
    raise RuntimeError("PROXYAPI_BASE_URL должен начинаться с https:// — по нему уходит ключ API")
# JURY_MODELS — прежнее имя переменной, поддерживается для старых .env
_DEFAULT_MODELS = "google/gemini-2.5-flash,anthropic/claude-haiku-4-5"
_models = os.getenv("EXPERT_MODELS") or os.getenv("JURY_MODELS") or _DEFAULT_MODELS
EXPERT_MODELS = [m.strip() for m in _models.split(",") if m.strip()]
EXPERT_CONCURRENCY = _int("EXPERT_CONCURRENCY", 6)
# Визуальный разбор «как арт-директор» — одна сильная модель; если она не ответила — первая из EXPERT_MODELS
VISUAL_MODEL = os.getenv("VISUAL_MODEL", "").strip() or "anthropic/claude-sonnet-5-5"
VISUAL_MAX_RIVALS = 3  # сколько конкурентов показать модели рядом с обложкой

# ---------------------------------------------------------------- генерация улучшенной обложки

# Модель ProxyAPI для редактирования картинок (эндпоинт /images/edits)
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "").strip() or "openai/gpt-image-2"
# medium — ~14 ₽ и ~30 с за обложку; high — ~51 ₽ и ~75 с, разница в превью почти не видна
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "").strip() or "medium"

# ---------------------------------------------------------------- конкуренты с маркетплейса

# Wildberries отдаёт выдачу только настоящему браузеру: нужен Chromium (Playwright).
# Путь к своему Chrome/Chromium — для запуска без Docker; в образе браузер ставится сам.
BROWSER_PATH = os.getenv("BROWSER_PATH", "").strip() or None
COMPETITORS_CACHE_HOURS = _int("COMPETITORS_CACHE_HOURS", 24)

# ---------------------------------------------------------------- подписка и оплата (ЮKassa)

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
# Чек по 54-ФЗ через ЮKassa: включите, если магазин передаёт чеки через неё
YOOKASSA_RECEIPT = _flag("YOOKASSA_RECEIPT")
YOOKASSA_VAT_CODE = _int("YOOKASSA_VAT_CODE", 1)  # 1 — без НДС
# Адрес сайта: сюда ЮKassa вернёт покупателя после оплаты
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/") or "http://localhost:8080"
