import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints

from ..errors import api_error
from ..services import accounts, partners, payout_gateway
from .deps import require_admin, require_user

router = APIRouter(prefix="/api")


class Requisites(BaseModel):
    details: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class SbpRequisites(BaseModel):
    phone: Annotated[str, StringConstraints(pattern=r"^7[0-9]{10}$")]
    bank_id: Annotated[str, StringConstraints(pattern=r"^[0-9]{9,15}$")]


class GatewayRequest(BaseModel):
    provider_id: Annotated[str, StringConstraints(max_length=80)] = ""


class Settlement(BaseModel):
    status: Literal["paid", "declined"]
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


@router.get("/partner")
def dashboard(user: accounts.User = Depends(require_user)) -> dict:
    return partners.dashboard(user.id)


@router.post("/partner/join")
def join(user: accounts.User = Depends(require_user)) -> dict:
    partners.join(user.id)
    return partners.dashboard(user.id)


@router.post("/partner/payouts")
def request_payout(body: Requisites, user: accounts.User = Depends(require_user)) -> dict:
    partners.request_payout(user.id, body.details)
    return partners.dashboard(user.id)


@router.get("/partner/banks")
def banks(user: accounts.User = Depends(require_user)):
    return payout_gateway.banks()


@router.post("/partner/payouts/sbp")
def sbp(body: SbpRequisites, user: accounts.User = Depends(require_user)):
    bank = next((b for b in payout_gateway.banks() if b["bank_id"] == body.bank_id), None)
    if not bank:
        raise api_error(422, "bad_bank", "Выберите банк из списка участников СБП")
    partners.request_payout(user.id, json.dumps({**body.model_dump(), "bank": bank["name"]}, ensure_ascii=False), "sbp")
    return partners.dashboard(user.id)


@router.post("/admin/payouts/{payout}/transfer", dependencies=[Depends(require_admin)])
def transfer(payout: int, body: GatewayRequest):
    payout_gateway.dispatch(payout, body.provider_id)
    return {"ok": True}


@router.get("/admin/payouts", dependencies=[Depends(require_admin)])
def payouts() -> list:
    return partners.requests()


@router.post("/admin/payouts/{payout}", dependencies=[Depends(require_admin)])
def settle(payout: int, body: Settlement) -> dict:
    partners.settle(payout, body.status, body.reference)
    return {"ok": True}
