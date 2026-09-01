import os
import logging
from typing import Optional, List

from app.services.sms.base import BaseSMSProvider, SMSResult, mask_phone
from app.services.sms.airtel import AirtelSMSProvider
from app.services.sms.sns_provider import AWSSNSProvider
from app.services.sms.fast2sms_provider import Fast2SMSProvider
from app.services.sms.mock_provider import MockSMSProvider

logger = logging.getLogger(__name__)


class SMSService:
    """
    Unified SMS Dispatcher Service.
    Selects primary provider based on configuration with transparent fallback support.
    """

    def __init__(
        self,
        primary_provider_name: Optional[str] = None,
        custom_provider: Optional[BaseSMSProvider] = None,
    ):
        self.dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
        self.provider_name = (
            primary_provider_name or os.getenv("SMS_PROVIDER", "airtel")
        ).lower()

        self.custom_provider = custom_provider
        self.airtel_provider = AirtelSMSProvider()
        self.sns_provider = AWSSNSProvider()
        self.fast2sms_provider = Fast2SMSProvider()
        self.mock_provider = MockSMSProvider(simulate_success=True)

    def get_provider_chain(self) -> List[BaseSMSProvider]:
        """Determine ordered chain of SMS providers based on configuration."""
        if self.custom_provider:
            return [self.custom_provider]

        if self.dev_mode:
            return [self.mock_provider]

        if self.provider_name == "airtel":
            # Primary Airtel -> Fallback AWS SNS -> Fallback Fast2SMS
            return [self.airtel_provider, self.sns_provider, self.fast2sms_provider]
        elif self.provider_name == "sns":
            return [self.sns_provider, self.fast2sms_provider]
        elif self.provider_name == "fast2sms":
            return [self.fast2sms_provider]
        elif self.provider_name == "mock":
            return [self.mock_provider]
        else:
            logger.warning(f"Unknown SMS_PROVIDER '{self.provider_name}' — defaulting to Airtel with fallbacks")
            return [self.airtel_provider, self.sns_provider, self.fast2sms_provider]

    def send_otp(self, phone: str, otp: str, template_type: str = "registration") -> SMSResult:
        """
        Dispatch OTP via configured provider chain.
        Fails over to secondary providers if the primary provider fails or is unconfigured.
        """
        masked = mask_phone(phone)
        providers = self.get_provider_chain()
        last_result = SMSResult(
            success=False,
            provider="none",
            error="No SMS providers available",
        )

        for provider in providers:
            provider_name = getattr(provider, "__class__", {}).__name__
            try:
                res = provider.send_otp(phone, otp, template_type=template_type)
                if res.success:
                    return res
                last_result = res
                logger.warning(
                    f"SMS Provider {res.provider} failed for phone={masked}: {res.error}. Attempting fallback..."
                )
            except Exception as exc:
                logger.error(
                    f"Exception in SMS provider {provider_name} for phone={masked}: {exc}"
                )
                last_result = SMSResult(
                    success=False,
                    provider=provider_name.lower(),
                    error=str(exc),
                )

        logger.error(f"All SMS providers failed to dispatch OTP to phone={masked}")
        return last_result


# Singleton instance
default_sms_service = SMSService()


def send_sms_otp(phone: str, otp: str, template_type: str = "registration") -> SMSResult:
    """Convenience function to send OTP SMS via default service."""
    return default_sms_service.send_otp(phone, otp, template_type=template_type)
