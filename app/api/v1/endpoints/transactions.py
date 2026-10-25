import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, verify_group_membership
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.meeting import Meeting
from app.models.transaction import Transaction
from app.services.sms import send_sms_notification

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
async def record_deposit(
    group_id: int,
    payload: DepositRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiates a deposit for shares and social fund.
    Enforces maximum shares per meeting limit (bylaw).
    Triggers Mobile Money USSD Push to the member's phone.
    """
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Verify meeting exists
    meeting = await db.get(Meeting, payload.meeting_id)
    if not meeting or meeting.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found for this group")

    # Verify member exists in group
    member = await db.get(GroupMember, payload.member_id)
    if not member or member.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this group")

    # Business rule: Shares exceed max meeting limit
    if payload.shares_bought > group.max_shares_per_meeting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shares bought ({payload.shares_bought}) exceeds maximum allowed per meeting ({group.max_shares_per_meeting})"
        )

    share_cost = float(payload.shares_bought) * float(group.share_value)
    total_amount = share_cost + float(payload.social_fund_amount)
    tx_ref = f"tx-{uuid.uuid4().hex[:8]}"

    tx = Transaction(
        reference_id=tx_ref,
        group_id=group_id,
        member_id=payload.member_id,
        meeting_id=payload.meeting_id,
        type="share_purchase",
        amount=total_amount,
        shares_bought=payload.shares_bought,
        social_fund_amount=payload.social_fund_amount,
        payment_method=payload.payment_method,
        status="pending_payment"
    )
    db.add(tx)
    await db.commit()

    # Trigger USSD Push in background
    member_user = await db.get(User, member.user_id)
    if member_user:
        background_tasks.add_task(
            send_sms_notification,
            member_user.phone_number,
            f"USSD Push initiated for TZS {total_amount:,.2f} (VICOBA deposit). Please confirm PIN on your phone."
        )

    return DepositResponse(transaction_id=tx_ref, status="pending_payment")
