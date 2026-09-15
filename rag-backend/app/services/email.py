"""
Shared Resend email helper.

Extracted from app.api.auth's original _send_email_otp (the email-OTP
login path) rather than duplicated — payments.py needs the exact same
"POST to Resend, log, never raise" logic for payment receipts, and two
copies of that request-building code drifting apart is exactly how a
"works here, silently doesn't work there" bug gets introduced later.
"""
import os
import logging
import requests as _requests

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_ADDRESS = "LETA TEC <noreply@letatec.com>"


def send_email(to: str, subject: str, html: str) -> bool:
    """
    Sends an email via Resend. Returns True on success, False on ANY
    failure (missing key, network error, non-2xx response) — never
    raises. Callers where email is a nice-to-have on top of something
    that already succeeded (a payment receipt after the plan is already
    activated, an OTP that also has a phone-based path) should treat a
    False return as non-fatal, same as this function treats every
    failure mode internally.
    """
    if not RESEND_API_KEY:
        logger.warning(f"RESEND_API_KEY missing — email not sent (to={to}, subject={subject!r})")
        return False
    try:
        response = _requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": FROM_ADDRESS, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Email sent | to={to} | subject={subject!r}")
        return True
    except Exception as e:
        logger.error(f"Email sending failed | to={to} | subject={subject!r} | {e}")
        return False
