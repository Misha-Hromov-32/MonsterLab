"""Аккаунты, лимиты тарифов, оплата через ЮKassa и платные инструменты — внешние сервисы подменены."""

from __future__ import annotations

import json
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import accounts, billing, db, expert, improve, mail, marketplace

from .conftest import CONSENT, OUTBOX, PASSWORD, jpeg_bytes, link_token, make_cover, verified_token


def test_register_verify_login_me(anon: TestClient) -> None:
    creds = {"email": "Anna@Example.com", "password": "пароль-подлиннее", **CONSENT}
    r = anon.post("/api/auth/register", json=creds)
    assert r.json() == {"status": "verify", "email": "anna@example.com"}

    # до подтверждения почты входа нет, даже с верным паролем
    r = anon.post("/api/auth/login", json=creds)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "email_unverified"
    # повторная регистрация до подтверждения шлёт письмо не чаще раза в минуту
    sent = len(OUTBOX)
    assert anon.post("/api/auth/register", json=creds).status_code == 200
    assert len(OUTBOX) == sent

    session = anon.post("/api/auth/verify", json={"token": link_token("anna@example.com", "verify")}).json()
    assert session["user"]["email"] == "anna@example.com" and session["token"].startswith("u2.")
    again = anon.post("/api/auth/register", json=creds)
    assert again.status_code == 422 and "уже зарегистрирован" in again.json()["detail"]["message"]

    assert anon.post("/api/auth/login", json={**creds, "password": "чужой-пароль"}).status_code == 401
    token = anon.post("/api/auth/login", json={**creds, "email": " anna@example.com"}).json()["token"]
    me = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "anna@example.com" and me["plan"] == "demo" and me["plan_title"] == "Демо"
    assert set(me["usage"]) == set(accounts.FEATURES)


def test_preregistered_password_does_not_survive_verification(anon: TestClient) -> None:
    """Захват до регистрации: чужой человек занимает адрес своим паролем, владелец регистрируется
    и подтверждает почту. Пароль чужого после этого не должен открывать аккаунт."""
    email = "victim@example.com"
    attacker = {"email": email, "password": "пароль-захватчика", **CONSENT}
    owner = {"email": email, "password": "пароль-владельца", **CONSENT}
    assert anon.post("/api/auth/register", json=attacker).status_code == 200
    assert anon.post("/api/auth/register", json=owner).status_code == 200

    r = anon.post("/api/auth/verify", json={"token": link_token(email, "verify")})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "set_password" and "token" not in body
    assert anon.post("/api/auth/login", json=attacker).status_code == 401
    assert anon.post("/api/auth/login", json=owner).status_code == 401  # пароль задаётся заново

    session = anon.post("/api/auth/reset", json={"token": body["reset"], "password": owner["password"]}).json()
    assert session["user"]["email"] == email
    assert anon.post("/api/auth/login", json=attacker).status_code == 401
    assert anon.post("/api/auth/login", json=owner).status_code == 200


def test_links_are_single_use(anon: TestClient) -> None:
    anon.post("/api/auth/register", json={"email": "once@example.com", "password": PASSWORD, **CONSENT})
    token = link_token("once@example.com", "verify")
    assert anon.post("/api/auth/verify", json={"token": token}).status_code == 200
    r = anon.post("/api/auth/verify", json={"token": token})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "bad_link"
    assert anon.post("/api/auth/verify", json={"token": "x" * 43}).status_code == 422


def test_password_reset_revokes_old_sessions(anon: TestClient) -> None:
    old = verified_token(anon, "reset@example.com")
    auth = {"Authorization": f"Bearer {old}"}
    assert anon.get("/api/auth/me", headers=auth).status_code == 200

    # на неизвестный адрес ответ тот же, но письма нет
    sent = len(OUTBOX)
    assert anon.post("/api/auth/forgot", json={"email": "nobody@example.com"}).json() == {"ok": True}
    assert len(OUTBOX) == sent
    assert anon.post("/api/auth/forgot", json={"email": "Reset@example.com"}).json() == {"ok": True}
    token = link_token("reset@example.com", "reset")

    short = anon.post("/api/auth/reset", json={"token": token, "password": "123"})
    assert short.status_code == 422  # короткий пароль ссылку не гасит
    r = anon.post("/api/auth/reset", json={"token": token, "password": "новый-пароль-1"})
    assert r.status_code == 200 and r.json()["token"]

    assert anon.get("/api/auth/me", headers=auth).status_code == 401  # старый вход отозван
    assert anon.post("/api/auth/login", json={"email": "reset@example.com", "password": PASSWORD}).status_code == 401
    ok = anon.post("/api/auth/login", json={"email": "reset@example.com", "password": "новый-пароль-1"})
    assert ok.status_code == 200


def test_email_and_password_are_not_stored_in_clear(anon: TestClient) -> None:
    verified_token(anon, "secret.buyer@example.com")
    raw = (config.DATA_DIR / "app.sqlite").read_bytes()
    assert b"secret.buyer" not in raw and PASSWORD.encode() not in raw
    with db.connect() as con:
        row = con.execute("SELECT password FROM users ORDER BY id DESC LIMIT 1").fetchone()
    assert row["password"].startswith("$argon2id$")


def test_letter_is_html_with_inline_logo() -> None:
    msg = mail.verification_letter("a&b@example.com", "https://site.test/?verify=abc")
    html = msg.get_body(("html",)).get_content()
    assert "https://site.test/?verify=abc" in html and "cid:logo" in html
    assert "a&amp;b@example.com" in html  # данные в шаблоне экранируются
    assert "{{" not in html
    assert any(part.get_content_type() == "image/png" for part in msg.walk())
    assert "https://site.test/?verify=abc" in msg.get_body(("plain",)).get_content()


def test_reply_to_goes_to_configured_mailbox(monkeypatch) -> None:
    letter = mail.verification_letter("a@example.com", "https://x/?verify=t")
    assert letter["Reply-To"] is None
    monkeypatch.setattr(config, "MAIL_REPLY_TO", "hello@example.com")
    assert mail.verification_letter("a@example.com", "https://x/?verify=t")["Reply-To"] == "hello@example.com"


def test_resend_is_throttled(anon: TestClient) -> None:
    anon.post("/api/auth/register", json={"email": "slow@example.com", "password": PASSWORD, **CONSENT})
    sent = len(OUTBOX)
    assert anon.post("/api/auth/resend", json={"email": "slow@example.com"}).json() == {"ok": True}
    assert len(OUTBOX) == sent  # минута ещё не прошла


def test_mail_failure_is_reported_and_retryable(anon: TestClient, monkeypatch) -> None:
    def broken(msg) -> None:
        raise mail.MailError("Не удалось отправить письмо. Попробуйте через пару минут.")

    monkeypatch.setattr(mail, "deliver", broken)
    r = anon.post("/api/auth/register", json={"email": "later@example.com", "password": PASSWORD, **CONSENT})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "mail_failed"
    monkeypatch.setattr(mail, "deliver", OUTBOX.append)
    # ссылка из неотправленного письма отозвана — повторить можно сразу, без минуты ожидания
    assert anon.post("/api/auth/resend", json={"email": "later@example.com"}).status_code == 200
    assert link_token("later@example.com", "verify")


@pytest.mark.parametrize("token", ["", "u2.1.9999999999.bad", "u1.1.9999999999.bad", "u2.x.y.z", "admin-token"])
def test_bad_user_tokens(client: TestClient, token: str) -> None:
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_short_password_and_bad_email() -> None:
    with pytest.raises(accounts.AccountError):
        accounts.register("не-почта", "достаточно-длинный", True)
    with pytest.raises(accounts.AccountError):
        accounts.register("ok@example.com", "123", True)


@pytest.mark.parametrize("consent", [{}, {"accept_terms": True}, {"accept_personal_data": True}])
def test_registration_needs_both_consents(anon: TestClient, consent: dict) -> None:
    sent = len(OUTBOX)
    r = anon.post("/api/auth/register", json={"email": "noconsent@example.com", "password": PASSWORD, **consent})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "consent_required"
    assert len(OUTBOX) == sent and accounts.find("noconsent@example.com") is None


def test_consent_is_recorded_with_legal_version(anon: TestClient) -> None:
    verified_token(anon, "consent@example.com")
    user = accounts.find("consent@example.com")
    with db.connect() as con:
        row = con.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    assert row["terms_accepted_at"] and row["pd_consent_at"] and row["legal_version"] == accounts.LEGAL_VERSION
    legal = anon.get("/api/public/legal").json()
    assert legal["version"] == accounts.LEGAL_VERSION
    assert {"operator", "name", "inn", "ogrn", "address", "email"} <= set(legal)


def _upload(client: TestClient) -> str:
    files = {"file": ("c.jpg", jpeg_bytes(make_cover(3)), "image/jpeg")}
    return client.post("/api/analyze", files=files).json()["id"]


def test_improve_spends_limit_only_on_success(client: TestClient, user_headers: dict, monkeypatch) -> None:
    monkeypatch.setattr(expert, "current_config", lambda: expert.ExpertConfig("key", "https://x.test/v1", ["m"]))
    calls = []

    def fake_generate(jpeg: bytes, prompt: str) -> bytes:
        calls.append(prompt)
        if len(calls) == 1:
            raise improve.ImproveError("сбой")
        return jpeg_bytes(make_cover(9))

    monkeypatch.setattr(improve, "generate", fake_generate)
    image_id = _upload(client)
    first = client.post("/api/improve", json={"id": image_id}, headers=user_headers)
    assert first.status_code == 502  # сбой модели лимит не тратит
    body = {"id": image_id, "issues": ["мелкий текст — укрупнить"]}
    ok = client.post("/api/improve", json=body, headers=user_headers)
    assert ok.status_code == 200 and ok.json()["image"].startswith("data:image/jpeg;base64,")
    assert "мелкий текст" in calls[-1]
    # на бесплатном тарифе — одно улучшение в день
    again = client.post("/api/improve", json={"id": image_id}, headers=user_headers)
    assert again.status_code == 403 and again.json()["detail"]["code"] == "limit_reached"


def test_competitors_from_marketplace(client: TestClient, user_headers: dict, monkeypatch) -> None:
    async def fake_search(query: str, limit: int) -> list[dict]:
        path = marketplace.image_path(marketplace.query_key(query), "123456")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(jpeg_bytes(make_cover(5)))
        return [{"id": "123456", "brand": "Бренд", "name": "Термос"}]

    monkeypatch.setattr(marketplace, "search", fake_search)
    body = client.get("/api/competitors", params={"query": "термос"}, headers=user_headers).json()
    assert body["items"][0]["brand"] == "Бренд"
    assert client.get(body["items"][0]["url"]).headers["content-type"] == "image/jpeg"
    assert client.get("/api/competitors/files/zzzz/1.jpg").status_code == 404
    assert TestClient(client.app).get("/api/competitors", params={"query": "термос"}).status_code == 401


def test_choice_percent_sums_to_100() -> None:
    chance = expert.choice_percent({"A": 0.333, "B": 0.333, "C": 0.334})
    assert sum(chance.values()) == 100 and max(chance.values()) - min(chance.values()) <= 1


# ---------------------------------------------------------------- оплата


@pytest.fixture
def yookassa(monkeypatch) -> dict:
    """Подменённая ЮKassa: платежи живут в словаре, статус меняет сам тест."""
    payments: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        if request.method == "POST":
            body = json.loads(request.content)
            pid = f"pay-{len(payments) + 1}"
            payments[pid] = {
                "id": pid,
                "status": "pending",
                "paid": False,
                "metadata": body["metadata"],
                "amount": body["amount"],
            }
            confirmation = {"confirmation_url": f"https://pay.test/{pid}"}
            return httpx.Response(200, json={**payments[pid], "confirmation": confirmation})
        pid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=payments[pid]) if pid in payments else httpx.Response(404)

    monkeypatch.setattr(config, "YOOKASSA_SHOP_ID", "123")
    monkeypatch.setattr(config, "YOOKASSA_SECRET_KEY", "test")
    real = httpx.Client
    monkeypatch.setattr(billing.httpx, "Client", lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    return payments


def test_payment_activates_plan_once(client: TestClient, user_headers: dict, yookassa: dict) -> None:
    body = client.post("/api/billing/checkout", json={"plan": "start"}, headers=user_headers).json()
    pid = body["url"].rsplit("/", 1)[-1]
    assert yookassa[pid]["metadata"]["plan"] == "start"

    # уведомление до оплаты и уведомление о чужом платеже ничего не меняют
    client.post("/api/billing/webhook", json={"object": {"id": pid}})
    client.post("/api/billing/webhook", json={"object": {"id": "чужой"}})
    assert client.get("/api/auth/me", headers=user_headers).json()["plan"] == "demo"

    yookassa[pid].update(status="succeeded", paid=True)
    for _ in range(2):  # ЮKassa может прислать уведомление повторно
        assert client.post("/api/billing/webhook", json={"object": {"id": pid}}).status_code == 200
    me = client.get("/api/auth/me", headers=user_headers).json()
    assert me["plan"] == "start" and me["plan_title"] == "Старт"
    assert 29 * 86400 < me["pro_until"] - time.time() <= 30 * 86400  # продлено ровно один раз
    assert me["limits"]["improve"] == 10
    assert set(me["usage"].values()) == {0}  # квоты тарифа начинаются заново, демо-расход не переносится


@pytest.fixture
def tochka(monkeypatch) -> dict:
    """Подменённая Точка: операции живут в словаре, статус меняет сам тест; запросы складываются в sent."""
    ops: dict[str, dict] = {}
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer jwt-test"
        if request.method == "POST":
            body = json.loads(request.content)
            sent.append({"path": request.url.path, **body})
            oid = f"op-{uuid.uuid4()}"  # как в Точке: id операций уникальны, а база общая на весь прогон
            ops[oid] = {"operationId": oid, "status": "CREATED", "amount": body["Data"]["amount"]}
            link = {"paymentLink": f"https://merch.tochka.test/{oid}"}
            return httpx.Response(200, json={"Data": {**ops[oid], **link}})
        oid = request.url.path.rsplit("/", 1)[-1]
        if oid not in ops:
            return httpx.Response(404, json={"code": "404"})
        return httpx.Response(200, json={"Data": {"Operation": [ops[oid]]}})

    for name, value in {
        "PAYMENT_PROVIDER": "tochka",
        "TOCHKA_JWT": "jwt-test",
        "TOCHKA_CUSTOMER_CODE": "300000001",
        "TOCHKA_MERCHANT_ID": "200000000000001",
        "TOCHKA_RECEIPT": True,
    }.items():
        monkeypatch.setattr(config, name, value)
    real = httpx.Client
    monkeypatch.setattr(billing.httpx, "Client", lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    return {"ops": ops, "sent": sent}


def _jwt(payload: dict) -> bytes:
    """Уведомление Точки — JWT; подпись сервис не проверяет (платёж перепроверяется в банке)."""
    import base64

    part = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return b"eyJhbGciOiJSUzI1NiJ9." + part + b".c2lnbg"


def test_tochka_payment_with_receipt_activates_plan_once(client: TestClient, user_headers: dict, tochka: dict) -> None:
    body = client.post("/api/billing/checkout", json={"plan": "start"}, headers=user_headers).json()
    oid = body["url"].rsplit("/", 1)[-1]
    req = tochka["sent"][-1]
    assert req["path"].endswith("/acquiring/v1.0/payments_with_receipt")
    data = req["Data"]
    assert data["customerCode"] == "300000001" and data["merchantId"] == "200000000000001"
    assert data["paymentMode"] == ["sbp", "card"] and data["redirectUrl"].endswith("/?payment=return")
    assert data["Client"]["email"] and data["Items"][0]["paymentObject"] == "service"
    assert data["Items"][0]["amount"] == data["amount"]

    hook = _jwt({"webhookType": "acquiringInternetPayment", "operationId": oid, "status": "APPROVED"})
    # уведомлению «оплачено» не верим, пока банк не подтвердит
    assert client.post("/api/billing/webhook", content=hook).status_code == 200
    assert client.get("/api/auth/me", headers=user_headers).json()["plan"] == "demo"

    tochka["ops"][oid]["status"] = "APPROVED"
    for _ in range(2):  # повторное уведомление не продлевает тариф второй раз
        assert client.post("/api/billing/webhook", content=hook).status_code == 200
    me = client.get("/api/auth/me", headers=user_headers).json()
    assert me["plan"] == "start"
    with db.connect() as con:
        assert con.execute("SELECT applied, provider FROM payments WHERE id = ?", (oid,)).fetchone()[:] == (1, "tochka")


def test_account_without_email_gives_email_for_receipt(client: TestClient, tochka: dict) -> None:
    user = accounts.oauth_login("vk", "vk-no-mail", None, True)
    auth = {"Authorization": f"Bearer {accounts.make_token(user)}"}
    r = client.post("/api/billing/checkout", json={"plan": "start"}, headers=auth)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "email_required"
    assert client.post("/api/billing/checkout", json={"plan": "start", "email": "чек"}, headers=auth).status_code == 422
    r = client.post("/api/billing/checkout", json={"plan": "start", "email": "Buyer@Gmail.com"}, headers=auth)
    assert r.status_code == 200 and tochka["sent"][-1]["Data"]["Client"]["email"] == "buyer@gmail.com"


def test_tochka_underpaid_operation_is_not_applied(client: TestClient, tochka: dict) -> None:
    token = verified_token(client)
    auth = {"Authorization": f"Bearer {token}"}
    oid = client.post("/api/billing/checkout", json={"plan": "pro"}, headers=auth).json()["url"].rsplit("/", 1)[-1]
    tochka["ops"][oid].update(status="APPROVED", amount=1.0)
    client.post("/api/billing/webhook", content=_jwt({"operationId": oid}))
    assert client.get("/api/auth/me", headers=auth).json()["plan"] == "demo"


def test_return_from_payment_checks_without_webhook(client: TestClient, anon: TestClient, tochka: dict) -> None:
    token = verified_token(client)
    auth = {"Authorization": f"Bearer {token}"}
    oid = client.post("/api/billing/checkout", json={"plan": "start"}, headers=auth).json()["url"].rsplit("/", 1)[-1]
    assert client.post("/api/billing/check", headers=auth).json()["activated"] is False
    tochka["ops"][oid]["status"] = "APPROVED"
    r = client.post("/api/billing/check", headers=auth).json()
    assert r["activated"] is True and r["user"]["plan"] == "start"
    assert anon.post("/api/billing/check").status_code == 401


def test_webhook_ignores_garbage(client: TestClient) -> None:
    for body in (b"", b"not a jwt", b"a.b.c", b"{}", b'{"object": {}}'):
        assert client.post("/api/billing/webhook", content=body).status_code == 200


def test_unknown_plan_is_rejected(client: TestClient, user_headers: dict, yookassa: dict) -> None:
    r = client.post("/api/billing/checkout", json={"plan": "gold"}, headers=user_headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "bad_plan"


def test_checkout_without_shop_is_503(client: TestClient, user_headers: dict) -> None:
    r = client.post("/api/billing/checkout", json={"plan": "start"}, headers=user_headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "billing_unavailable"


def test_demo_quota_is_lifetime_and_counts_analysis(anon: TestClient) -> None:
    auth = {"Authorization": f"Bearer {verified_token(anon)}"}
    files = {"file": ("c.jpg", jpeg_bytes(make_cover(4)), "image/jpeg")}
    demo = anon.get("/api/billing/plans").json()["demo"]["analyze"]
    for _ in range(demo):
        assert anon.post("/api/analyze", files=files, headers=auth).status_code == 200
    r = anon.post("/api/analyze", files=files, headers=auth)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "limit_reached"
    assert "Демо-доступ" in r.json()["detail"]["message"]
    assert anon.get("/api/auth/me", headers=auth).json()["usage"]["analyze"] == demo


def test_foreign_email_is_refused_russian_is_accepted(anon: TestClient) -> None:
    for foreign in ("someone@gmail.com", "someone@outlook.com", "someone@proton.me"):
        r = anon.post("/api/auth/register", json={"email": foreign, "password": PASSWORD, **CONSENT})
        assert r.status_code == 422 and r.json()["detail"]["message"] == "Регистрация на эту почту недоступна"
    for russian in ("Someone@Yandex.ru", "someone@mail.ru", "someone@rambler.ru"):
        r = anon.post("/api/auth/register", json={"email": russian, "password": PASSWORD, **CONSENT})
        assert r.status_code == 200, r.text


def test_disposable_email_is_refused(anon: TestClient) -> None:
    r = anon.post("/api/auth/register", json={"email": "x@mailinator.com", "password": PASSWORD, **CONSENT})
    assert r.status_code == 422 and "Временные" in r.json()["detail"]["message"]


def test_admin_sets_plans(client: TestClient) -> None:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    before = client.get("/api/billing/plans").json()
    quota = {"analyze": 50, "shelf": 5, "expert": 5, "choice": 3, "improve": 2, "competitors": 4}
    plan = {"id": "solo", "title": "Соло", "price_rub": 1490, "period_days": 30, "limits": quota}
    body = {"demo": {**quota, "improve": 0}, "plans": [plan]}
    try:
        assert client.put("/api/admin/billing", json=body, headers=headers).status_code == 200
        got = client.get("/api/billing/plans").json()
        assert got["plans"][0]["price_rub"] == 1490 and got["demo"]["improve"] == 0 and got["enabled"] is False
        bad = {**body, "plans": [{**plan, "price_rub": 0}]}
        assert client.put("/api/admin/billing", json=bad, headers=headers).status_code == 422
        twins = {**body, "plans": [plan, plan]}
        assert client.put("/api/admin/billing", json=twins, headers=headers).status_code == 422
    finally:  # остальные тесты рассчитывают на тарифы по умолчанию
        restore = {"demo": before["demo"], "plans": before["plans"]}
        assert client.put("/api/admin/billing", json=restore, headers=headers).status_code == 200


def test_unreadable_email_means_signed_out_not_500(anon: TestClient) -> None:
    token = verified_token(anon, "broken@example.com")
    user = accounts.find("broken@example.com")
    with db.connect() as con:  # как будто сменили MASTER_KEY: шифртекст больше не сходится
        con.execute("UPDATE users SET email_enc = ? WHERE id = ?", (b"\x00" * 40, user.id))
    assert anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_stats_counts_runs_and_visits(client: TestClient, anon: TestClient) -> None:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    before = client.get("/api/admin/stats", headers=headers).json()
    anon.get("/api/public/site")
    anon.get("/api/public/site", params={"preview": "true"})  # предпросмотр из админки не считается
    files = {"file": ("c.jpg", jpeg_bytes(make_cover(6)), "image/jpeg")}
    assert client.post("/api/analyze", files=files).status_code == 200
    after = client.get("/api/admin/stats", headers=headers).json()

    runs = {f["feature"]: f for f in after["features"]}
    was = {f["feature"]: f for f in before["features"]}
    assert runs["analyze"]["today"] == was["analyze"]["today"] + 1
    assert after["daily"][-1]["visits"] == before["daily"][-1]["visits"] + 1
    assert len(after["daily"]) == 30 and after["users"]["total"] >= 1
    assert any(u["email"] == "session@example.com" and u["plan"] == "Агентство" for u in after["latest_users"])
    assert anon.get("/api/admin/stats").status_code == 401
