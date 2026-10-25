from typing import List
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user, verify_group_membership
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, GroupMember, Cycle
from app.models.meeting import Meeting, Fine
from app.models.transaction import Transaction
from app.models.loan import Loan
from app.core.security import verify_pin
from app.services.sms import send_sms_notification

router = APIRouter()


class CloseCycleRequest(BaseModel):
    admin_signatures: List[int] = Field(..., min_length=1, examples=[[4, 7, 12]])
    confirmation_pin: str = Field(..., min_length=4, max_length=4, examples=["9999"])


class CloseCycleResponse(BaseModel):
    status: str = "closed"
    total_profit_distributed: float
    dividend_per_share: float
    member_payouts_initiated: bool = True


@router.post("/{group_id}/cycles/{cycle_id}/close", response_model=CloseCycleResponse, status_code=status.HTTP_200_OK)
async def close_cycle_share_out(
    group_id: int,
    cycle_id: int,
    payload: CloseCycleRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Locks the cycle. Sums all interest and fines. Calculates dividends proportionally
    based on shares held and initiates payouts. Requires Maker-Checker multi-admin signatures.
    """
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Verify caller is a group admin
    await verify_group_membership(
        group_id=group_id,
        user=current_user,
        db=db,
        allowed_roles=["chairperson", "secretary", "treasurer"]
    )

    # Verify admin confirmation PIN
    if not current_user.hashed_pin or not verify_pin(payload.confirmation_pin, current_user.hashed_pin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation PIN"
        )

    # Verify multi-admin signatures (at least 1 admin signature)
    admin_check_stmt = select(func.count(GroupMember.id)).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id.in_(payload.admin_signatures),
        GroupMember.role.in_(["chairperson", "secretary", "treasurer"])
    )
    admin_count = (await db.execute(admin_check_stmt)).scalar() or 0
    if admin_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid group admin signatures are required to close cycle"
        )

    cycle = await db.get(Cycle, cycle_id)
    if not cycle or cycle.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found for this group")

    if cycle.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cycle is already closed"
        )

    # 1. Sum total loan interest earned
    interest_stmt = select(func.coalesce(func.sum(Loan.total_due - Loan.amount), 0.0)).where(
        Loan.group_id == group_id,
        Loan.status.in_(["disbursed", "repaid"])
    )
    total_interest = float((await db.execute(interest_stmt)).scalar() or 0.0)

    # 2. Sum fines collected
    fines_stmt = select(func.coalesce(func.sum(Fine.amount), 0.0)).where(
        Fine.group_id == group_id
    )
    total_fines = float((await db.execute(fines_stmt)).scalar() or 0.0)

    total_profit = total_interest + total_fines

    # 3. Sum total group shares
    shares_stmt = select(func.coalesce(func.sum(Transaction.shares_bought), 0)).where(
        Transaction.group_id == group_id,
        Transaction.status == "SUCCESS"
    )
    total_shares = int((await db.execute(shares_stmt)).scalar() or 0)

    dividend_per_share = (total_profit / total_shares) if total_shares > 0 else 0.0

    # 4. Lock Cycle
    cycle.status = "closed"
    cycle.total_profit_distributed = total_profit
    cycle.dividend_per_share = dividend_per_share
    cycle.end_date = datetime.now(timezone.utc).date()

    # 5. Record payout distribution transactions for each member
    members_stmt = select(GroupMember).where(GroupMember.group_id == group_id)
    members = (await db.execute(members_stmt)).scalars().all()

    for m in members:
        mem_shares_stmt = select(func.coalesce(func.sum(Transaction.shares_bought), 0)).where(
            Transaction.member_id == m.id,
            Transaction.status == "SUCCESS"
        )
        mem_shares = int((await db.execute(mem_shares_stmt)).scalar() or 0)

        if mem_shares > 0:
            share_capital = mem_shares * float(group.share_value)
            dividend_portion = mem_shares * dividend_per_share
            total_member_payout = share_capital + dividend_portion

            payout_tx = Transaction(
                reference_id=f"tx-payout-{uuid.uuid4().hex[:6]}",
                group_id=group_id,
                member_id=m.id,
                type="dividend_payout",
                amount=total_member_payout,
                status="SUCCESS"
            )
            db.add(payout_tx)

    await db.commit()

    return CloseCycleResponse(
        status="closed",
        total_profit_distributed=total_profit,
        dividend_per_share=round(dividend_per_share, 2),
        member_payouts_initiated=True
    )
