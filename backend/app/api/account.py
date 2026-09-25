"""Аккаунт покупателя и оплата подписки."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..errors import api_error
from ..ratelimit import client_ip, login_limit
from ..services import accounts, billing
from .deps import current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


def _me(user: accounts.User) -> dict:
    return {
        "email": user.email,
        "plan": user.plan,
        "pro_until": user.pro_until or None,
        "usage": accounts.usage(user),
        "limits": accounts.limits(user.plan),
    }


def _session(user: accounts.User) -> dict:
    return {"token": accounts.make_token(user), "user": _me(user)}


@router.post("/auth/register")
async def register(body: Credentials, request: Request) -> dict:
    login_limit.check(client_ip(request))
    try:
        user = await asyncio.to_thread(accounts.register, body.email, body.password)
    except accounts.AccountError as exc:
        login_limit.hit(client_ip(request))  # перебор чужих email тоже притормаживаем
        raise api_error(422, "bad_account", str(exc)) from exc
    return await asyncio.to_thread(_session, user)


@router.post("/auth/login")
async def login(body: Credentials, request: Request) -> dict:
    ip = client_ip(request)
    login_limit.check(ip)  # засчитываем только неудачные попытки
    try:
        user = await asyncio.to_thread(accounts.login, body.email, body.password)
    except accounts.AccountError as exc:
        login_limit.hit(ip)
        await asyncio.sleep(0.8)
        raise api_error(401, "bad_password", str(exc)) from exc
    return await asyncio.to_thread(_session, user)


@router.get("/auth/me")
def me(user: accounts.User | None = Depends(current_user)) -> dict:
    if user is None:
        raise api_error(401, "login_required", "Войдите заново")
    return _me(user)


@router.get("/billing/plan")
def plan() -> dict:
    """Условия подписки для страницы тарифов — видны и без входа."""
    return {"enabled": billing.enabled(), **billing.plan()}


@router.post("/billing/checkout")
async def checkout(user: accounts.User | None = Depends(current_user)) -> dict:
    if user is None:
        raise api_error(401, "login_required", "Войдите, чтобы оформить подписку")
    try:
        return {"url": await asyncio.to_thread(billing.checkout, user)}
    except billing.BillingError as exc:
        raise api_error(503, "billing_unavailable", str(exc)) from exc


@router.post("/billing/webhook", include_in_schema=False)
async def webhook(request: Request) -> dict:
    """Уведомление ЮKassa. Телу не верим — платёж перепроверяется запросом к ЮKassa по id."""
    try:
        payment_id = str((await request.json())["object"]["id"])[:64]
    except (ValueError, KeyError, TypeError):
        return {"ok": True}  # не наш формат — ЮKassa повторять не нужно
    try:
        await asyncio.to_thread(billing.confirm, payment_id)
    except billing.BillingError as exc:
        # 5xx — ЮKassa повторит уведомление позже
        raise api_error(503, "billing_unavailable", str(exc)) from exc
    return {"ok": True}
