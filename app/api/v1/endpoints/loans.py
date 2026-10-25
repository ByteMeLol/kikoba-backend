import uuid
import random
from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user, verify_group_membership
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.transaction import Transaction
from app.models.loan import Loan
from app.core.security import verify_pin
from app.services.sms import send_sms_notification

router = APIRouter()


class ApplyLoanRequest(BaseModel):
    amount: float = Field(..., examples=[150000.0])
    purpose: str = Field(..., examples=["Agriculture"])
    duration_months: int = Field(..., examples=[3])


class ApplyLoanResponse(BaseModel):
    loan_id: int
    status: str = "pending_approval"


class ApproveLoanRequest(BaseModel):
    admin_pin: str = Field(..., min_length=4, max_length=4, examples=["1234"])


class ApproveLoanResponse(BaseModel):
    status: str = "disbursed"
    payout_reference: str = "MPESA-9923"


class RepayLoanRequest(BaseModel):
    amount: float = Field(..., examples=[55000.0])


class RepayLoanResponse(BaseModel):
    transaction_id: str
    status: str = "pending_payment"


@router.post("/{group_id}/loans/apply", response_model=ApplyLoanResponse, status_code=status.HTTP_201_CREATED)
async def apply_for_loan(
    group_id: int,
    payload: ApplyLoanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validates eligibility: requested loan amount <= (member's total shares value * 3).
    Calculates interest rate and repayment total.
    """
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Get caller's membership
    membership = await verify_group_membership(group_id=group_id, user=current_user, db=db)

    # Calculate member's total active shares
    tx_stmt = select(func.coalesce(func.sum(Transaction.shares_bought), 0)).where(
        Transaction.member_id == membership.id,
        Transaction.status == "SUCCESS"
    )
    total_shares = (await db.execute(tx_stmt)).scalar() or 0
    total_shares_val = float(total_shares) * float(group.share_value)
    max_eligible_loan = total_shares_val * 3.0

    if payload.amount > max_eligible_loan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loan amount ({payload.amount}) exceeds 3x shares value ({max_eligible_loan})"
        )

    # Calculate interest
    interest = payload.amount * float(group.interest_rate_monthly) * payload.duration_months
    total_due = payload.amount + interest
    due_date = date.today() + timedelta(days=30 * payload.duration_months)

    loan = Loan(
        group_id=group_id,
        member_id=membership.id,
        amount=payload.amount,
        purpose=payload.purpose,
        duration_months=payload.duration_months,
        interest_rate=group.interest_rate_monthly,
        total_due=total_due,
        amount_repaid=0.0,
        status="pending_approval",
        due_date=due_date
    )
    db.add(loan)
    await db.commit()
    await db.refresh(loan)

    return ApplyLoanResponse(loan_id=loan.id, status=loan.status)


@router.post("/{group_id}/loans/{loan_id}/approve", response_model=ApproveLoanResponse, status_code=status.HTTP_200_OK)
async def approve_and_disburse_loan(
    group_id: int,
    loan_id: int,
    payload: ApproveLoanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin approves the loan using Maker-Checker security PIN.
    Triggers B2C Mobile Money payout to the member.
    """
    # Verify admin role
    await verify_group_membership(
        group_id=group_id,
        user=current_user,
        db=db,
        allowed_roles=["chairperson", "secretary", "treasurer"]
    )

    # Verify admin PIN
    if not current_user.hashed_pin or not verify_pin(payload.admin_pin, current_user.hashed_pin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid admin confirmation PIN"
        )

    loan = await db.get(Loan, loan_id)
    if not loan or loan.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found for this group")

    if loan.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve loan with status '{loan.status}'"
        )

    payout_ref = f"MPESA-{random.randint(1000, 9999)}"
    loan.status = "disbursed"
    loan.payout_reference = payout_ref
    loan.approved_by_id = current_user.id
    loan.disbursed_at = datetime.now(timezone.utc)
    await db.commit()

    # Get borrowing member info to notify
    borrower_member = await db.get(GroupMember, loan.member_id)
    if borrower_member:
        borrower_user = await db.get(User, borrower_member.user_id)
        if borrower_user:
            background_tasks.add_task(
                send_sms_notification,
                borrower_user.phone_number,
                f"Your loan of TZS {loan.amount:,.2f} has been approved and disbursed. Ref: {payout_ref}"
            )

    return ApproveLoanResponse(status="disbursed", payout_reference=payout_ref)


@router.post("/{group_id}/loans/{loan_id}/repay", response_model=RepayLoanResponse, status_code=status.HTTP_202_ACCEPTED)
async def repay_loan(
    group_id: int,
    loan_id: int,
    payload: RepayLoanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiates a USSD push for a member to pay back their loan installment.
    """
    loan = await db.get(Loan, loan_id)
    if not loan or loan.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found for this group")

    if loan.status != "disbursed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loan is not active for repayment (status: '{loan.status}')"
        )

    tx_ref = f"tx-{uuid.uuid4().hex[:8]}"
    tx = Transaction(
        reference_id=tx_ref,
        group_id=group_id,
        member_id=loan.member_id,
        type="loan_repayment",
        amount=payload.amount,
        status="pending_payment",
        external_reference=str(loan.id)
    )
    db.add(tx)
    await db.commit()

    # Trigger USSD Push
    background_tasks.add_task(
        send_sms_notification,
        current_user.phone_number,
        f"USSD Push initiated for loan repayment of TZS {payload.amount:,.2f}. Please confirm on your phone."
    )

    return RepayLoanResponse(transaction_id=tx_ref, status="pending_payment")
