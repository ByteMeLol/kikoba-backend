import logging
import httpx
from typing import Dict, Any
from app.core.config import settings
from app.services.sms import send_sms_notification

logger = logging.getLogger("payment_service")


async def initiate_mobile_money_ussd_push(
    phone_number: str,
    amount: float,
    reference: str,
    description: str = "VICOBA deposit"
) -> Dict[str, Any]:
    """
    Initiates Mobile Money USSD Push (STK Push) to user's phone via ClickPesa/Selcom gateway.
    Also dispatches SMS notification to alert user to confirm prompt on their phone.
    """
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    if clean_phone.startswith("0"):
        clean_phone = "255" + clean_phone[1:]

    logger.info(
        f"[Payment Gateway] Initiating USSD Push for TZS {amount:,.2f} to {clean_phone} (Ref: {reference})"
    )

    # In development or if mock key is configured
    if settings.PAYMENT_GATEWAY_API_KEY in ("mock_key", "", "none"):
        logger.info(
            f"[Payment Gateway - DEV MOCK] USSD Push prompt sent to {clean_phone} for TZS {amount:,.2f}. "
            f"Simulate payment callback via POST /api/v1/webhooks/payments with reference '{reference}'"
        )
        await send_sms_notification(
            phone_number,
            f"USSD Push initiated for TZS {amount:,.2f} ({description}). Please confirm PIN on your phone."
        )
        return {
            "success": True,
            "status": "pending_payment",
            "reference": reference,
            "channel": "mobile_money_ussd_push",
            "mode": "mock"
        }

    # Live gateway call (ClickPesa / Selcom API)
    headers = {
        "Authorization": f"Bearer {settings.PAYMENT_GATEWAY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "phone_number": clean_phone,
        "amount": amount,
        "currency": "TZS",
        "reference": reference,
        "description": description
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            endpoint = f"{settings.PAYMENT_GATEWAY_URL.rstrip('/')}/v1/ussd-push"
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[Payment Gateway] Live USSD Push dispatched successfully to {clean_phone}: {data}")

            await send_sms_notification(
                phone_number,
                f"USSD Push initiated for TZS {amount:,.2f} ({description}). Please confirm PIN on your phone."
            )
            return {"success": True, "status": "pending_payment", "data": data}
    except Exception as e:
        logger.error(f"[Payment Gateway Error] USSD Push dispatch failed for {clean_phone}: {str(e)}")
        # Notify user via SMS regardless
        await send_sms_notification(
            phone_number,
            f"USSD Push requested for TZS {amount:,.2f} ({description}). Please check your phone."
        )
        return {"success": False, "status": "error", "error": str(e)}


async def disburse_b2c_payout(
    phone_number: str,
    amount: float,
    reference: str,
    description: str = "VICOBA loan disbursement"
) -> Dict[str, Any]:
    """
    Dispatches B2C Mobile Money payout to the member's wallet.
    """
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    if clean_phone.startswith("0"):
        clean_phone = "255" + clean_phone[1:]

    logger.info(
        f"[Payment Gateway] Disbursing B2C payout of TZS {amount:,.2f} to {clean_phone} (Ref: {reference})"
    )

    if settings.PAYMENT_GATEWAY_API_KEY in ("mock_key", "", "none"):
        logger.info(f"[Payment Gateway - DEV MOCK] B2C Payout of TZS {amount:,.2f} to {clean_phone} simulated.")
        await send_sms_notification(
            phone_number,
            f"Your loan of TZS {amount:,.2f} has been approved and disbursed. Ref: {reference}"
        )
        return {"success": True, "status": "disbursed", "reference": reference}

    headers = {
        "Authorization": f"Bearer {settings.PAYMENT_GATEWAY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "phone_number": clean_phone,
        "amount": amount,
        "currency": "TZS",
        "reference": reference,
        "description": description
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            endpoint = f"{settings.PAYMENT_GATEWAY_URL.rstrip('/')}/v1/b2c-payout"
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            await send_sms_notification(
                phone_number,
                f"Your loan of TZS {amount:,.2f} has been approved and disbursed. Ref: {reference}"
            )
            return {"success": True, "status": "disbursed", "data": resp.json()}
    except Exception as e:
        logger.error(f"[Payment Gateway Error] B2C Payout failed: {str(e)}")
        return {"success": False, "status": "error", "error": str(e)}
