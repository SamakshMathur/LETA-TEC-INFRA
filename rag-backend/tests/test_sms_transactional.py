"""
Tests for the new non-OTP transactional SMS path (send_transactional),
added so payment receipts can reach phone-only signups who have no email
on file — the OTP path (send_otp) is unaffected and not re-tested here.

India's DLT rules require every distinct SMS wording to be pre-registered
with the telecom operator before it can be sent at all, separately per
wording — a payment receipt needs its own approved template_id, distinct
from the OTP one already in use. AIRTEL_DLT_RECEIPT_TEMPLATE_ID is empty
until that registration is approved; these tests pin that send_transactional
degrades to a clean, logged no-op in that state instead of either crashing
or (worse) attempting to send with no valid template and getting the
account penalized by the carrier for non-compliant traffic.
"""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ANTHROPIC_API_KEY",   "ci-placeholder")
os.environ.setdefault("MONGODB_URI",         "mongodb://localhost:27017/ci_test")
os.environ.setdefault("SECRET_KEY",          "ci-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",           "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET", "ci-placeholder")
os.environ.setdefault("DEV_MODE",            "true")


def test_send_transactional_is_a_clean_noop_with_no_template_id():
    """The expected state right now — no real DLT template registered yet.
    Must not attempt an HTTP call at all, and must not raise."""
    from app.services.sms.airtel import AirtelSMSProvider

    provider = AirtelSMSProvider(customer_id="cust", password="pass")
    with patch("app.services.sms.airtel.requests.post") as mock_post:
        result = provider.send_transactional("9876543210", "", "some message")

    assert result.success is False
    mock_post.assert_not_called()


def test_send_transactional_sends_with_a_real_template_id():
    from app.services.sms.airtel import AirtelSMSProvider

    provider = AirtelSMSProvider(customer_id="cust", password="pass")
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {"messageId": "msg_123"}

    with patch("app.services.sms.airtel.requests.post", return_value=mock_response) as mock_post:
        result = provider.send_transactional("9876543210", "template_abc", "Your receipt: pay_123")

    assert result.success is True
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["dltTemplateId"] == "template_abc"
    assert call_kwargs["json"]["message"] == "Your receipt: pay_123"


def test_send_transactional_handles_gateway_error_without_raising():
    from app.services.sms.airtel import AirtelSMSProvider

    provider = AirtelSMSProvider(customer_id="cust", password="pass")
    mock_response = MagicMock(status_code=500, text="Internal error")

    with patch("app.services.sms.airtel.requests.post", return_value=mock_response):
        result = provider.send_transactional("9876543210", "template_abc", "message")

    assert result.success is False


def test_send_transactional_requires_configured_credentials():
    from app.services.sms.airtel import AirtelSMSProvider

    provider = AirtelSMSProvider(customer_id="", password="")  # unconfigured
    with patch("app.services.sms.airtel.requests.post") as mock_post:
        result = provider.send_transactional("9876543210", "template_abc", "message")

    assert result.success is False
    mock_post.assert_not_called()


def test_sms_service_send_transactional_uses_mock_in_dev_mode(monkeypatch):
    from app.services.sms.sms_service import SMSService

    monkeypatch.setenv("DEV_MODE", "true")
    service = SMSService()
    result = service.send_transactional("9876543210", "template_abc", "message")

    assert result.success is True
    assert result.provider == "mock"
    assert service.mock_provider.sent_messages[-1]["template_id"] == "template_abc"
