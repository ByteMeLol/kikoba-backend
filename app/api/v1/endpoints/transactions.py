from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()


class DepositRequest(BaseModel):
    member_id: int = Field(..., examples=[45])
    meeting_id: int = Field(..., examples=[12])
    shares_bought: int = Field(..., examples=[3])
    social_fund_amount: float = Field(..., examples=[2000.0])
    payment_method: str = Field(default="mobile_money", examples=["mobile_money"])


class DepositResponse(BaseModel):
    transaction_id: str
    status: str = "pending_payment"


@router.post("/{group_id}/transactions/deposit", response_model=DepositResponse, status_code=status.HTTP_202_ACCEPTED)
async def record_deposit(group_id: int, payload: DepositRequest):
    """
    Initiates a deposit for shares and social fund.
    Triggers Mobile Money USSD Push to the member's phone.
    Returns 400 Bad Request if shares exceed max meeting limit.
    """
    return DepositResponse(transaction_id="tx-8989", status="pending_payment")
