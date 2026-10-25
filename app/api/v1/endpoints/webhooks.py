from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel, Field

router = APIRouter()


class PaymentWebhookPayload(BaseModel):
    transaction_reference: str = Field(..., examples=["tx-8989"])
    status: str = Field(..., examples=["SUCCESS"])
    amount: float = Field(..., examples=[17000.0])


class WebhookResponse(BaseModel):
    acknowledged: bool = True


def send_sms_receipt_task(transaction_reference: str, amount: float):
    """Background task to dispatch SMS receipt without delaying the webhook response."""
    # Logic to send SMS via SMS gateway
    pass


@router.post("/payments", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def payment_gateway_callback(payload: PaymentWebhookPayload, background_tasks: BackgroundTasks):
    """
    Webhook for Selcom/ClickPesa.
    Updates transaction status (for shares, fines, or loan repayments) and queues an SMS receipt.
    """
    background_tasks.add_task(send_sms_receipt_task, payload.transaction_reference, payload.amount)
    return WebhookResponse(acknowledged=True)
