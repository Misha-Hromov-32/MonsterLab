from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from app.services import accounts, credits, db, rewards


def test_welcome_and_social(client):
    user = accounts.register("reward-user@example.com", "complex-password654!", True)
    assert credits.wallet(user)["remaining"] == 10
    user, _ = accounts.verify_email(accounts._issue(user, "verify"))
    assert credits.wallet(user)["remaining"] == 30
    headers = {"Authorization": f"Bearer {accounts.make_token(user)}"}
    for url in ("https://example.com/wall1_2", "https://vk.com@other.com/wall1_2", "https://t.me/share/url"):
        assert client.post("/api/rewards/share", json={"url": url}, headers=headers).status_code == 422
    post = "https://t.me/PublicChannel/234?single"
    for _ in range(2):
        assert (
            client.post("/api/rewards/share", json={"url": post}, headers=headers).json()["claim"]["status"]
            == "pending"
        )
    claim = next(row for row in rewards.pending() if row["buyer"] == user.id)
    assert claim["url"] == "https://t.me/publicchannel/234"
    second = accounts.oauth_login("vk", "rewards-no-email", None, True)
    assert credits.wallet(second)["remaining"] == 10
    accounts.activate(second.id, "start", 30)
    assert credits.wallet(accounts.get(second.id))["remaining"] == 1010
    with pytest.raises(HTTPException):
        rewards.submit(second, post)
    rewards.review(claim["id"], "declined")
    rewards.submit(user, "https://vk.com/wall-123_456")
    new_claim = next(row for row in rewards.pending() if row["buyer"] == user.id)
    with pytest.raises(HTTPException):
        rewards.review(claim["id"], "approved")
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: rewards.review(new_claim["id"], "approved"), range(2)))
    assert credits.wallet(user)["remaining"] == 60
    charged = credits.reserve(user, "rules", 40)
    credits.finish(charged, True)
    assert credits.wallet(user)["remaining"] == 20
    accounts.activate(user.id, "start", 30)
    assert credits.wallet(accounts.get(user.id))["remaining"] == 1020


def test_oauth_email_reward(client, monkeypatch):
    from app.services import mail

    user = accounts.oauth_login("vk", "attach-bonus-email", None, True)
    code = None

    def capture(email, value):
        nonlocal code
        code = value
        return mail.verification_letter(email, "https://example.com/")

    monkeypatch.setattr(mail, "link_email_letter", capture)
    monkeypatch.setattr(mail, "deliver", lambda _: None)
    hdr = {"Authorization": f"Bearer {accounts.make_token(user)}"}
    body = {"email": "attach@example.com"}
    assert client.post("/api/rewards/email", json=body, headers=hdr).status_code == 200
    assert (
        code
        and client.post(
            "/api/rewards/email/confirm",
            json={**body, "code": "99999999" if code != "99999999" else "11111111"},
            headers=hdr,
        ).status_code
        == 422
    )
    for _ in range(2):
        assert client.post("/api/rewards/email/confirm", json={**body, "code": code}, headers=hdr).json()["verified"]
    assert accounts.get(user.id).email == body["email"]
    assert credits.wallet(accounts.get(user.id))["remaining"] == 30


def test_existing_wallet_preserved(client, user_headers):
    user = accounts.user_from_token(user_headers["Authorization"].split()[1])
    before = credits.wallet(user)
    with db.connect() as con:
        con.execute("DELETE FROM welcome_rewards WHERE buyer=?", (user.id,))
    assert credits.wallet(user)["remaining"] == before["remaining"]
    assert rewards.overview(user)["legacy"]
