"""Заранее посчитанные результаты примеров: разбор каждой обложки, тест полки и витрина главной.

Показ примера не должен тратить процессор — нейросеть на слабом сервере считает полку минуту.
Поэтому всё считается один раз в фоне и хранится в SQLite (DATA_DIR/examples.sqlite).

Когда пересчитывать, решает отпечаток примера: состав и порядок картинок, подписи, обложка
для главной, движок внимания и версия алгоритмов. Изменили пример в админке, вышла новая
ревизия встроенных примеров или поменялись метрики (ALGO_VERSION) — отпечаток другой,
и фоновый поток пересчитает пример. Пока пересчёт не готов, API отвечает «ещё не готово»,
и интерфейс считает пример как обычную загрузку.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from .. import config
from ..core import saliency, shelf
from ..core.imaging import decode
from ..core.report import cover_report
from . import showcase, site

log = logging.getLogger(__name__)

# Увеличьте, если поменялись метрики или формат результатов — все примеры пересчитаются.
ALGO_VERSION = 2
DB_FILE = config.DATA_DIR / "examples.sqlite"
KEYS = "ABCD"  # варианты примера открываются в интерфейсе в эти слоты, по порядку

_db_lock = threading.Lock()
_wake = threading.Event()
_worker: threading.Thread | None = None
_failed: dict[str, str] = {}  # example_id -> отпечаток, на котором расчёт упал: не повторяем до изменений


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    """Соединение на одну операцию: транзакция фиксируется при выходе, файл закрывается."""
    with _db_lock:
        con = sqlite3.connect(DB_FILE)
        try:
            with con:
                con.execute(
                    "CREATE TABLE IF NOT EXISTS results ("
                    " example_id TEXT PRIMARY KEY,"
                    " fingerprint TEXT NOT NULL,"
                    " payload TEXT NOT NULL,"
                    " computed_at REAL NOT NULL)"
                )
                yield con
        finally:
            con.close()


def fingerprint(ex: dict) -> str:
    parts = {
        "algo": ALGO_VERSION,
        "neural": saliency.deepgaze.ready,
        "side": config.DEEPGAZE_SIDE,
        "id": ex["id"],
        "hero": ex.get("hero"),
        "variants": [[v["id"], v.get("title", "")] for v in ex["variants"]],
        "competitors": [c["id"] for c in ex["competitors"]],
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:20]


def load(ex: dict) -> dict | None:
    """Готовые результаты примера или None, если их ещё нет или пример с тех пор изменился."""
    with _db() as con:
        row = con.execute("SELECT fingerprint, payload FROM results WHERE example_id = ?", (ex["id"],)).fetchone()
    if row is None or row[0] != fingerprint(ex):
        return None
    return json.loads(row[1])


def compute(ex: dict) -> dict:
    """Всё, что нужно показать по примеру, — один раз и целиком."""
    variants = ex["variants"][: len(KEYS)]
    images = {i["id"]: decode(site.image_path(ex["id"], i["id"]).read_bytes()) for i in variants}
    rivals = [decode(site.image_path(ex["id"], c["id"]).read_bytes()) for c in ex["competitors"]]
    keyed = {KEYS[n]: images[v["id"]] for n, v in enumerate(variants)}

    shelves = {}
    if rivals or len(keyed) >= 2:  # тесту полки нужно два варианта или хотя бы один конкурент
        shelves = {layout: shelf.run(keyed, rivals, layout) for layout in shelf.LAYOUTS}
    return {
        "keys": {KEYS[n]: v["id"] for n, v in enumerate(variants)},
        "variants": {image_id: cover_report(rgb) for image_id, rgb in images.items()},
        "shelf": shelves,
        "showcase": showcase.build(ex),
    }


def _save(example_id: str, print_: str, payload: dict) -> None:
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO results (example_id, fingerprint, payload, computed_at) VALUES (?, ?, ?, ?)",
            (example_id, print_, json.dumps(payload, ensure_ascii=False), time.time()),
        )


def _forget_missing(keep: set[str]) -> None:
    with _db() as con:
        for (example_id,) in con.execute("SELECT example_id FROM results").fetchall():
            if example_id not in keep:
                con.execute("DELETE FROM results WHERE example_id = ?", (example_id,))


def run_pending() -> int:
    """Пересчитывает устаревшие примеры по очереди, первым — пример для витрины главной."""
    _forget_missing({e["id"] for e in site.read()["examples"]})
    done = 0
    for ex in site.published_examples():
        print_ = fingerprint(ex)
        if _failed.get(ex["id"]) == print_ or load(ex) is not None:
            continue
        started = time.perf_counter()
        try:
            payload = compute(ex)
        except Exception:  # битый файл примера не должен останавливать расчёт остальных
            log.exception("Не удалось посчитать пример «%s»", ex["title"])
            _failed[ex["id"]] = print_
            continue
        _save(ex["id"], print_, payload)
        _failed.pop(ex["id"], None)
        done += 1
        log.info("Пример «%s» посчитан за %.0f с", ex["title"], time.perf_counter() - started)
    return done


def _loop() -> None:
    while True:
        _wake.wait()
        _wake.clear()
        try:
            run_pending()
        except Exception:  # поток должен пережить любую ошибку и ждать следующих изменений
            log.exception("Фоновый расчёт примеров прервался")


def schedule() -> None:
    """Попросить фоновый поток проверить примеры (после правок в админке, при старте)."""
    _wake.set()


def start() -> None:
    global _worker
    if _worker is None:
        _worker = threading.Thread(target=_loop, name="precompute", daemon=True)
        _worker.start()
        site.subscribe(schedule)
    schedule()
