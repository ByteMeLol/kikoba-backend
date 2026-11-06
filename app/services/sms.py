import logging
import httpx
from app.core.config import settings

logger = logging.getLogger("sms_service")


async def send_sms_notification(phone_number: str, message: str) -> bool:
    """
    Dispatches SMS via Elive API (message.elive.co.tz).
    Converts numbers like '+255716718040' or '0716718040' to '255716718040'.
    Logs clearly for development/testing so testers are never locked out if SMS credentials are missing or failing.
    """
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    if clean_phone.startswith("0"):
        clean_phone = "255" + clean_phone[1:]

    payload = {
        "senderId": getattr(settings, "SMS_SENDER_ID", "VICOBA"),
        "messageType": "text",
        "message": message,
        "contacts": clean_phone,
        "deliveryReportUrl": getattr(settings, "ELIVE_DELIVERY_REPORT_URL", "")
    }

    api_key = getattr(settings, "ELIVE_API_KEY", "")
    api_secret = getattr(settings, "ELIVE_API_SECRET", "")

    # If mock / unconfigured credentials in dev environment
    if not api_key or api_key in ("mock_key", "mock_sms_key", "YOUR_API_KEY", ""):
        logger.info(f"[ELIVE SMS DEV MOCK] Dispatched to {clean_phone}: '{message}'")
        return True

    headers = {
        "Content-Type": "application/json",
        "api_key": api_key,
        "api_secret": api_secret
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.SMS_GATEWAY_URL,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"[Elive SMS Gateway] Dispatched successfully to {clean_phone}: {response.text}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"[Elive SMS Error] HTTP {e.response.status_code} sending to {clean_phone}: {e.response.text}")
        if settings.DEBUG or settings.ENVIRONMENT == "development":
            logger.warning(
                f"[ELIVE SMS DEV FALLBACK] Gateway delivery failed ({e.response.status_code}). Message for {clean_phone}: '{message}'"
            )
        return False
    except Exception as e:
        logger.error(f"[Elive SMS Exception] Failed sending to {clean_phone}: {str(e)}")
        if settings.DEBUG or settings.ENVIRONMENT == "development":
            logger.warning(
                f"[ELIVE SMS DEV FALLBACK] Exception during dispatch. Message for {clean_phone}: '{message}'"
            )
        return False
