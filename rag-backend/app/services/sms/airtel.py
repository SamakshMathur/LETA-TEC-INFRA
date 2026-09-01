import os
import logging
import requests
from typing import Optional, Dict, Any

from app.services.sms.base import BaseSMSProvider, SMSResult, normalize_phone_10_digits, mask_phone

logger = logging.getLogger(__name__)

# Registered Airtel DLT Regulatory Constants
AIRTEL_DLT_PE_ID = "1001355597545597385"
AIRTEL_DLT_HEADER = "LTATEC"
AIRTEL_DLT_HEADER_ID = "1005169685880415720"
AIRTEL_DLT_REGISTRATION_TEMPLATE_ID = "1077380560017332633"
AIRTEL_DLT_REGISTRATION_TEMPLATE = (
    "Your LETATEC verification code is {otp}. This OTP is used to verify your identity "
    "during account registration. It is valid for 2 minutes. Do not share this OTP with anyone."
)


class AirtelSMSProvider(BaseSMSProvider):
    """
    Production Airtel SMS Gateway Provider with DLT compliance.
    Integrates with Airtel IQ / Airtel Enterprise SMS Gateway.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        customer_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sender_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        self.api_url = api_url or os.getenv(
            "AIRTEL_SMS_URL",
            "https://iqsms.airtel.in/gateway/airtel-iq-sms-utility/bulk-sms"
        )
        self.customer_id = customer_id or os.getenv("AIRTEL_CUSTOMER_ID", "")
        self.api_key = api_key or os.getenv("AIRTEL_API_KEY", "")
        self.api_secret = api_secret or os.getenv("AIRTEL_API_SECRET", "")
        self.sender_id = sender_id or os.getenv("AIRTEL_SENDER_ID", AIRTEL_DLT_HEADER)
        self.entity_id = entity_id or os.getenv("AIRTEL_ENTITY_ID", AIRTEL_DLT_PE_ID)
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        """Check if required Airtel credentials and endpoints are present."""
        return bool(self.api_url and (self.customer_id or self.api_key))

    def build_payload(self, phone: str, otp: str, template_type: str = "registration") -> Dict[str, Any]:
        """Construct the DLT-compliant payload for Airtel SMS Gateway."""
        clean_phone = normalize_phone_10_digits(phone)
        # Format destination address with 91 country code prefix if needed
        msisdn = f"91{clean_phone}" if len(clean_phone) == 10 else clean_phone

        # Select approved DLT template
        template_id = AIRTEL_DLT_REGISTRATION_TEMPLATE_ID
        message_body = AIRTEL_DLT_REGISTRATION_TEMPLATE.format(otp=otp)

        payload = {
            "customerId": self.customer_id,
            "sourceAddress": self.sender_id,
            "destinationAddress": [msisdn],
            "message": message_body,
            "entityId": self.entity_id,
            "dltTemplateId": template_id,
            "messageType": "SERVICE_IMPLICIT",
        }
        return payload

    def send_otp(self, phone: str, otp: str, template_type: str = "registration") -> SMSResult:
        """
        Send DLT-compliant OTP via Airtel SMS Gateway.
        Logs delivery status without exposing OTP or credentials.
        """
        masked = mask_phone(phone)
        if not self.is_configured():
            logger.warning(f"Airtel SMS credentials not configured — skipping Airtel delivery for phone={masked}")
            return SMSResult(
                success=False,
                provider="airtel",
                error="Airtel SMS credentials not configured",
            )

        payload = self.build_payload(phone, otp, template_type)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Auth header construction
        auth = None
        if self.customer_id and self.api_secret:
            auth = (self.customer_id, self.api_secret)
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            logger.info(f"Dispatching DLT OTP via Airtel SMS Gateway | phone={masked} | template_id={AIRTEL_DLT_REGISTRATION_TEMPLATE_ID}")
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                auth=auth,
                timeout=self.timeout_seconds,
            )

            status_code = response.status_code
            if 200 <= status_code < 300:
                resp_json = {}
                try:
                    resp_json = response.json()
                except Exception:
                    pass
                msg_id = resp_json.get("messageId") or resp_json.get("msgId") or resp_json.get("requestId")
                logger.info(f"Airtel SMS delivered successfully | phone={masked} | status={status_code} | message_id={msg_id}")
                return SMSResult(
                    success=True,
                    provider="airtel",
                    message_id=str(msg_id) if msg_id else None,
                    status_code=status_code,
                )
            else:
                logger.error(f"Airtel SMS Gateway returned error | phone={masked} | status={status_code}")
                return SMSResult(
                    success=False,
                    provider="airtel",
                    status_code=status_code,
                    error=f"Airtel HTTP {status_code}: {response.text[:200]}",
                )

        except requests.exceptions.Timeout:
            logger.error(f"Airtel SMS Gateway request timed out | phone={masked}")
            return SMSResult(
                success=False,
                provider="airtel",
                error="Airtel SMS request timed out",
            )
        except requests.exceptions.RequestException as exc:
            logger.error(f"Airtel SMS Gateway connection error | phone={masked} | error={type(exc).__name__}")
            return SMSResult(
                success=False,
                provider="airtel",
                error=f"Airtel connection error: {type(exc).__name__}",
            )
        except Exception as exc:
            logger.error(f"Unexpected error sending Airtel SMS | phone={masked} | error={type(exc).__name__}")
            return SMSResult(
                success=False,
                provider="airtel",
                error=f"Unexpected error: {str(exc)}",
            )
