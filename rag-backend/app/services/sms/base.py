import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SMSResult:
    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


def normalize_phone_10_digits(phone: str) -> str:
    """Extract standard 10-digit Indian mobile number."""
    digits = re.sub(r"\D", "", phone.strip())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def normalize_phone_e164(phone: str) -> str:
    """Normalize Indian phone number to E.164 format (+91XXXXXXXXXX)."""
    digits = normalize_phone_10_digits(phone)
    return f"+91{digits}"


def mask_phone(phone: str) -> str:
    """Mask phone number for safe structured logging (e.g., ***1234)."""
    digits = normalize_phone_10_digits(phone)
    if len(digits) >= 4:
        return f"***{digits[-4:]}"
    return "***"


class BaseSMSProvider(ABC):
    """Abstract base class for SMS gateway providers."""

    @abstractmethod
    def send_otp(self, phone: str, otp: str, template_type: str = "registration") -> SMSResult:
        """
        Send an OTP message to the specified phone number.
        
        Args:
            phone: 10-digit Indian phone number or E.164 phone string.
            otp: Exactly 6-digit numeric OTP string.
            template_type: Purpose of OTP (default: 'registration').
            
        Returns:
            SMSResult containing delivery status.
        """
        pass
