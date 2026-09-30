"""Личные обложки: постоянное хранение в SQLite, все операции ограничены владельцем."""

from __future__ import annotations

import hashlib
import json
import time
import uuid

from ..core.imaging import data_url, resize_long, to_jpeg
from ..errors import api_error
from . import db


def save(
    user_id: int, rgb, name: str, report: dict | None = None, kind: str = "uploaded", baseline: float | None = None
) -> dict:
    jpeg = to_jpeg(rgb, 90)
    digest = hashlib.sha256(jpeg).hexdigest()
    preview = to_jpeg(resize_long(rgb, 240), 75)
    with db.connect() as con:
        existing = con.execute(
            "SELECT id, baseline FROM personal_covers WHERE user_id = ? AND digest = ?", (user_id, digest)
        ).fetchone()
        if existing:
            if report is not None:
                con.execute(
                    "UPDATE personal_covers SET report = ? WHERE id = ? AND user_id = ?",
                    (json.dumps(report, ensure_ascii=False), existing["id"], user_id),
                )
            return {"library_id": existing["id"], "generated_baseline": existing["baseline"]}
        count = con.execute("SELECT COUNT(*) FROM personal_covers WHERE user_id = ?", (user_id,)).fetchone()[0]
        if count >= 500:
            raise api_error(409, "library_full", "В кабинете уже 500 обложек. Удалите ненужные, чтобы сохранить новые.")
        key = uuid.uuid4().hex
        con.execute(
            "INSERT INTO personal_covers "
            "(id, user_id, digest, name, kind, jpeg, preview, report, baseline, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key,
                user_id,
                digest,
                name[:160] or "Обложка",
                kind,
                jpeg,
                preview,
                json.dumps(report, ensure_ascii=False) if report is not None else None,
                baseline,
                time.time(),
            ),
        )
    return {"library_id": key, "generated_baseline": baseline}


def listing(user_id: int, offset: int, limit: int) -> dict:
    with db.connect() as con:
        total = con.execute("SELECT COUNT(*) FROM personal_covers WHERE user_id = ?", (user_id,)).fetchone()[0]
        rows = con.execute(
            "SELECT id, name, kind, preview, created_at FROM personal_covers WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
    return {
        "total": total,
        "items": [
            {
                "id": r["id"],
                "name": r["name"],
                "kind": r["kind"],
                "preview": data_url(r["preview"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


def get(user_id: int, key: str) -> dict:
    with db.connect() as con:
        row = con.execute("SELECT * FROM personal_covers WHERE id = ? AND user_id = ?", (key, user_id)).fetchone()
    if row is None:
        raise api_error(404, "not_found", "Обложка не найдена")
    return dict(row)


def remove(user_id: int, key: str) -> None:
    with db.connect() as con:
        if con.execute("DELETE FROM personal_covers WHERE id = ? AND user_id = ?", (key, user_id)).rowcount != 1:
            raise api_error(404, "not_found", "Обложка не найдена")
