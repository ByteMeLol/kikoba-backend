from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ActiveLoanSummary(BaseModel):
    amount_due: float
    next_payment_date: str


class GroupPassbookItem(BaseModel):
    group_id: int
    group_name: str
    role: str
    total_shares: int
    share_value_total: float
    social_fund_balance: float
    active_loan: Optional[ActiveLoanSummary] = None


class PassbookResponse(BaseModel):
    user_id: int
    name: str
    kyc_verified: bool
    groups: List[GroupPassbookItem]


@router.get("/me", response_model=PassbookResponse)
async def get_my_passbook():
    """
    Returns the authenticated user's digital passbook, including KYC status,
    active groups, total shares, active loans, and balances.
    """
    return PassbookResponse(
        user_id=45,
        name="Amina Juma",
        kyc_verified=True,
        groups=[
            GroupPassbookItem(
                group_id=101,
                group_name="Mavuno Women Group",
                role="member",
                total_shares=15,
                share_value_total=75000.0,
                social_fund_balance=10000.0,
                active_loan=ActiveLoanSummary(
                    amount_due=50000.0,
                    next_payment_date="2026-09-14"
                )
            )
        ]
    )
