import os
import logging
from typing import Optional
from app.services.sms.base import BaseSMSProvider, SMSResult, normalize_phone_e164, mask_phone


logger = logging.getLogger(__name__)


class AWSSNSProvider(BaseSMSProvider):
    """Fallback SMS Provider using AWS SNS."""

    def __init__(self, region_name: Optional[str] = None):
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

    def send_otp(self, phone: str, otp: str, template_type: str = "registration") -> SMSResult:
        masked = mask_phone(phone)
        try:
            import boto3
            e164 = normalize_phone_e164(phone)
            sns = boto3.client("sns", region_name=self.region_name)
            resp = sns.publish(
                PhoneNumber=e164,
                Message=f"Your LETA OTP is {otp}. Valid for 2 minutes. Do not share.",
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"},
                    "AWS.SNS.SMS.SenderID": {"DataType": "String", "StringValue": "LETATEC"},
                },
            )
            msg_id = resp.get("MessageId")
            logger.info(f"SMS OTP sent via AWS SNS | phone={masked} | message_id={msg_id}")
            return SMSResult(success=True, provider="aws_sns", message_id=msg_id)
        except Exception as exc:
            logger.warning(f"AWS SNS SMS failed | phone={masked} | error={exc}")
            return SMSResult(success=False, provider="aws_sns", error=str(exc))
