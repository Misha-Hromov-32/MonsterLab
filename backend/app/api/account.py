"""Аккаунт покупателя: регистрация с подтверждением почты, вход, сброс пароля и оплата подписки."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..errors import api_error
from ..ratelimit import analysis_limit, client_ip, login_limit, mail_limit
from ..services import accounts, billing, mail, oauth
from .deps import current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class Registration(Credentials):
    # две отдельные галочки: согласие на обработку персональных данных по закону оформляется
    # отдельно от пользовательского соглашения и политики
    accept_terms: bool = False
    accept_personal_data: bool = False


class CheckoutRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=40)


class EmailOnly(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class LinkToken(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class NewPassword(LinkToken):
    password: str = Field(min_length=1, max_length=200)


def _me(user: accounts.User) -> dict:
    plan = accounts.find_plan(user.plan)
    return {
        "email": user.email,
        "plan": user.plan,
        "plan_title": plan["title"] if plan else ("Демо" if user.plan == accounts.DEMO else "Платный"),
        "pro_until": user.pro_until if user.plan != accounts.DEMO else None,
        "usage": accounts.usage(user),
        "limits": accounts.limits(user),
    }


def _session(user: accounts.User) -> dict:
    return {"token": accounts.make_token(user), "user": _me(user)}


def _mail_failed(exc: mail.MailError):
    return api_error(503, "mail_failed", str(exc))


@router.post("/auth/register")
async def register(body: Registration, request: Request) -> dict:
    """Создаёт аккаунт и отправляет письмо со ссылкой. Войти можно только после подтверждения почты."""
    if not (body.accept_terms and body.accept_personal_data):
        raise api_error(
            422,
            "consent_required",
            "Чтобы зарегистрироваться, примите соглашение и дайте согласие на обработку персональных данных",
        )
    ip = client_ip(request)
    login_limit.check(ip)
    mail_limit.hit(ip)  # регистрация — это письмо и 64 МБ памяти на хэш пароля
    try:
        user = await asyncio.to_thread(accounts.register, body.email, body.password, True)
        await asyncio.to_thread(accounts.send_verification, user)
    except accounts.AccountError as exc:
        login_limit.hit(ip)  # перебор чужих email тоже притормаживаем
        raise api_error(422, "bad_account", str(exc)) from exc
    except mail.MailError as exc:
        raise _mail_failed(exc) from exc
    return {"status": "verify", "email": user.email}


@router.post("/auth/login")
async def login(body: Credentials, request: Request) -> dict:
    ip = client_ip(request)
    login_limit.check(ip)  # засчитываем только неудачные попытки
    try:
        user = await asyncio.to_thread(accounts.login, body.email, body.password)
    except accounts.EmailUnverified as exc:
        raise api_error(403, "email_unverified", str(exc)) from exc
    except accounts.AccountError as exc:
        login_limit.hit(ip)
        await asyncio.sleep(0.8)
        raise api_error(401, "bad_password", str(exc)) from exc
    return await asyncio.to_thread(_session, user)


class OAuthStart(BaseModel):
    accept_terms: bool = False
    accept_personal_data: bool = False


class OAuthFinish(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=10, max_length=200)
    device_id: str | None = Field(None, max_length=200)


def _provider(provider: str) -> str:
    if provider not in oauth.TITLES:
        raise api_error(404, "not_found", "Такого способа входа нет")
    return provider


@router.post("/auth/oauth/{provider}/start")
async def oauth_start(provider: str, body: OAuthStart, request: Request) -> dict:
    """Начало входа через VK ID / Яндекс ID: адрес страницы провайдера и state для сверки после возврата."""
    login_limit.check(client_ip(request))
    try:
        url, state = await asyncio.to_thread(
            oauth.start, _provider(provider), body.accept_terms and body.accept_personal_data
        )
    except oauth.OAuthError as exc:
        raise api_error(503, "oauth_unavailable", str(exc)) from exc
    return {"url": url, "state": state}


@router.post("/auth/oauth/{provider}/finish")
async def oauth_finish(provider: str, body: OAuthFinish, request: Request) -> dict:
    """Возврат от провайдера: код меняется на данные пользователя, вход — как после подтверждения почты."""
    ip = client_ip(request)
    login_limit.check(ip)
    try:
        identity = await asyncio.to_thread(oauth.finish, _provider(provider), body.code, body.state, body.device_id)
        user = await asyncio.to_thread(
            accounts.oauth_login, identity.provider, identity.subject, identity.email, identity.accepted
        )
    except oauth.OAuthError as exc:
        login_limit.hit(ip)
        raise api_error(422, "oauth_failed", str(exc)) from exc
    except accounts.ConsentRequired as exc:
        raise api_error(422, "consent_required", str(exc)) from exc
    except accounts.AccountError as exc:
        raise api_error(422, "oauth_failed", str(exc)) from exc
    return await asyncio.to_thread(_session, user)


@router.post("/auth/resend")
async def resend(body: EmailOnly, request: Request) -> dict:
    """Ещё одно письмо для подтверждения. Ответ одинаковый, есть такой аккаунт или нет."""
    mail_limit.hit(client_ip(request))
    try:
        user = await asyncio.to_thread(accounts.find, body.email)
        if user is not None:
            await asyncio.to_thread(accounts.send_verification, user)
    except mail.MailError as exc:
        raise _mail_failed(exc) from exc
    return {"ok": True}


@router.post("/auth/verify")
async def verify(body: LinkToken, request: Request) -> dict:
    """Переход по ссылке из письма: почта подтверждена — сразу выдаём вход."""
    ip = client_ip(request)
    login_limit.check(ip)
    try:
        user, reset = await asyncio.to_thread(accounts.verify_email, body.token)
    except accounts.AccountError as exc:
        login_limit.hit(ip)
        raise api_error(422, "bad_link", str(exc)) from exc
    if reset:  # на почту регистрировались несколько раз — пароль задаёт владелец почты
        return {"status": "set_password", "email": user.email, "reset": reset}
    return await asyncio.to_thread(_session, user)


@router.post("/auth/forgot")
async def forgot(body: EmailOnly, request: Request) -> dict:
    """Письмо со ссылкой для нового пароля. Ответ одинаковый, есть такой аккаунт или нет."""
    mail_limit.hit(client_ip(request))
    try:
        await asyncio.to_thread(accounts.send_reset, body.email)
    except mail.MailError as exc:
        raise _mail_failed(exc) from exc
    return {"ok": True}


@router.post("/auth/reset")
async def reset(body: NewPassword, request: Request) -> dict:
    ip = client_ip(request)
    login_limit.check(ip)
    try:
        user = await asyncio.to_thread(accounts.reset_password, body.token, body.password)
    except accounts.AccountError as exc:
        login_limit.hit(ip)
        raise api_error(422, "bad_link", str(exc)) from exc
    return await asyncio.to_thread(_session, user)


@router.get("/auth/me")
def me(user: accounts.User | None = Depends(current_user)) -> dict:
    if user is None:
        raise api_error(401, "login_required", "Войдите заново")
    return _me(user)


@router.get("/billing/plans")
def plans() -> dict:
    """Тарифы и демо-квоты для страницы тарифов — видны и без входа."""
    return {"enabled": billing.enabled(), "provider": billing.provider(), **billing.plans()}


@router.post("/billing/checkout")
async def checkout(body: CheckoutRequest, user: accounts.User | None = Depends(current_user)) -> dict:
    if user is None:
        raise api_error(401, "login_required", "Войдите, чтобы оформить подписку")
    if accounts.find_plan(body.plan) is None:
        raise api_error(422, "bad_plan", "Такого тарифа нет — обновите страницу")
    try:
        return {"url": await asyncio.to_thread(billing.checkout, user, body.plan)}
    except billing.BillingError as exc:
        raise api_error(503, "billing_unavailable", str(exc)) from exc


@router.post("/billing/check", dependencies=[Depends(analysis_limit.dependency)])
async def check_payment(user: accounts.User | None = Depends(current_user)) -> dict:
    """Возврат со страницы оплаты: перепроверить недавние платежи покупателя, не дожидаясь уведомления."""
    if user is None:
        raise api_error(401, "login_required", "Войдите заново")
    try:
        activated = await asyncio.to_thread(billing.sync_user, user)
    except billing.BillingError as exc:
        raise api_error(503, "billing_unavailable", str(exc)) from exc
    fresh = await asyncio.to_thread(accounts.get, user.id)
    return {"activated": activated, "user": _me(fresh or user)}


@router.post("/billing/webhook", include_in_schema=False)
async def webhook(request: Request) -> dict:
    """Уведомление Точки (JWT) или ЮKassa (JSON). Телу не верим — платёж перепроверяется запросом к банку по id."""
    payment_id = billing.webhook_payment_id((await request.body())[:20_000])
    if payment_id is None:
        return {"ok": True}  # не наш формат — повторять не нужно
    try:
        await asyncio.to_thread(billing.confirm, payment_id)
    except billing.BillingError as exc:
        # 5xx — ЮKassa повторит уведомление позже
        raise api_error(503, "billing_unavailable", str(exc)) from exc
    return {"ok": True}
