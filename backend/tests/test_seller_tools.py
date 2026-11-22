import base64
import json
import time

import httpx
import pytest

from app.services import accounts, billing, db, payout_gateway, wb_audit
from tests.conftest import CONSENT, PASSWORD, jpeg_bytes, link_token, make_cover


def admin_headers(client):
    login = client.post("/api/admin/login", json={"password": "test-password"})
    return {"Authorization": "Bearer " + login.json()["token"]}


def test_editor_visibility_and_conflicts(client, anon, user_headers):
    admin = admin_headers(client)
    endpoint = "/api/admin/articles"
    assert client.get(endpoint, headers=user_headers).status_code == 401
    data = {
        "title": "Тест редактора",
        "summary": "Описание",
        "slug": "test-editor",
        "body": "## Заголовок\n<script>test()</script>",
    }
    draft = client.post(endpoint, json=data, headers=admin).json()
    url = "/articles/test-editor"
    assert anon.get(url).status_code == 404 and url not in anon.get("/sitemap.xml").text
    address = f"{endpoint}/{draft['id']}"
    published = client.put(address, json={**draft, "published": True}, headers=admin).json()
    result = anon.get(url)
    assert result.status_code == 200 and "<h2>Заголовок</h2>" in result.text and "<script>" not in result.text
    assert url in anon.get("/articles").text and url in anon.get("/sitemap.xml").text
    assert client.put(address, json=draft, headers=admin).status_code == 409
    assert client.put(address, json={**published, "published": False}, headers=admin).status_code == 200
    assert anon.get(url).status_code == 404


@pytest.mark.parametrize("periods,price", [(3, 2673), (6, 4752)])
def test_long_payment_and_partner_workflow(client, user_headers, monkeypatch, periods, price):
    dashboard = client.post("/api/partner/join", headers=user_headers).json()
    email = f"invite{periods}@example.com"
    registration = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, **CONSENT, "referral": dashboard["code"]}
    )
    assert registration.status_code == 200
    token = client.post("/api/auth/verify", json={"token": link_token(email, "verify")}).json()["token"]
    buyer = {"Authorization": "Bearer " + token}
    pid = f"term-{periods}"

    def make(user, email, plan, total, description):
        assert total == price and str(30 * periods) in description
        return pid, "pending", "https://bank.test/pay"

    monkeypatch.setattr(billing, "provider", lambda: "yookassa")
    monkeypatch.setattr(billing, "_yookassa_checkout", make)
    monkeypatch.setattr(billing, "_fetch", lambda *_: ("succeeded", True, price))
    assert (
        client.post("/api/billing/checkout", headers=buyer, json={"plan": "start", "periods": periods}).status_code
        == 200
    )
    assert billing.confirm(pid) and not billing.confirm(pid)
    user = accounts.find(email)
    assert 30 * periods - 0.01 < (user.pro_until - time.time()) / 86400 <= 30 * periods
    with monkeypatch.context() as changed_config:
        changed_config.setattr(accounts, "find_plan", lambda _: {"limits": {"analyze": 0}})
        assert accounts.limits(user)["analyze"] > 0
    accounts.spend(user, "analyze")
    assert accounts.usage(user)["analyze"] == 1
    later = time.time() + 30 * 86400
    with monkeypatch.context() as clock:
        clock.setattr(accounts.time, "time", lambda: later)
        assert accounts.usage(accounts.find(email))["analyze"] == 0
    accounts.activate(user.id, "agency", 30)
    assert accounts.get(user.id).plan == "start"
    assert accounts.upcoming(user.id)[0]["plan"] == "agency"
    with monkeypatch.context() as clock:
        clock.setattr(accounts.time, "time", lambda: user.pro_until + 1)
        assert accounts.get(user.id).plan == "agency"
    balance = client.get("/api/partner", headers=user_headers).json()
    assert balance["buyers"] == 1 and balance["available"] == price * 15

    def payout():
        return client.post("/api/partner/payouts", headers=user_headers, json={"details": "Счёт для теста"})

    first = payout().json()
    assert first["available"] == 0 and payout().status_code == 409
    admin = admin_headers(client)
    path = "/api/admin/payouts/" + str(first["payouts"][0]["id"])
    assert (
        client.post(path, json={"status": "declined", "reference": "Ошибка реквизитов"}, headers=admin).status_code
        == 200
    )
    second = payout().json()
    path = "/api/admin/payouts/" + str(second["payouts"][0]["id"])
    for expected in (200, 409):
        assert (
            client.post(path, json={"status": "paid", "reference": "bank-123"}, headers=admin).status_code == expected
        )
    assert payout().status_code == 409


@pytest.mark.parametrize("final_status", ["succeeded", "canceled"])
def test_sbp_transfer_recovers_after_lost_response(client, user_headers, monkeypatch, final_status):
    monkeypatch.setattr(payout_gateway, "enabled", lambda: True)
    code = client.post("/api/partner/join", headers=user_headers).json()["code"]
    with db.connect() as con:
        partner = con.execute("SELECT user_id FROM partners WHERE code=?", (code,)).fetchone()[0]
        con.execute(
            "INSERT INTO commissions(payment,partner,kopecks,at) VALUES(?,?,?,?)",
            ("sbp-" + final_status, partner, 10025, time.time()),
        )
    bank = {"bank_id": "100000000111", "name": "Тестовый банк"}
    op = {}
    posts = []

    def gateway(method, path, **kwargs):
        if path == "/sbp_banks":
            return httpx.Response(200, json={"items": [bank]})
        if method == "POST":
            posts.append(kwargs["headers"]["Idempotence-Key"])
            payload = kwargs["json"]
            assert payload["amount"] == {"value": "100.25", "currency": "RUB"}
            assert payload["payout_destination_data"]["phone"] == "79000000000"
            op.update(id="payout-test", status="pending", metadata=payload["metadata"], amount=payload["amount"])
            if len(posts) == 1:
                from app.errors import api_error

                raise api_error(503, "gateway_wait", "Потерян ответ")
        else:
            assert path == "/payouts/payout-test"
            op["status"] = final_status
        return httpx.Response(200, json=op)

    monkeypatch.setattr(payout_gateway, "_call", gateway)
    req = client.post(
        "/api/partner/payouts/sbp", headers=user_headers, json={"bank_id": bank["bank_id"], "phone": "79000000000"}
    )
    assert req.status_code == 200, req.text
    payout = req.json()["payouts"][0]["id"]
    path = f"/api/admin/payouts/{payout}/transfer"
    admin = admin_headers(client)
    assert client.post(path, headers=user_headers, json={}).status_code == 401
    assert client.post(path, headers=admin, json={}).status_code == 503
    assert client.post(path, headers=admin, json={}).status_code == 200
    assert len(posts) == 2 and posts[0] == posts[1]
    assert client.post(path, headers=admin, json={}).status_code == 200
    assert client.post(path, headers=admin, json={}).status_code == 409
    dashboard = client.get("/api/partner", headers=user_headers).json()
    assert dashboard["available"] == (0 if final_status == "succeeded" else 10025)
    assert dashboard["payouts"][0]["status"] == ("paid" if final_status == "succeeded" else "declined")


def test_market_rules_and_access(client, anon):
    assert anon.post("/api/card-rules", data={"market": "wb", "title": "№1"}).status_code == 401
    for market in ("wb", "ozon"):
        result = client.post(
            "/api/card-rules", data={"market": market, "caption": "Лучший термос №1 по продажам!", "title": "Набор №10"}
        )
        assert result.status_code == 200
        rows = result.json()["findings"]
        assert {f["match"] for f in rows} == {"№1", "Лучший"}
        assert all(f["field"] == "Обложка" for f in rows)
    assert client.post("/api/card-rules", data={"market": "wb"}).status_code == 422


def test_wb_throttle_and_denied_token_leave_partial_report(client, user_headers, monkeypatch):
    claims = {"acc": 1, "exp": time.time() + 1000, "s": (1 << 30) | 2}

    def token(values):
        return "h." + base64.urlsafe_b64encode(json.dumps(values).encode()).decode().rstrip("=") + ".s"

    for wrong in ({"acc": 3}, {"s": 2}, {"exp": 1}):
        assert (
            client.post("/api/wb/audits", headers=user_headers, json={"token": token({**claims, **wrong})}).status_code
            == 422
        )
    run = client.post("/api/wb/audits", headers=user_headers, json={"token": token(claims)}).json()["id"]
    responses = iter([httpx.Response(429, headers={"X-Ratelimit-Retry": "60"}), httpx.Response(403)])
    with httpx.Client(transport=httpx.MockTransport(lambda _: next(responses))) as transport:
        assert wb_audit.step(transport)
        with db.connect() as con:
            row = con.execute("SELECT * FROM wb_audits WHERE id=?", (run,)).fetchone()
            assert row["next_at"] > time.time() + 58 and row["status"] == "import" and row["token"]
            con.execute("UPDATE wb_audits SET next_at=0 WHERE id=?", (run,))
        assert wb_audit.step(transport)
    result = client.get(f"/api/wb/audits/{run}", headers=user_headers).json()
    assert result["status"] == "error" and result["total"] == 0
    with db.connect() as con:
        assert con.execute("SELECT token FROM wb_audits WHERE id=?", (run,)).fetchone()[0] is None


def test_catalog_pages_ocr_and_private_export(client, user_headers, monkeypatch):
    monkeypatch.setattr(wb_audit, "PAGE_SIZE", 2)
    claims = (
        base64.urlsafe_b64encode(json.dumps({"acc": 1, "exp": time.time() + 3600, "s": (1 << 30) | 2}).encode())
        .decode()
        .rstrip("=")
    )
    token = f"header.{claims}.sig"

    def page(request):
        if request.method == "GET":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=jpeg_bytes(make_cover()))
        assert request.headers["Authorization"] == token
        settings = json.loads(request.content)["settings"]
        assert settings["filter"] == {"withPhoto": 0}
        if "nmID" not in settings["cursor"]:
            cards = [
                {"nmID": 1, "title": "Лучший", "vendorCode": "=SUM(1)", "photos": []},
                {"nmID": 2, "title": "Чашка", "photos": [{"big": "https://basket-01.wbbasket.ru/2.webp"}]},
            ]
        else:
            assert settings["cursor"]["nmID"] == 2
            cards = [{"nmID": 3, "description": "Термос"}]
        return httpx.Response(
            200, json={"cards": cards, "cursor": {"total": len(cards), "nmID": cards[-1]["nmID"], "updatedAt": "t"}}
        )

    # Фоновый воркер будет ждать next_at; шаги ниже выполняются с тестовым HTTP-транспортом.
    created = client.post("/api/wb/audits", headers=user_headers, json={"token": token})
    assert created.status_code == 200, created.text
    run = created.json()["id"]
    endpoint = f"/api/wb/audits/{run}"
    assert client.get(endpoint).status_code == 404
    assert client.get(endpoint + "/export", headers=user_headers).status_code == 409
    monkeypatch.setattr(wb_audit, "read_cover", lambda image: ("хит продаж", "Текст распознан"))
    with httpx.Client(transport=httpx.MockTransport(page)) as transport:
        for _ in range(4):
            with db.connect() as con:
                con.execute("UPDATE wb_audits SET next_at=0 WHERE id=?", (run,))
            wb_audit.step(transport)
    result = client.get(endpoint, headers=user_headers).json()
    assert result["status"] == "done" and result["total"] == result["checked"] == 3
    assert result["items"][1]["score"] is not None
    csv = client.get(endpoint + "/export", headers=user_headers).text
    assert "'=SUM(1)" in csv and "хит продаж" in csv
    with db.connect() as con:
        assert con.execute("SELECT token FROM wb_audits WHERE id=?", (run,)).fetchone()[0] is None
