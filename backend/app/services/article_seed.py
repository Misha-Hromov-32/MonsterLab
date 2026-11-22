"""Начальные статьи журнала. Администратор редактирует копии в базе."""

from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "articles"


def articles():
    for path in sorted(DIRECTORY.glob("*.md")):
        heading, summary, body = path.read_text(encoding="utf-8").strip().split("\n\n", 2)
        yield path.stem, heading.removeprefix("# "), summary, body
