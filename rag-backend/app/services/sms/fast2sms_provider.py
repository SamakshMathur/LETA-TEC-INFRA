import os
import logging
import requests
from typing import Optional
from app.services.sms.base import BaseSMSProvider, SMSResult, normalize_phone_10_digits, mask_phone

logger = logging.getLogger(__name__)


class Fast2SMSProvider(BaseSMSProvider):
    """Fallback SMS Provider using Fast2SMS."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FAST2SMS_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "ci-placeholder")

    def send_otp(self, phone: str, otp: str, template_type: str = "registration") -> SMSResult:
        masked = mask_phone(phone)
        if not self.is_configured():
            logger.warning(f"FAST2SMS_API_KEY missing or placeholder — skipping Fast2SMS for phone={masked}")
            return SMSResult(success=False, provider="fast2sms", error="FAST2SMS_API_KEY missing")

        clean_phone = normalize_phone_10_digits(phone)
        try:
            resp = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={
                    "authorization": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "route": "otp",
                    "variables_values": otp,
                    "numbers": clean_phone,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"SMS OTP sent via Fast2SMS | phone={masked}")
            return SMSResult(success=True, provider="fast2sms", status_code=resp.status_code)
        except Exception as exc:
            logger.warning(f"Fast2SMS delivery failed | phone={masked} | error={exc}")
            return SMSResult(success=False, provider="fast2sms", error=str(exc))
