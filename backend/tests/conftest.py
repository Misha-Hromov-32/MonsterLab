"""Общие фикстуры. Окружение задаётся до импорта приложения: config читает его один раз."""

from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
from email.message import EmailMessage

import numpy as np
import pytest
from PIL import Image

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="monster-lab-test-")
os.environ["ENGINE"] = "classic"  # тесты не зависят от torch и весов DeepGaze
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ.pop("STATIC_DIR", None)
os.environ.pop("PROXYAPI_KEY", None)
os.environ.pop("TRUST_PROXY", None)
os.environ.pop("MASTER_KEY", None)
os.environ.pop("SMTP_HOST", None)
os.environ.pop("TOCHKA_JWT", None)
# тестовые адреса — на example.com; в бою регистрация только на российских почтовых сервисах
os.environ["ALLOWED_EMAIL_DOMAINS"] = "example.com"
os.environ.pop("PAYMENT_PROVIDER", None)

from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app
from app.services import accounts, mail, precompute

# Фоновый поток расчёта примеров в тестах не нужен: тесты вызывают precompute.run_pending() сами
# и проверяют результат детерминированно.
precompute.start = lambda: None

# Письма не уходят по SMTP, а складываются сюда — тесты достают из них ссылки.
OUTBOX: list[EmailMessage] = []
mail.deliver = OUTBOX.append

PASSWORD = "секретный-пароль"
CONSENT = {"accept_terms": True, "accept_personal_data": True}
_users = iter(range(1, 100_000))


def link_token(email: str, purpose: str) -> str:
    """Токен из последней ссылки verify/reset, отправленной на этот адрес."""
    for msg in reversed(OUTBOX):
        if msg["To"] == email:
            found = re.search(rf"\?{purpose}=([\w-]+)", msg.get_body(("plain",)).get_content())
            if found:
                return found.group(1)
    raise AssertionError(f"Письма {purpose} для {email} нет")


def verified_token(client: TestClient, email: str | None = None) -> str:
    """Регистрирует покупателя, подтверждает почту по ссылке из письма и возвращает токен входа."""
    email = email or f"buyer{next(_users)}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": PASSWORD, **CONSENT})
    assert r.status_code == 200, r.text
    r = client.post("/api/auth/verify", json={"token": link_token(email, "verify")})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Клиент вошедшего покупателя на старшем тарифе: функции сервиса — только после входа,
    а квот хватает на весь прогон тестов."""
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {verified_token(c, 'session@example.com')}"
        c.headers["X-Wait"] = "1"  # тяжёлые ручки отвечают результатом, а не задачей очереди (см. test_jobs.py)
        accounts.activate(accounts.find("session@example.com").id, "agency", 30)
        yield c
    shutil.rmtree(os.environ["DATA_DIR"], ignore_errors=True)


@pytest.fixture
def anon(client: TestClient) -> TestClient:
    """Гость без входа (приложение уже запущено фикстурой client)."""
    return TestClient(app, headers={"X-Wait": "1"})


@pytest.fixture(autouse=True)
def _fresh_limits() -> None:
    """Лимиты частоты общие на процесс — сбрасываем, чтобы тесты не влияли друг на друга."""
    for limiter in (
        ratelimit.analysis_limit,
        ratelimit.expert_limit,
        ratelimit.login_limit,
        ratelimit.mail_limit,
        ratelimit.promo_limit,
    ):
        limiter._hits.clear()


@pytest.fixture
def user_headers(client: TestClient) -> dict:
    """Свежий покупатель с демо-доступом — заголовок с его токеном входа."""
    return {"Authorization": f"Bearer {verified_token(client)}"}


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
