"""Экспертный разбор: мультимодальные модели через ProxyAPI (OpenAI-совместимый API).

critique — развёрнутый разбор одной обложки: каждая модель отвечает отдельно, оценки усредняются.
compare  — попарные сравнения «на что нажмёт покупатель». Каждая пара показывается в обоих
           порядках, чтобы погасить склонность моделей выбирать первую картинку, а итоговый
           рейтинг собирается моделью Брэдли–Терри.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import math
import re
from dataclasses import dataclass

import httpx

from .. import config
from . import site

log = logging.getLogger(__name__)

ATTEMPTS = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
SCORE_KEYS = ("clarity", "trust", "premium", "emotion", "readability")

_sem = asyncio.Semaphore(config.EXPERT_CONCURRENCY)


class ExpertError(RuntimeError):
    """Понятное пользователю сообщение о сбое разбора."""


@dataclass(frozen=True)
class ExpertConfig:
    api_key: str
    base_url: str
    models: list[str]

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def current_config() -> ExpertConfig:
    """Ключ и модели из админ-панели; если там пусто — из переменных окружения."""
    saved = site.read()["expert"]
    models = [m for m in saved.get("models") or [] if m] or config.EXPERT_MODELS
    return ExpertConfig(
        api_key=(saved.get("api_key") or config.PROXYAPI_KEY).strip(),
        base_url=(saved.get("base_url") or config.PROXYAPI_BASE_URL).rstrip("/"),
        models=models[: config.MAX_EXPERT_MODELS],
    )


def _client(cfg: ExpertConfig) -> httpx.AsyncClient:
    if not cfg.enabled:
        raise ExpertError("Не задан ключ ProxyAPI — экспертный разбор отключён")
    return httpx.AsyncClient(
        base_url=cfg.base_url,
        timeout=httpx.Timeout(120, connect=15),
        headers={"Authorization": f"Bearer {cfg.api_key}"},
    )


def _context_text(ctx: dict) -> str:
    parts = []
    if ctx.get("category"):
        parts.append(f"Категория товара: {ctx['category']}.")
    if ctx.get("query"):
        parts.append(f"Покупатель искал: «{ctx['query']}».")
    if ctx.get("price"):
        parts.append(f"Цена товара: {ctx['price']} ₽.")
    if ctx.get("audience"):
        parts.append(f"Целевая аудитория: {ctx['audience']}.")
    parts.append("Площадка: маркетплейс (Wildberries / Ozon).")
    return " ".join(parts)


def _extract_json(text: str) -> dict:
    """Модели иногда оборачивают JSON в ```json … ``` или добавляют слова вокруг."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("ответ не в формате JSON")
    data = json.loads(text[start : end + 1], parse_constant=_reject_constant)
    if not isinstance(data, dict):
        raise ValueError("ответ не объект")
    return data


def _reject_constant(name: str) -> None:
    raise ValueError(f"недопустимое число {name}")  # NaN и Infinity ломают усреднение


def _api_error(r: httpx.Response) -> str:
    hints = {
        401: "неверный ключ ProxyAPI",
        402: "на балансе ProxyAPI закончились средства",
        403: "доступ к модели запрещён",
        404: "модель не найдена — проверьте название",
    }
    try:
        detail = r.json().get("error", {})
        msg = detail.get("message") if isinstance(detail, dict) else str(detail)
    except ValueError:
        msg = r.text[:200]
    return hints.get(r.status_code, f"HTTP {r.status_code}") + (f" ({msg})" if msg else "")


async def _ask(client: httpx.AsyncClient, model: str, prompt: str, images: list[str], max_tokens: int = 1200) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for i, url in enumerate(images, 1):
        if len(images) > 1:
            content.append({"type": "text", "text": f"Изображение {i}:"})
        content.append({"type": "image_url", "image_url": {"url": url}})
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }

    for attempt in range(1, ATTEMPTS + 1):
        last = attempt == ATTEMPTS
        try:
            async with _sem:  # паузы между попытками — вне семафора, чтобы не держать слот
                r = await client.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            if last:
                raise ExpertError(f"{model}: сеть недоступна ({type(exc).__name__})") from exc
            await asyncio.sleep(1.5 * attempt)
            continue
        if r.status_code in RETRY_STATUSES and not last:
            await asyncio.sleep(2 * attempt)
            continue
        if r.status_code >= 400:
            raise ExpertError(f"{model}: {_api_error(r)}")
        try:
            text = r.json()["choices"][0]["message"]["content"]
            if isinstance(text, list):
                text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
            if not isinstance(text, str):
                raise ValueError("пустой ответ")
            return _extract_json(text)
        except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
            if last:
                raise ExpertError(f"{model}: не удалось разобрать ответ") from exc
    raise ExpertError(f"{model}: нет ответа")


def _is_num(v: object) -> bool:
    if v is None or isinstance(v, bool):
        return False
    try:
        return math.isfinite(float(v))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------- разбор одной обложки

CRITIQUE_PROMPT = """Ты — арт-директор и специалист по конверсии карточек товаров на маркетплейсах.
Перед тобой главное фото (обложка) карточки. Покупатель видит его в выдаче на телефоне размером
около 170×230 пикселей и решает за 1–2 секунды, нажать ли.
{context}

Оцени обложку строго и конкретно, без общих слов. Верни ТОЛЬКО JSON такого вида:
{{
  "offer": "что покупатель поймёт за 1 секунду — одна фраза от его лица",
  "product": "что за товар, как ты его распознал",
  "scores": {{
    "clarity": 1-10,      // понятно ли сразу, что это и зачем
    "trust": 1-10,        // вызывает ли доверие (качество фото, аккуратность, реализм)
    "premium": 1-10,      // ощущение дорогого/качественного товара
    "emotion": 1-10,      // вызывает ли желание, эмоцию
    "readability": 1-10   // читаются ли надписи в размере превью
  }},
  "price_guess_rub": число или null,   // сколько, по ощущению, стоит товар
  "texts": [{{"text": "надпись на картинке", "legible_on_thumb": true/false}}],
  "strengths": ["что сделано хорошо", "..."],
  "issues": [{{"severity": "high|medium|low", "problem": "что мешает", "fix": "как конкретно исправить"}}],
  "verdict": "одно предложение: главный вывод"
}}
Пиши по-русски. Не больше 4 проблем, самые важные — первыми."""


async def critique(image_url: str, ctx: dict) -> dict:
    cfg = current_config()
    prompt = CRITIQUE_PROMPT.format(context=_context_text(ctx))
    async with _client(cfg) as client:
        results = await asyncio.gather(
            *(_ask(client, m, prompt, [image_url]) for m in cfg.models), return_exceptions=True
        )
    ok = [(m, r) for m, r in zip(cfg.models, results) if isinstance(r, dict)]
    failed = [(m, r) for m, r in zip(cfg.models, results) if isinstance(r, BaseException)]
    for _, exc in failed:
        log.warning("Экспертный разбор: %s", exc)
    if not ok:
        raise ExpertError("; ".join(str(r) for _, r in failed) or "Модели не ответили")

    scores = {}
    for k in SCORE_KEYS:
        vals = [float(v) for _, r in ok if _is_num(v := (r.get("scores") or {}).get(k))]
        if vals:
            scores[k] = {"mean": round(sum(vals) / len(vals), 1), "min": min(vals), "max": max(vals)}
    prices = [float(r["price_guess_rub"]) for _, r in ok if _is_num(r.get("price_guess_rub"))]
    return {
        "models": [m for m, _ in ok],
        "errors": [m for m, _ in failed],  # только id моделей: подробности — в журнале сервера
        "scores": scores,
        "price_guess": round(sum(prices) / len(prices)) if prices else None,
        "opinions": [{**r, "model": m} for m, r in ok],
    }


# ---------------------------------------------------------------- сравнение вариантов

COMPARE_PROMPT = """Ты — обычный покупатель, листающий выдачу маркетплейса в телефоне.
{context}
Перед тобой две обложки карточек одного типа товара: «Изображение 1» и «Изображение 2».
Представь, что они стоят рядом в выдаче. На какую ты скорее нажмёшь? Порядок показа случаен
и не должен влиять на выбор.
Верни ТОЛЬКО JSON:
{{"winner": 1 или 2, "confidence": число от 0.5 до 1, "reason": "почему, одно короткое предложение"}}"""


def bradley_terry(keys: list[str], games: list[tuple[str, str, float]], iters: int = 200) -> dict[str, float]:
    """Сила каждого варианта по итогам попарных «матчей» (MM-алгоритм Хантера).

    games: (победитель, проигравший, уверенность w) — победитель получает w очка, проигравший 1-w.
    Слабый априорный член не даёт силе уйти в ноль у варианта без побед. Сумма сил = 1.
    """
    wins = dict.fromkeys(keys, 0.0)
    played: dict[tuple[str, str], int] = {}
    for i, j, w in games:
        wins[i] += w
        wins[j] += 1 - w
        pair = (i, j) if i < j else (j, i)
        played[pair] = played.get(pair, 0) + 1
    p = dict.fromkeys(keys, 1.0)
    for _ in range(iters):
        new = {}
        for k in keys:
            denom = sum(n / (p[a] + p[b]) for (a, b), n in played.items() if k in (a, b))
            new[k] = (wins[k] + 0.1) / (denom + 0.2 / p[k]) if denom else p[k]
        total = sum(new.values())
        p = {k: v / total * len(keys) for k, v in new.items()}
    total = sum(p.values())
    return {k: v / total for k, v in p.items()}


async def compare(images: dict[str, str], ctx: dict) -> dict:
    keys = list(images)
    if len(keys) < 2:
        raise ExpertError("Для сравнения нужно минимум два варианта")
    cfg = current_config()
    prompt = COMPARE_PROMPT.format(context=_context_text(ctx))
    jobs = [(m, a, b) for m in cfg.models for a, b in itertools.permutations(keys, 2)]
    async with _client(cfg) as client:
        results = await asyncio.gather(
            *(_ask(client, m, prompt, [images[a], images[b]], 300) for m, a, b in jobs), return_exceptions=True
        )

    games: list[tuple[str, str, float]] = []
    records, messages, failed = [], set(), set()
    for (model, a, b), r in zip(jobs, results):
        if isinstance(r, BaseException):
            messages.add(str(r))
            failed.add(model)
            continue
        try:
            win = int(r.get("winner"))
            conf = min(1.0, max(0.5, float(r.get("confidence", 0.75))))
        except (TypeError, ValueError):
            continue
        if win not in (1, 2):
            continue
        winner, loser = (a, b) if win == 1 else (b, a)
        games.append((winner, loser, conf))
        records.append(
            {
                "model": model,
                "shown": [a, b],
                "winner": winner,
                "confidence": round(conf, 2),
                "reason": str(r.get("reason", ""))[:300],
            }
        )
    for message in sorted(messages):
        log.warning("Выбор покупателя: %s", message)
    if not games:
        raise ExpertError("; ".join(sorted(messages)) or "Модели не вернули ни одного решения")

    strength = bradley_terry(keys, games)
    ranking = [
        {
            "key": k,
            "strength": round(strength[k], 4),
            "wins": sum(1 for g in games if g[0] == k),
            "played": sum(1 for g in games if k in g[:2]),
        }
        for k in keys
    ]
    ranking.sort(key=lambda x: -x["strength"])
    answered = {r["model"] for r in records}
    return {"errors": sorted(failed - answered), "ranking": ranking, "records": records}


# ---------------------------------------------------------------- проверка из админки


async def check() -> list[dict]:
    """Короткий запрос к каждой модели: работает ли ключ и доступна ли модель."""
    cfg = current_config()

    async def one(client: httpx.AsyncClient, model: str) -> dict:
        body = {"model": model, "max_tokens": 5, "messages": [{"role": "user", "content": "Ответь одним словом: ок"}]}
        try:
            r = await client.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            return {"model": model, "ok": False, "message": f"сеть недоступна ({type(exc).__name__})"}
        if r.status_code >= 400:
            return {"model": model, "ok": False, "message": _api_error(r)}
        return {"model": model, "ok": True, "message": "работает"}

    async with _client(cfg) as client:
        return list(await asyncio.gather(*(one(client, m) for m in cfg.models)))
