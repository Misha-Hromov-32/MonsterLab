"""Экспертный разбор: мультимодальные модели через ProxyAPI (OpenAI-совместимый API).

critique — визуальный разбор обложки «как арт-директор»: общее впечатление, стиль, позиционирование,
           смысл каждой надписи, порядок чтения и вид среди конкурентов. Одна сильная модель
           (VISUAL_MODEL); если она не ответила — запасная из EXPERT_MODELS.
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
THINKING_TOKENS = 3000  # запас на размышления «думающих» моделей сверх длины самого ответа
SCORE_KEYS = ("aesthetics", "offer", "positioning", "standout", "trust")
MESSAGE_ROLES = ("оффер", "факт", "статус", "бренд", "призыв", "шум")
# Модели, у которых можно выключить «размышления»: для мгновенного выбора «на что нажму» они не нужны,
# а стоят в 7 раз дороже самого ответа (замер 30.09.2026: 3,3 ₽ против 0,46 ₽ за пару).
NO_THINKING = ("google/gemini-2.5-flash", "google/gemini-2.5-flash-lite")

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
    if ctx.get("positioning"):
        parts.append(f"Бренд и позиционирование: {ctx['positioning']}.")
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


async def _ask(
    client: httpx.AsyncClient, model: str, prompt: str, images: list[str], max_tokens: int = 1200, fast: bool = False
) -> dict:
    """fast — ответ без «размышлений», где модель это умеет: быстрее и в разы дешевле."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for i, url in enumerate(images, 1):
        if len(images) > 1:
            content.append({"type": "text", "text": f"Изображение {i}:"})
        content.append({"type": "image_url", "image_url": {"url": url}})
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        # «думающие» модели (Gemini 2.5 и новее) тратят часть max_tokens на размышления — без запаса
        # ответ обрывается посередине JSON. Оплачиваются только реально потраченные токены.
        "max_tokens": max_tokens + THINKING_TOKENS,
        "temperature": 0.2,
    }
    if fast and model in NO_THINKING:
        body["reasoning_effort"] = "none"

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


# ---------------------------------------------------------------- визуальный разбор одной обложки

CRITIQUE_PROMPT = """Ты — сильный арт-директор, который много лет делает главные фото карточек для Wildberries и Ozon
и знает, что продаёт, а что нет. Покупатель видит обложку в выдаче на телефоне размером около 170×230 пикселей.
{rivals}
{context}

Дай честный профессиональный разбор визуала — как коллеге-дизайнеру, а не новичку. Смотри на обложку целиком:
общее впечатление и уровень исполнения, стиль и визуальный язык, какой ценовой сегмент и аудиторию она считывает
и совпадает ли это с заявленным, что сообщает каждая надпись и в каком порядке покупатель это прочитает,
как обложка выглядит рядом с конкурентами.

Правила:
- Информационные плашки (объём, «новинка», комплектация, сертификаты) — нормальная часть инфографики маркетплейса.
  Не называй их перегрузом, если они аккуратно сгруппированы и несут пользу покупателю.
- Оценивай всё через одно: поможет ли это покупателю нажать и купить. Без абстрактных «добавьте контраст» —
  только с привязкой к конкретному месту обложки.
- Если обложка сильная — прямо скажи это и не выдумывай проблемы. Улучшений может быть от 0 до 3.
- Обязательно назови, что сделано хорошо и что НЕ стоит трогать.

Верни ТОЛЬКО JSON:
{{
  "impression": "2–3 предложения: общее впечатление, как ты описал бы обложку коллеге",
  "reads_as": {{
    "segment": "эконом | средний | средний+ | премиум",
    "audience": "кого цепляет",
    "mood": "стиль в 2–5 словах"
  }},
  "positioning": "совпадает ли то, что считывается, с заявленными ценой, аудиторией и позиционированием",
  "style": "визуальный язык: цвет, типографика, свет и качество фото, целостность — 2–3 предложения",
  "messages": [{{
    "text": "надпись",
    "role": "оффер | факт | статус | бренд | призыв | шум",
    "works": true,
    "comment": "зачем она покупателю и работает ли"
  }}],
  "reading_order": "что покупатель считает первым, вторым, третьим — и правильный ли это порядок",
  "shelf": "как обложка смотрится среди конкурентов: чем выделяется или с кем сливается",
  "strengths": ["что сильного и что не трогать"],
  "improvements": [{{
    "priority": 1,
    "what": "что изменить",
    "why": "как это повлияет на решение покупателя",
    "how": "как сделать"
  }}],
  "scores": {{"aesthetics": 1-10, "offer": 1-10, "positioning": 1-10, "standout": 1-10, "trust": 1-10}},
  "overall": 1-10,
  "verdict": "одно предложение — главный вывод"
}}
Пиши по-русски, живым профессиональным языком, без канцелярита."""

RIVALS_SHOWN = "Изображение 1 — наша обложка. Изображения 2–{n} — конкуренты, которые стоят рядом в выдаче."
RIVALS_NONE = "На изображении — наша обложка. Конкурентов не показали: сравнивай с типичной выдачей этой категории."


def _text(v: object, limit: int = 1200) -> str:
    return str(v).strip()[:limit] if isinstance(v, str | int | float) and not isinstance(v, bool) else ""


def _score(v: object) -> float | None:
    return round(min(10.0, max(1.0, float(v))), 1) if _is_num(v) else None  # type: ignore[arg-type]


def normalize_critique(raw: dict) -> dict:
    """Ответ модели → предсказуемая структура: лишние поля отбрасываются, оценки — в 1–10, списки ограничены."""
    scores = {k: s for k in SCORE_KEYS if (s := _score((raw.get("scores") or {}).get(k))) is not None}
    overall = _score(raw.get("overall"))
    if overall is None and scores:
        overall = round(sum(scores.values()) / len(scores), 1)
    reads = raw.get("reads_as") if isinstance(raw.get("reads_as"), dict) else {}
    messages = []
    for m in (raw.get("messages") or [])[:12]:
        if isinstance(m, dict) and _text(m.get("text"), 120):
            role = _text(m.get("role"), 20).lower()
            messages.append(
                {
                    "text": _text(m.get("text"), 120),
                    "role": role if role in MESSAGE_ROLES else "факт",
                    "works": m.get("works") is not False,
                    "comment": _text(m.get("comment"), 400),
                }
            )
    improvements = []
    for i in raw.get("improvements") or []:
        if isinstance(i, dict) and _text(i.get("what"), 300):
            prio = i.get("priority")
            improvements.append(
                {
                    "priority": int(prio) if _is_num(prio) and 1 <= float(prio) <= 3 else 3,
                    "what": _text(i.get("what"), 300),
                    "why": _text(i.get("why"), 500),
                    "how": _text(i.get("how"), 500),
                }
            )
    improvements.sort(key=lambda x: x["priority"])
    return {
        "overall": overall,
        "verdict": _text(raw.get("verdict"), 400),
        "impression": _text(raw.get("impression")),
        "reads_as": {k: _text(reads.get(k), 200) for k in ("segment", "audience", "mood")},
        "positioning": _text(raw.get("positioning")),
        "style": _text(raw.get("style")),
        "messages": messages,
        "reading_order": _text(raw.get("reading_order")),
        "shelf": _text(raw.get("shelf")),
        "strengths": [_text(x, 300) for x in (raw.get("strengths") or [])[:6] if _text(x, 300)],
        "improvements": improvements[:4],
        "scores": scores,
    }


async def critique(image_url: str, rivals: list[str], ctx: dict) -> dict:
    """Визуальный разбор. rivals — data URL обложек конкурентов из выдачи (до VISUAL_MAX_RIVALS)."""
    cfg = current_config()
    rivals = rivals[: config.VISUAL_MAX_RIVALS]
    intro = RIVALS_SHOWN.format(n=len(rivals) + 1) if rivals else RIVALS_NONE
    prompt = CRITIQUE_PROMPT.format(rivals=intro, context=_context_text(ctx))
    # сначала сильная модель, при сбое — запасные из списка экспертов
    models = list(dict.fromkeys([config.VISUAL_MODEL, *cfg.models]))[:2]
    errors: list[str] = []
    async with _client(cfg) as client:
        for model in models:
            try:
                raw = await _ask(client, model, prompt, [image_url, *rivals], 2600)
            except ExpertError as exc:
                log.warning("Визуальный разбор: %s", exc)
                errors.append(model)
                continue
            result = normalize_critique(raw)
            if result["impression"] or result["verdict"]:
                return {"model": model, "errors": errors, "rivals": len(rivals), **result}
            log.warning("Визуальный разбор: %s вернула пустой разбор", model)
            errors.append(model)
    raise ExpertError("Модели не ответили")


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


def choice_percent(strength: dict[str, float]) -> dict[str, int]:
    """Вероятность выбора в целых процентах, в сумме ровно 100 (метод наибольших остатков).

    Сила Брэдли–Терри и есть вероятность: если покупателю показать все варианты сразу, он
    выберет вариант k с вероятностью strength[k] / сумма сил — а сумма сил у нас 1.
    """
    raw = {k: v * 100 for k, v in strength.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: 100 - sum(out.values())]:
        out[k] += 1
    return out


async def compare(images: dict[str, str], ctx: dict) -> dict:
    keys = list(images)
    if len(keys) < 2:
        raise ExpertError("Для сравнения нужно минимум два варианта")
    cfg = current_config()
    prompt = COMPARE_PROMPT.format(context=_context_text(ctx))
    jobs = [(m, a, b) for m in cfg.models for a, b in itertools.permutations(keys, 2)]
    async with _client(cfg) as client:
        results = await asyncio.gather(
            *(_ask(client, m, prompt, [images[a], images[b]], 300, fast=True) for m, a, b in jobs),
            return_exceptions=True,
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
    chance = choice_percent(strength)
    ranking = [
        {
            "key": k,
            "strength": round(strength[k], 4),
            "chance": chance[k],
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
