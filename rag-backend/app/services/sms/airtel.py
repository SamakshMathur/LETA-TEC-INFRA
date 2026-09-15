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

# Payment-receipt SMS — DELIBERATELY a separate, empty-by-default template
# id. DLT requires every distinct message WORDING to be pre-registered
# with the telecom operator before it can be sent at all; the receipt
# text is different wording than the OTP template above, so it needs its
# own registration and its own approved id, which doesn't exist yet.
# Until AIRTEL_DLT_RECEIPT_TEMPLATE_ID is set (once that registration is
# approved), send_transactional() degrades safely — see its own docstring.
AIRTEL_DLT_RECEIPT_TEMPLATE_ID = os.getenv("AIRTEL_DLT_RECEIPT_TEMPLATE_ID", "")


class AirtelSMSProvider(BaseSMSProvider):
    """
    Production Airtel SMS Gateway Provider with DLT compliance.
    Integrates with Airtel IQ / Airtel Enterprise SMS Gateway.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        customer_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sender_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        self.api_url = api_url or os.getenv(
            "AIRTEL_SMS_URL",
            "https://iqsms.airtel.in/api/v1/send-prepaid-sms"
        )
        self.customer_id = customer_id or os.getenv("AIRTEL_CUSTOMER_ID", "")
        self.username = username or os.getenv("AIRTEL_USERNAME") or self.customer_id
        self.api_secret = api_secret or os.getenv("AIRTEL_API_SECRET", "")
        self.password = password or os.getenv("AIRTEL_PASSWORD") or self.api_secret
        self.api_key = api_key or os.getenv("AIRTEL_API_KEY", "")
        self.sender_id = sender_id or os.getenv("AIRTEL_SENDER_ID", AIRTEL_DLT_HEADER)
        self.entity_id = entity_id or os.getenv("AIRTEL_ENTITY_ID", AIRTEL_DLT_PE_ID)
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        """Check if required Airtel credentials and endpoints are present."""
        has_basic_auth = bool(self.customer_id and (self.password or self.api_secret))
        has_bearer_auth = bool(self.api_key)
        return bool(self.api_url and (has_basic_auth or has_bearer_auth))

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
        if not self.is_configured():
            masked = mask_phone(phone)
            logger.warning(f"Airtel SMS credentials not configured — skipping Airtel delivery for phone={masked}")
            return SMSResult(
                success=False,
                provider="airtel",
                error="Airtel SMS credentials not configured",
            )
        payload = self.build_payload(phone, otp, template_type)
        return self._dispatch(phone, payload, log_template_id=AIRTEL_DLT_REGISTRATION_TEMPLATE_ID)

    def send_transactional(self, phone: str, template_id: str, message: str) -> SMSResult:
        """
        Send an already-DLT-approved transactional message that ISN'T an
        OTP (a payment receipt, for example). Unlike send_otp, this
        doesn't select a template itself — the caller supplies both the
        exact registered template_id and the exact final message text,
        since (unlike OTP, which only ever has one shape) there's no
        single fixed wording for every kind of transactional message this
        could ever send.

        Returns a clean failure (not an exception, not an HTTP call) when
        template_id is empty — the expected state until that template's
        DLT registration is actually approved and its id configured.
        """
        masked = mask_phone(phone)
        if not template_id:
            logger.info(f"No DLT template configured for this message type — skipping SMS for phone={masked}")
            return SMSResult(success=False, provider="airtel", error="No DLT template_id configured for this message type")
        if not self.is_configured():
            logger.warning(f"Airtel SMS credentials not configured — skipping Airtel delivery for phone={masked}")
            return SMSResult(success=False, provider="airtel", error="Airtel SMS credentials not configured")

        clean_phone = normalize_phone_10_digits(phone)
        msisdn = f"91{clean_phone}" if len(clean_phone) == 10 else clean_phone
        payload = {
            "customerId": self.customer_id,
            "sourceAddress": self.sender_id,
            "destinationAddress": [msisdn],
            "message": message,
            "entityId": self.entity_id,
            "dltTemplateId": template_id,
            "messageType": "SERVICE_IMPLICIT",
        }
        return self._dispatch(phone, payload, log_template_id=template_id)

    def _dispatch(self, phone: str, payload: Dict[str, Any], log_template_id: str) -> SMSResult:
        """Shared HTTP dispatch for both send_otp and send_transactional —
        same auth-header construction, same response handling, same error
        cases either way; only the payload (and which DLT template it
        declares) differs between an OTP and any other transactional SMS."""
        masked = mask_phone(phone)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        auth = None
        resolved_user = self.username or self.customer_id
        resolved_pass = self.password or self.api_secret
        if resolved_user and resolved_pass:
            auth = (resolved_user, resolved_pass)
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            logger.info(f"Dispatching SMS via Airtel Gateway | phone={masked} | template_id={log_template_id}")
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
