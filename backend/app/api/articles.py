"""Редактор статей и серверные HTML-страницы для читателей и поисковых систем."""

import re
import sqlite3
from html import escape
from typing import Annotated
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field, StringConstraints

from .. import config
from ..errors import api_error
from ..services import db
from ..services.article_seed import articles
from .deps import require_admin

router = APIRouter()
admin = APIRouter(prefix="/api/admin/articles", dependencies=[Depends(require_admin)])
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)]


class Article(BaseModel):
    slug: Slug
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=350)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=90000)]
    published: bool = False
    version: int = Field(0, ge=0)


def seed() -> None:
    with db.connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS editorial_seed (edition INTEGER PRIMARY KEY)")
        if con.execute("INSERT OR IGNORE INTO editorial_seed VALUES (1)").rowcount:
            con.executemany(
                "INSERT OR IGNORE INTO articles(slug,title,summary,body,published) VALUES(?,?,?,?,1)", articles()
            )


def render_body(body: str) -> str:
    def inline(line):
        safe = escape(line)
        return re.sub(
            r"\[([^\[\]]{1,200})\]\((https?://[^\s<>()]+|/articles/[a-z0-9-]+|/studio#(?:rules|wb|partner))\)",
            r'<a href="\2">\1</a>',
            safe,
        )

    blocks = []
    for line in body.splitlines():
        line = line.strip()
        if line:
            heading = line.startswith("## ")
            tag = "h2" if heading else "p"
            blocks.append(f"<{tag}>{inline(line[3:] if heading else line)}</{tag}>")
    return "\n".join(blocks)


STYLE = """
*{box-sizing:border-box}body{margin:0;background:#f6f6f2;color:#222322;font:17px/1.65 system-ui,sans-serif}
main,nav{max-width:820px;margin:auto;padding:20px clamp(16px,5vw,48px)}
nav{display:flex;gap:24px;border-bottom:1px solid #d6d6ce}
nav a:first-child{font-weight:750;margin-right:auto}a{color:#494082;text-underline-offset:3px}
h1{font-size:clamp(34px,6vw,56px);line-height:1.05;letter-spacing:-.04em;margin:36px 0 20px}
h2{font-size:clamp(22px,4vw,30px);line-height:1.22;margin:36px 0 10px}.lead{font-size:1.2em;color:#4b4a49}
article{padding-bottom:32px}aside{border-top:1px solid #d6d6ce;padding:16px 0}a:focus-visible{outline:3px solid #6758b1}
"""


def page(title: str, summary: str, path: str, content: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} — MonStoreLab</title>
<meta name="description" content="{escape(summary)}"><link rel="canonical" href="{escape(config.PUBLIC_URL + path)}">
<style>{STYLE}</style></head><body><nav><a href="/">MonStoreLab</a><a href="/articles">Все статьи</a></nav>
<main>{content}</main></body></html>""")


@router.get("/articles", response_class=HTMLResponse)
def journal():
    with db.connect() as con:
        rows = con.execute("SELECT slug,title,summary FROM articles WHERE published=1 ORDER BY id DESC").fetchall()
    entries = "".join(
        f'<section><h2><a href="/articles/{r["slug"]}">{escape(r["title"])}</a></h2>'
        f"<p>{escape(r['summary'])}</p></section>"
        for r in rows
    )
    return page(
        "Статьи о карточках товаров",
        "Практические руководства по обложкам, требованиям площадок и проверке каталога.",
        "/articles",
        "<h1>Статьи о карточках товаров</h1>" + entries,
    )


@router.get("/articles/{slug}", response_class=HTMLResponse)
def article_page(slug: str):
    with db.connect() as con:
        row = con.execute("SELECT * FROM articles WHERE slug=? AND published=1", (slug,)).fetchone()
    if not row:
        return HTMLResponse(
            '<html lang="ru"><title>Статья не найдена</title><h1>Статья не найдена</h1>'
            '<a href="/articles">Все статьи</a></html>',
            404,
        )
    content = (
        f'<article><h1>{escape(row["title"])}</h1><p class="lead">{escape(row["summary"])}</p>'
        f'{render_body(row["body"])}</article><aside><a href="/">Проверить обложку в MonStoreLab</a></aside>'
    )
    return page(row["title"], row["summary"], "/articles/" + slug, content)


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return f"User-agent: *\nDisallow: /admin\nDisallow: /api/\nSitemap: {config.PUBLIC_URL}/sitemap.xml\n"


@router.get("/sitemap.xml")
def sitemap():
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    with db.connect() as con:
        paths = [
            "/",
            "/articles",
            *("/articles/" + r[0] for r in con.execute("SELECT slug FROM articles WHERE published=1")),
        ]
    for path in paths:
        ET.SubElement(ET.SubElement(root, "url"), "loc").text = config.PUBLIC_URL + path
    return Response(ET.tostring(root, encoding="utf-8", xml_declaration=True), media_type="application/xml")


@admin.get("")
def drafts():
    with db.connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM articles ORDER BY id DESC")]


class Preview(BaseModel):
    body: str = Field(max_length=90000)


@admin.post("/preview")
def preview(body: Preview):
    return {"html": render_body(body.body)}


def save(body: Article, article_id: int | None = None):
    values = (body.slug, body.title, body.summary, body.body, body.published)
    try:
        with db.connect() as con:
            if article_id is None:
                article_id = con.execute(
                    "INSERT INTO articles(slug,title,summary,body,published) VALUES (?,?,?,?,?)", values
                ).lastrowid
            elif not con.execute(
                "UPDATE articles SET slug=?,title=?,summary=?,body=?,published=?,version=version+1"
                " WHERE id=? AND version=?",
                (*values, article_id, body.version),
            ).rowcount:
                raise api_error(409, "stale", "Статья уже изменилась. Откройте её заново.")
            return dict(con.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise api_error(409, "slug_used", "Этот адрес уже занят другой статьёй") from exc


@admin.post("")
def create(body: Article):
    return save(body)


@admin.put("/{article_id}")
def update(article_id: int, body: Article):
    return save(body, article_id)


router.include_router(admin)
