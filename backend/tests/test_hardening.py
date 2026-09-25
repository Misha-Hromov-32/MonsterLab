"""Защита от неудобных входных данных: картинки-«иголки», однотонные обложки, подделанные токены,
подмена адреса для обхода лимитов, странные ответы моделей."""

from __future__ import annotations

import asyncio
import io
import json

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import ratelimit
from app.core import imaging, metrics, saliency, shelf
from app.services import auth, expert

from .conftest import make_cover


def _png(w: int, h: int, color: int = 200) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (color, color, color)).save(buf, format="PNG")
    return buf.getvalue()


def test_needle_and_huge_images_are_rejected() -> None:
    with pytest.raises(imaging.BadImage, match="вытянутое"):
        imaging.decode(_png(32, 2000))
    with pytest.raises(imaging.BadImage, match="мегапикселей"):
        imaging.decode(_png(8000, 6000))


def test_uniform_image_gives_finite_report() -> None:
    rgb = np.full((480, 360, 3), 240, np.uint8)
    dens = saliency.classic_density(rgb)
    assert np.isfinite(dens).all() and dens.sum() == pytest.approx(1.0, abs=1e-4)
    report = metrics.analyze(rgb, dens)
    assert all(np.isfinite(v) for v in report["scores"].values())
    assert all(np.isfinite(f["mass"]) for f in metrics.fixations(dens))


def test_shelf_rotation_uses_every_competitor(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: set[int] = set()
    competitors = [make_cover(i) for i in range(12)]
    real_mosaic = shelf.mosaic

    def spy(tiles, *args, **kwargs):
        seen.update(id(t) for t in tiles)
        return real_mosaic(tiles, *args, **kwargs)

    monkeypatch.setattr(shelf, "mosaic", spy)
    shelf.run({"A": make_cover(99)}, competitors, "mobile")
    assert {id(c) for c in competitors} <= seen


@pytest.mark.parametrize("token", ["", "abc", "9999999999.é", "9" * 5000 + ".x", "1.deadbeef"])
def test_bad_tokens_get_401(client: TestClient, token: str) -> None:
    # байты в latin-1: так в заголовок попадают символы, которые клиент иначе не отправит
    r = client.get("/api/admin/settings", headers={"Authorization": f"Bearer {token}".encode("latin-1")})
    assert r.status_code == 401


def test_empty_password_never_logs_in(client: TestClient) -> None:
    assert client.post("/api/admin/login", json={"password": ""}).status_code == 422
    assert auth.check_password("   ") is False


def test_forwarded_ip_is_ignored_without_proxy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = ratelimit.RateLimiter(2, 60, "стоп")
    monkeypatch.setattr(ratelimit, "login_limit", limiter)
    monkeypatch.setattr("app.api.admin.login_limit", limiter)
    codes = [
        client.post("/api/admin/login", json={"password": "x"}, headers={"X-Real-IP": f"10.0.0.{i}"}).status_code
        for i in range(3)
    ]
    assert codes[-1] == 429  # подменённый заголовок не даёт нового «адреса»


def test_rate_limiter_forgets_idle_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "MAX_TRACKED", 3)
    limiter = ratelimit.RateLimiter(5, 0.0, "стоп")  # окно 0 с — все записи сразу устаревают
    for i in range(10):
        limiter.hit(f"client-{i}")
    assert len(limiter._hits) <= 3


# ---------------------------------------------------------------- экспертный разбор с подменой API


def _chat(content: object) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture
def fake_models(monkeypatch: pytest.MonkeyPatch):
    """Подменяет ProxyAPI: ответ каждой модели задаёт словарь answers[model]."""
    answers: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        answer = answers[model]
        if isinstance(answer, int):
            return httpx.Response(answer, json={"error": {"message": "нет"}})
        return httpx.Response(200, json=_chat(answer))

    cfg = expert.ExpertConfig(api_key="test", base_url="https://proxy.test/v1", models=["a/one", "b/two"])
    monkeypatch.setattr(expert, "current_config", lambda: cfg)
    monkeypatch.setattr(
        expert,
        "_client",
        lambda c: httpx.AsyncClient(base_url=c.base_url, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(expert.asyncio, "sleep", lambda *_: _noop())
    return answers


async def _noop() -> None:
    return None


def test_critique_survives_nan_and_failed_model(fake_models: dict) -> None:
    fake_models["a/one"] = '{"scores": {"clarity": 8, "trust": NaN}, "price_guess_rub": Infinity, "verdict": "ок"}'
    fake_models["b/two"] = '```json\n{"scores": {"clarity": 6, "trust": 7}, "price_guess_rub": 990}\n```'
    result = asyncio.run(expert.critique("data:image/jpeg;base64,", {}))
    # у первой модели NaN — ответ отбрасывается целиком, считается как не ответившая
    assert result["errors"] == ["a/one"]
    assert result["scores"]["clarity"]["mean"] == 6
    assert result["price_guess"] == 990


def test_compare_ranks_and_reports_failed_models(fake_models: dict) -> None:
    fake_models["a/one"] = '{"winner": 1, "confidence": 0.9, "reason": "ярче"}'
    fake_models["b/two"] = 402
    result = asyncio.run(expert.compare({"A": "x", "B": "y"}, {}))
    assert result["errors"] == ["b/two"]
    assert len(result["ranking"]) == 2 and len(result["records"]) == 2


def test_broken_settings_file_is_set_aside(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import site

    broken = tmp_path / "settings.json"
    broken.write_text("{не json", "utf-8")
    monkeypatch.setattr(site, "SETTINGS_FILE", broken)
    assert site._read_file() is None
    assert not broken.exists() and list(tmp_path.glob("settings.broken-*.json"))


def test_precompute_failure_is_not_retried_until_example_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import precompute

    calls = []

    def boom(ex: dict) -> dict:
        calls.append(ex["id"])
        raise OSError("файл примера пропал")

    monkeypatch.setattr(precompute, "compute", boom)
    monkeypatch.setattr(precompute, "load", lambda ex: None)
    monkeypatch.setattr(precompute, "_failed", {})
    first = precompute.run_pending()
    second = precompute.run_pending()
    assert first == second == 0
    assert len(calls) == len(set(calls)) > 0  # каждый пример пробовали один раз


def test_token_without_env_password_does_not_deadlock(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # сгенерированный пароль и ключ подписи создаются под одной блокировкой — раньше поток ждал сам себя
    import threading

    monkeypatch.setattr(auth.config, "ADMIN_PASSWORD", "")
    monkeypatch.setattr(auth, "PASSWORD_FILE", tmp_path / "admin_password.txt")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / ".secret")
    auth.admin_password.cache_clear()
    auth._signing_key.cache_clear()
    auth.secret.cache_clear()
    result: list[str] = []
    worker = threading.Thread(target=lambda: result.append(auth.make_token()), daemon=True)
    worker.start()
    worker.join(timeout=5)
    try:
        assert result and auth.verify_token(result[0])
    finally:
        auth.admin_password.cache_clear()
        auth._signing_key.cache_clear()
        auth.secret.cache_clear()
