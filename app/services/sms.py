import logging

logger = logging.getLogger("sms_service")


async def send_sms_notification(phone_number: str, message: str) -> bool:
    """
    Dispatches SMS via external SMS gateway (e.g. Beem Africa, NextSMS, Twilio).
    In development/testing, logs the message.
    """
    logger.info(f"[SMS Gateway] Sent to {phone_number}: {message}")
    return True
