from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.loan import Loan
from app.models.group import GroupMember
from app.models.user import User
from app.services.sms import send_sms_notification

router = APIRouter()


class PaymentWebhookPayload(BaseModel):
    transaction_reference: str = Field(..., examples=["tx-8989"])
    status: str = Field(..., examples=["SUCCESS"])
    amount: float = Field(..., examples=[17000.0])


class WebhookResponse(BaseModel):
    acknowledged: bool = True


@router.post("/payments", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def payment_gateway_callback(
    payload: PaymentWebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook callback for Selcom / ClickPesa mobile money gateway.
    Processes deposits and loan repayments idempotently and dispatches SMS receipts.
    """
    stmt = select(Transaction).where(Transaction.reference_id == payload.transaction_reference)
    result = await db.execute(stmt)
    tx = result.scalar_one_or_none()

    if not tx:
        # Acknowledge to prevent provider retries, but log unknown transaction
        return WebhookResponse(acknowledged=True)

    # Idempotency check: If already finalized, do not process again
    if tx.status == "SUCCESS":
        return WebhookResponse(acknowledged=True)

    tx.status = payload.status

    if payload.status == "SUCCESS":
        # Handle loan repayment deduction
        if tx.type == "loan_repayment" and tx.external_reference:
            try:
                loan_id = int(tx.external_reference)
                loan = await db.get(Loan, loan_id)
                if loan:
                    loan.amount_repaid = float(loan.amount_repaid) + float(payload.amount)
                    if float(loan.amount_repaid) >= float(loan.total_due):
                        loan.status = "repaid"
            except (ValueError, TypeError):
                pass

        # Trigger background SMS receipt
        member = await db.get(GroupMember, tx.member_id)
        if member:
            user = await db.get(User, member.user_id)
            if user:
                background_tasks.add_task(
                    send_sms_notification,
                    user.phone_number,
                    f"Payment of TZS {payload.amount:,.2f} confirmed for VICOBA. Ref: {payload.transaction_reference}"
                )

    await db.commit()
    return WebhookResponse(acknowledged=True)
