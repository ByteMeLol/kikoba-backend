from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.transaction import Transaction
from app.models.loan import Loan

router = APIRouter()


class ActiveLoanSummary(BaseModel):
    amount_due: float
    next_payment_date: Optional[str] = None


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
async def get_my_passbook(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the authenticated user's digital passbook, including KYC status,
    active groups, total shares, active loans, and balances calculated from the ledger.
    """
    # Fetch group memberships with group details
    stmt = (
        select(GroupMember)
        .options(selectinload(GroupMember.group))
        .where(GroupMember.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    group_items: List[GroupPassbookItem] = []

    for m in memberships:
        # Calculate shares & social fund from transactions
        tx_stmt = select(
            func.coalesce(func.sum(Transaction.shares_bought), 0),
            func.coalesce(func.sum(Transaction.social_fund_amount), 0.0)
        ).where(
            Transaction.member_id == m.id,
            Transaction.status == "SUCCESS"
        )
        tx_result = await db.execute(tx_stmt)
        total_shares, social_fund_balance = tx_result.one()

        share_val = float(m.group.share_value) if m.group else 5000.0
        share_value_total = float(total_shares) * share_val

        # Check for active loan
        loan_stmt = select(Loan).where(
            Loan.member_id == m.id,
            Loan.status == "disbursed"
        ).order_by(Loan.id.desc())
        loan_result = await db.execute(loan_stmt)
        active_loan_obj = loan_result.scalars().first()

        active_loan_summary = None
        if active_loan_obj:
            amount_due = float(active_loan_obj.total_due) - float(active_loan_obj.amount_repaid)
            next_date_str = active_loan_obj.due_date.isoformat() if active_loan_obj.due_date else None
            active_loan_summary = ActiveLoanSummary(
                amount_due=max(0.0, amount_due),
                next_payment_date=next_date_str
            )

        group_items.append(
            GroupPassbookItem(
                group_id=m.group_id,
                group_name=m.group.name if m.group else "Group",
                role=m.role,
                total_shares=int(total_shares),
                share_value_total=float(share_value_total),
                social_fund_balance=float(social_fund_balance),
                active_loan=active_loan_summary
            )
        )

    return PassbookResponse(
        user_id=current_user.id,
        name=current_user.full_name,
        kyc_verified=current_user.kyc_verified,
        groups=group_items
    )
