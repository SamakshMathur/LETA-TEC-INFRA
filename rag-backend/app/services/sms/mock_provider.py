import logging
from typing import List, Dict, Any
from app.services.sms.base import BaseSMSProvider, SMSResult, mask_phone

logger = logging.getLogger(__name__)


class MockSMSProvider(BaseSMSProvider):
    """Mock SMS Provider for unit tests and local development."""

    def __init__(self, simulate_success: bool = True):
        self.simulate_success = simulate_success
        self.sent_messages: List[Dict[str, Any]] = []

    def send_otp(self, phone: str, otp: str, template_type: str = "registration") -> SMSResult:
        masked = mask_phone(phone)
        if self.simulate_success:
            self.sent_messages.append({
                "phone": phone,
                "otp": otp,
                "template_type": template_type,
            })
            logger.info(f"[MOCK SMS] OTP dispatched | phone={masked} | template={template_type}")
            return SMSResult(
                success=True,
                provider="mock",
                message_id=f"mock_msg_{len(self.sent_messages)}",
                status_code=200,
            )
        else:
            logger.warning(f"[MOCK SMS] Simulated failure | phone={masked}")
            return SMSResult(
                success=False,
                provider="mock",
                error="Simulated provider delivery failure",
                status_code=500,
            )
