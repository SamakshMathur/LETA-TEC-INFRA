"""Tests for the shared Resend email helper (app/services/email.py),
extracted from auth.py's original _send_email_otp so payments.py's
receipt email reuses the exact same proven request-building logic
instead of a second, potentially-drifting copy of it."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ANTHROPIC_API_KEY",   "ci-placeholder")
os.environ.setdefault("MONGODB_URI",         "mongodb://localhost:27017/ci_test")
os.environ.setdefault("SECRET_KEY",          "ci-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",           "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET", "ci-placeholder")
os.environ.setdefault("DEV_MODE",            "true")


def test_send_email_returns_false_without_raising_when_key_missing(monkeypatch):
    from app.services import email as email_module
    monkeypatch.setattr(email_module, "RESEND_API_KEY", "")

    result = email_module.send_email("user@example.com", "Subject", "<p>hi</p>")
    assert result is False


def test_send_email_returns_true_on_success(monkeypatch):
    from app.services import email as email_module
    monkeypatch.setattr(email_module, "RESEND_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch.object(email_module._requests, "post", return_value=mock_response) as mock_post:
        result = email_module.send_email("user@example.com", "Subject", "<p>hi</p>")

    assert result is True
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["to"] == ["user@example.com"]
    assert call_kwargs["json"]["subject"] == "Subject"


def test_send_email_returns_false_without_raising_on_network_error(monkeypatch):
    from app.services import email as email_module
    monkeypatch.setattr(email_module, "RESEND_API_KEY", "fake-key")

    with patch.object(email_module._requests, "post", side_effect=Exception("network down")):
        result = email_module.send_email("user@example.com", "Subject", "<p>hi</p>")

    assert result is False  # never raises — a caller that ignores the return value is still safe
