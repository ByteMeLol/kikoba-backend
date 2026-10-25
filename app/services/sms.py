import logging
import uuid
import httpx
from app.core.config import settings

logger = logging.getLogger("sms_service")


async def send_sms_notification(phone_number: str, message: str) -> bool:
    """
    Dispatches real SMS via messaging-service.co.tz API.
    Converts numbers like '+255716718040' or '0716718040' to '255716718040'.
    """
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    if clean_phone.startswith("0"):
        clean_phone = "255" + clean_phone[1:]

    payload = {
        "to": clean_phone,
        "text": message,
        "reference": uuid.uuid4().hex[:8]
    }

    headers = {
        "Authorization": f"Bearer {settings.SMS_GATEWAY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.SMS_GATEWAY_URL,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"[SMS Gateway] Dispatched successfully to {clean_phone}: {response.text}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"[SMS Gateway Error] HTTP {e.response.status_code} sending to {clean_phone}: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"[SMS Gateway Exception] Failed sending to {clean_phone}: {str(e)}")
        return False
