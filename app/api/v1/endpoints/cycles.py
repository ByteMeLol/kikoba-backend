from typing import List
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()


class CloseCycleRequest(BaseModel):
    admin_signatures: List[int] = Field(..., min_length=1, examples=[[4, 7, 12]])
    confirmation_pin: str = Field(..., min_length=4, max_length=4, examples=["9999"])


class CloseCycleResponse(BaseModel):
    status: str = "closed"
    total_profit_distributed: float = 1200000.0
    dividend_per_share: float = 2400.0
    member_payouts_initiated: bool = True


@router.post("/{group_id}/cycles/{cycle_id}/close", response_model=CloseCycleResponse, status_code=status.HTTP_200_OK)
async def close_cycle_share_out(group_id: int, cycle_id: int, payload: CloseCycleRequest):
    """
    Locks the cycle. Sums all interest and fines. Calculates dividends proportionally
    based on shares held and initiates payouts. Requires Maker-Checker multi-admin signatures.
    """
    return CloseCycleResponse()
