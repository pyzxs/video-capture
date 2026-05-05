from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.api.services.profile_service import get_profile, get_records, recharge


class RechargeBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)


router = APIRouter(prefix="/profile", tags=["用户信息"])


@router.get("")
def _get_profile():
    return get_profile()


@router.get("/records")
def _get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return get_records(page, page_size)


@router.post("/recharge")
def _recharge(body: RechargeBody):
    return recharge(body.code)
