"""Общий баланс, резервы параллельных действий и стоимость выбранной модели."""

import json
from concurrent.futures import ThreadPoolExecutor

from app.services import accounts, credits, db, improve

from .conftest import jpeg_bytes, make_cover


def test_competing_reservations_and_refund(client, user_headers):
    user = accounts.user_from_token(user_headers["Authorization"].split()[1])
    initial = credits.wallet(user)["remaining"]

    def attempt(_):
        try:
            return credits.reserve(user, "rules", initial)
        except accounts.LimitReached:
            return None

    with ThreadPoolExecutor(2) as workers:
        results = list(workers.map(attempt, range(2)))
    assert len([r for r in results if r]) == 1
    hold = next(r for r in results if r)
    assert credits.wallet(user)["remaining"] == 0
    credits.finish(hold, False)
    assert credits.wallet(user)["remaining"] == initial


def test_snapshot_old_paid_quota(client, user_headers):
    user = accounts.user_from_token(user_headers["Authorization"].split()[1])
    accounts.activate(user.id, "start", 30)
    with db.connect() as con:
        con.execute("DELETE FROM welcome_rewards WHERE buyer=?", (user.id,))  # Аккаунт до введения бонусов.
        con.execute("UPDATE users SET quota_json=? WHERE id=?", (json.dumps({"improve": 3, "shelf": 2}), user.id))
    user = accounts.get(user.id)
    with db.connect() as con:
        con.execute(
            "INSERT INTO usage(user_id,day,feature,count) VALUES(?,?,?,?)",
            (user.id, accounts.usage_period(user), "improve", 1),
        )
    assert credits.wallet(user)["remaining"] == 2 * credits.COST["improve"] + 2 * credits.COST["shelf"]


def test_photo_generation_dispatch_and_price(client, user_headers, monkeypatch):
    user = accounts.user_from_token(user_headers["Authorization"].split()[1])
    accounts.activate(user.id, "agency", 30)
    image = jpeg_bytes(make_cover(1))
    user = accounts.get(user.id)
    current = credits.wallet(user)["remaining"]
    assert current == 7000 + 30
    calls = []

    def generate(jpeg, prompt, model):
        calls.append((prompt, model))
        return image

    monkeypatch.setattr(improve, "generate", generate)
    files = {"file": ("product.jpg", image, "image/jpeg")}
    params = {"prompt": "Светлый камень и мягкие тени"}
    assert (
        client.post(
            "/api/improve/from-photo", data={**params, "model": "unknown"}, files=files, headers=user_headers
        ).status_code
        == 422
    )
    models = client.get("/api/billing/plans").json()["image_models"]
    assert len(models) == len(set(m["id"] for m in models)) == 10
    for m in models:
        r = client.post("/api/improve/from-photo", data={**params, "model": m["id"]}, files=files, headers=user_headers)
        assert r.status_code == 200, r.text
        assert r.json()["model"] == m["id"] and calls[-1][1] == m["id"]
        assert params["prompt"] in calls[-1][0]
        current -= m["cost"]
        assert credits.wallet(user)["remaining"] == current
