"""Welcome impulses and one moderated reward for a public post."""

import re
import sqlite3
import time
from urllib.parse import urlsplit

from .. import config
from ..errors import api_error
from . import crypto, db, site

SOCIAL = 30


def welcome():
    total = site.read()["billing"].get("demo_credits", 30)
    signup = total // 3
    return signup, total - signup


def enroll(con, buyer):
    con.execute("INSERT INTO welcome_rewards VALUES(?,?,?)", (buyer, *welcome()))


def personal_link(buyer):
    code = crypto.blind_index(str(buyer), "public-share")[:18]
    return f"{config.PUBLIC_URL}/?share={code}"


def overview(user):
    with db.connect() as con:
        welcome_row = con.execute("SELECT signup,email FROM welcome_rewards WHERE buyer=?", (user.id,)).fetchone()
        claim = con.execute(
            "SELECT url,status,amount FROM social_claims WHERE buyer=? ORDER BY id DESC LIMIT 1", (user.id,)
        ).fetchone()
    signup, email = welcome_row or welcome()
    return {
        "signup": signup,
        "email": email,
        "verified": bool(user.email and user.verified),
        "legacy": welcome_row is None,
        "social": SOCIAL,
        "link": personal_link(user.id),
        "claim": dict(claim) if claim else None,
    }


def post_url(value):
    try:
        url = urlsplit(value.strip())
        host = url.netloc.lower()
        path = url.path.rstrip("/")
        if url.scheme == "https":
            if host in {"vk.com", "www.vk.com", "m.vk.com", "vk.ru", "m.vk.ru"} and re.fullmatch(
                r"/wall-?[1-9][0-9]*_[1-9][0-9]*", path
            ):
                return "https://vk.com" + path
            if host in {"t.me", "telegram.me"} and re.fullmatch(r"/[a-zA-Z][a-zA-Z0-9_]{3,31}/[1-9][0-9]*", path):
                return "https://t.me" + path.lower()
    except ValueError:
        pass
    raise api_error(422, "bad_post", "Пришлите ссылку на публичную запись VK или пост Telegram-канала.")


def submit(user, value):
    url = post_url(value)
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        current = con.execute(
            "SELECT url FROM social_claims WHERE buyer=? AND status!='declined'", (user.id,)
        ).fetchone()
        if current and current["url"] == url:
            return
        try:
            con.execute(
                "INSERT INTO social_claims(buyer,url,amount,created) VALUES(?,?,?,?)",
                (user.id, url, SOCIAL, time.time()),
            )
        except sqlite3.IntegrityError:
            raise api_error(409, "already_submitted", "Заявка на этот бонус уже существует.") from None


def pending():
    with db.connect() as con:
        return [
            {**dict(row), "link": personal_link(row["buyer"])}
            for row in con.execute(
                "SELECT id,buyer,url,created FROM social_claims WHERE status='pending' ORDER BY id LIMIT 100"
            )
        ]


def review(claim, decision):
    with db.connect() as con:
        cur = con.execute("UPDATE social_claims SET status=? WHERE id=? AND status='pending'", (decision, claim))
        if not cur.rowcount:
            row = con.execute("SELECT status FROM social_claims WHERE id=?", (claim,)).fetchone()
            if not row or row["status"] != decision:
                raise api_error(409, "claim_changed", "Заявка уже обработана или недоступна.")
