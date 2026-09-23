"""Ограничение частоты запросов по IP — скользящее окно в памяти процесса.

Сервис работает одним процессом (uvicorn --workers 1), поэтому внешнее хранилище не нужно.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import Request

from . import config
from .errors import api_error

MAX_TRACKED = 10_000  # столько адресов держим в памяти, дальше вычищаем устаревшие


def client_ip(request: Request) -> str:
    """Адрес клиента. X-Real-IP принимаем только за своим nginx (TRUST_PROXY=1 в docker-compose):
    без прокси заголовок подставит кто угодно и обойдёт лимиты."""
    peer = request.client.host if request.client else "unknown"
    if config.TRUST_PROXY:
        return request.headers.get("x-real-ip") or peer
    return peer


class RateLimiter:
    def __init__(self, limit: int, window_s: float, message: str) -> None:
        self.limit = limit
        self.window_s = window_s
        self.message = message
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, hits: deque[float], now: float) -> None:
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()

    def check(self, key: str) -> None:
        """Только проверяет, не исчерпан ли лимит, — сам запрос не засчитывает."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is not None:
                self._prune(hits, now)
                if len(hits) >= self.limit:
                    raise api_error(429, "rate_limited", self.message)

    def hit(self, key: str) -> None:
        """Засчитывает запрос; сверх лимита — 429."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) >= MAX_TRACKED:
                for k in list(self._hits):
                    self._prune(self._hits[k], now)
                    if not self._hits[k]:
                        del self._hits[k]
            hits = self._hits.setdefault(key, deque())
            self._prune(hits, now)
            if len(hits) >= self.limit:
                raise api_error(429, "rate_limited", self.message)
            hits.append(now)

    def dependency(self, request: Request) -> None:
        self.hit(client_ip(request))


# Анализ дешёвый, но грузит CPU; экспертный разбор тратит деньги с баланса ProxyAPI.
analysis_limit = RateLimiter(60, 60, "Слишком много запросов. Подождите минуту.")
expert_limit = RateLimiter(10, 600, "Лимит экспертных разборов: 10 за 10 минут. Попробуйте позже.")
login_limit = RateLimiter(5, 300, "Слишком много попыток входа. Подождите 5 минут.")
