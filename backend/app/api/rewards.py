from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..errors import api_error
from ..ratelimit import client_ip, mail_limit
from ..services import accounts, mail, rewards
from .deps import require_admin, require_user

router = APIRouter(prefix="/api")


class Email(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class EmailCode(Email):
    code: str = Field(pattern=r"^[0-9]{8}$")


@router.post("/rewards/email")
def send_email(body: Email, request: Request, user: accounts.User = Depends(require_user)):
    mail_limit.hit(client_ip(request))
    try:
        accounts.send_link_email(user, body.email)
    except accounts.AccountError as exc:
        raise api_error(422, "email_error", str(exc)) from exc
    except mail.MailError as exc:
        raise api_error(503, "mail_unavailable", "Письмо не отправилось. Попробуйте ещё раз.") from exc
    return {"ok": True}


@router.post("/rewards/email/confirm")
def confirm_email(body: EmailCode, user: accounts.User = Depends(require_user)):
    try:
        accounts.confirm_link_email(user, body.email, body.code)
    except accounts.AccountError as exc:
        raise api_error(422, "email_error", str(exc)) from exc
    return rewards.overview(accounts.get(user.id))


class Post(BaseModel):
    url: str = Field(max_length=500)


class Decision(BaseModel):
    status: Literal["approved", "declined"]


@router.get("/rewards")
def overview(user: accounts.User = Depends(require_user)):
    return rewards.overview(user)


@router.post("/rewards/share")
def share(body: Post, user: accounts.User = Depends(require_user)):
    rewards.submit(user, body.url)
    return rewards.overview(user)


@router.get("/admin/shares", dependencies=[Depends(require_admin)])
def queue():
    return rewards.pending()


@router.post("/admin/shares/{claim}", dependencies=[Depends(require_admin)])
def moderate(claim: int, body: Decision):
    rewards.review(claim, body.status)
    return {"ok": True}
