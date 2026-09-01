import os
import sys
import unittest
import hashlib
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.time import utc_now
from app.api.auth import (
    _generate_otp,
    OTP_EXPIRY_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_RATE_LIMIT_PER_HOUR,
    MAX_OTP_ATTEMPTS,
    SendOTPRequest,
    VerifyOTPRequest,
    send_otp,
    verify_otp,
)
from app.services.sms.base import SMSResult, normalize_phone_10_digits, mask_phone
from app.services.sms.airtel import (
    AirtelSMSProvider,
    AIRTEL_DLT_PE_ID,
    AIRTEL_DLT_HEADER,
    AIRTEL_DLT_HEADER_ID,
    AIRTEL_DLT_REGISTRATION_TEMPLATE_ID,
    AIRTEL_DLT_REGISTRATION_TEMPLATE,
)
from app.services.sms.sms_service import SMSService, default_sms_service
from app.services.sms.mock_provider import MockSMSProvider
from fastapi import HTTPException


class MockMongoCollection:
    def __init__(self):
        self.data = {}

    def find_one(self, query):
        contact = query.get("contact")
        if contact:
            rec = self.data.get(contact)
            if rec:
                if "verified" in query and rec.get("verified") != query["verified"]:
                    return None
                return dict(rec)
            return None
        phone = query.get("phone")
        email = query.get("email")
        if phone:
            for rec in self.data.values():
                if rec.get("phone") == phone:
                    return dict(rec)
        if email:
            for rec in self.data.values():
                if rec.get("email") == email:
                    return dict(rec)
        if "$or" in query:
            for cond in query["$or"]:
                res = self.find_one(cond)
                if res:
                    return res
        return None

    def update_one(self, query, update, upsert=False):
        contact = query.get("contact") or query.get("phone") or query.get("email")
        if not contact and "_id" in query:
            for k, v in self.data.items():
                if v.get("_id") == query["_id"]:
                    contact = k
                    break
        if not contact:
            return
        if "$set" in update:
            if contact not in self.data:
                self.data[contact] = {"_id": f"id_{contact}", "contact": contact}
            self.data[contact].update(update["$set"])
        if "$setOnInsert" in update:
            if contact not in self.data:
                self.data[contact] = {"_id": f"id_{contact}", "contact": contact, **update["$setOnInsert"]}

    def insert_one(self, doc):
        contact = doc.get("contact") or doc.get("phone") or doc.get("email") or str(len(self.data))
        doc_copy = dict(doc)
        doc_copy["_id"] = f"id_{contact}"
        self.data[contact] = doc_copy
        return doc_copy

    def delete_one(self, query):
        contact = query.get("contact") or query.get("phone")
        if contact and contact in self.data:
            del self.data[contact]


class TestOTPAndAirtelSMS(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_users = MockMongoCollection()
        self.mock_otps = MockMongoCollection()

        # Ensure strict validation during security tests
        self.patcher_dev = patch("app.api.auth.DEV_MODE", False)
        self.patcher_dev.start()

        # Seed sample verified user
        self.test_phone = "9876543210"
        self.mock_users.insert_one({
            "username": "test_user",
            "phone": self.test_phone,
            "role": "user",
            "plan": "basic",
            "verified": False,
        })

    def tearDown(self):
        self.patcher_dev.stop()

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_production_fail_closed_prevents_dev_mode_bypass(self, mock_get_users, mock_get_otps):
        """When ENVIRONMENT=production, DEV_MODE=true bypass must be disabled."""
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_request = MagicMock()

        raw_otp = "123456"
        otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()
        now = utc_now()
        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp_hash": otp_hash,
            "verified": False,
            "failed_attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=2),
        })

        bad_req = VerifyOTPRequest(contact=self.test_phone, otp="999999")

        with patch("app.api.auth.DEV_MODE", True), patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with self.assertRaises(HTTPException) as cm:
                await verify_otp(mock_request, bad_req)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "Invalid OTP")

    def test_otp_generation_and_length(self):

        """OTP must be exactly 6 numeric digits."""
        for _ in range(100):
            otp = _generate_otp()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit())
            self.assertGreaterEqual(int(otp), 100000)
            self.assertLessEqual(int(otp), 999999)

    def test_airtel_dlt_constants_and_payload(self):
        """Airtel provider must construct DLT-compliant payload with registered template ID and header."""
        provider = AirtelSMSProvider(
            api_url="https://iqsms.airtel.in/gateway/bulk-sms",
            customer_id="TEST_CUST_123",
            api_key="TEST_API_KEY",
            sender_id=AIRTEL_DLT_HEADER,
            entity_id=AIRTEL_DLT_PE_ID,
        )
        self.assertTrue(provider.is_configured())

        otp = "654321"
        payload = provider.build_payload(self.test_phone, otp, "registration")
        self.assertEqual(payload["customerId"], "TEST_CUST_123")
        self.assertEqual(payload["sourceAddress"], "LTATEC")
        self.assertEqual(payload["destinationAddress"], ["919876543210"])
        self.assertEqual(payload["dltTemplateId"], "1077380560017332633")
        self.assertEqual(payload["entityId"], "1001355597545597385")
        self.assertIn("654321", payload["message"])
        self.assertIn("Your LETATEC verification code is 654321.", payload["message"])
        self.assertIn("valid for 2 minutes", payload["message"])

    def test_airtel_send_otp_success_mocked(self):
        """Airtel provider handles successful 200 HTTP response."""
        provider = AirtelSMSProvider(
            customer_id="TEST_CUST",
            api_key="TEST_KEY",
        )
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messageId": "AIRTEL_MSG_001"}

            res = provider.send_otp(self.test_phone, "123456")
            self.assertTrue(res.success)
            self.assertEqual(res.provider, "airtel")
            self.assertEqual(res.message_id, "AIRTEL_MSG_001")

    def test_airtel_send_otp_error_and_timeout_handling(self):
        """Airtel provider gracefully handles timeouts and 5xx errors."""
        provider = AirtelSMSProvider(
            customer_id="TEST_CUST",
            api_key="TEST_KEY",
        )
        import requests
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Request timed out")):
            res = provider.send_otp(self.test_phone, "123456")
            self.assertFalse(res.success)
            self.assertEqual(res.provider, "airtel")
            self.assertIn("timed out", res.error.lower())

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Server Error"
            res = provider.send_otp(self.test_phone, "123456")
            self.assertFalse(res.success)
            self.assertEqual(res.status_code, 500)

    def test_sms_service_fallback_chain(self):
        """SMSService attempts Airtel first, then falls back to secondary provider."""
        service = SMSService(primary_provider_name="airtel")
        mock_airtel = MagicMock()
        mock_airtel.send_otp.return_value = SMSResult(success=False, provider="airtel", error="Airtel gateway down")
        mock_sns = MagicMock()
        mock_sns.send_otp.return_value = SMSResult(success=True, provider="aws_sns", message_id="SNS_001")

        service.airtel_provider = mock_airtel
        service.sns_provider = mock_sns
        service.dev_mode = False

        res = service.send_otp(self.test_phone, "123456")
        self.assertTrue(res.success)
        self.assertEqual(res.provider, "aws_sns")
        self.assertEqual(res.message_id, "SNS_001")
        mock_airtel.send_otp.assert_called_once()
        mock_sns.send_otp.assert_called_once()

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_send_otp_lifecycle_and_2min_expiry(self, mock_sms, mock_get_users, mock_get_otps):
        """send_otp sets 2-minute expiry and SHA-256 hash."""
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        req = SendOTPRequest(contact=self.test_phone, method="phone")
        mock_request = MagicMock()

        res = await send_otp(mock_request, req)
        self.assertEqual(res["message"], "OTP sent successfully")
        self.assertEqual(res["expires_in_minutes"], 2)
        self.assertEqual(res["cooldown_seconds"], 60)

        stored = self.mock_otps.find_one({"contact": self.test_phone})
        self.assertIsNotNone(stored)
        self.assertIn("otp_hash", stored)
        self.assertNotIn("otp", stored)  # Plaintext OTP NEVER stored
        self.assertEqual(stored["failed_attempts"], 0)

        # Expiry is exactly 2 minutes from created_at
        created_at = stored["created_at"]
        expires_at = stored["expires_at"]
        delta = (expires_at - created_at).total_seconds()
        self.assertAlmostEqual(delta, 120, delta=2)

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_resend_cooldown_60_seconds(self, mock_sms, mock_get_users, mock_get_otps):
        """Attempting to resend OTP within 60s must raise 429."""
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_request = MagicMock()
        req = SendOTPRequest(contact=self.test_phone, method="phone")

        # 1st request
        await send_otp(mock_request, req)

        # 2nd immediate request within cooldown window
        with self.assertRaises(HTTPException) as cm:
            await send_otp(mock_request, req)
        self.assertEqual(cm.exception.status_code, 429)
        self.assertIn("Please wait", cm.exception.detail)

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_verify_otp_success_and_burn(self, mock_get_users, mock_get_otps):
        """Valid OTP verification issues JWT tokens and immediately burns OTP record."""
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_request = MagicMock()

        raw_otp = "852963"
        otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()
        now = utc_now()
        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp_hash": otp_hash,
            "verified": False,
            "failed_attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=2),
        })

        v_req = VerifyOTPRequest(contact=self.test_phone, otp=raw_otp)
        token_res = await verify_otp(mock_request, v_req)

        self.assertIn("tokens", token_res)
        self.assertIn("accessToken", token_res["tokens"])
        self.assertIn("refreshToken", token_res["tokens"])
        self.assertEqual(token_res["user"]["phone"], self.test_phone)

        # OTP burned (single-use)
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

        # Replay attempt fails
        with self.assertRaises(HTTPException) as cm:
            await verify_otp(mock_request, v_req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "No pending OTP found")

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_verify_otp_expired_rejection(self, mock_get_users, mock_get_otps):
        """Expired OTP is rejected and deleted."""
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_request = MagicMock()

        raw_otp = "123456"
        otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()
        past = utc_now() - timedelta(minutes=5)
        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp_hash": otp_hash,
            "verified": False,
            "failed_attempts": 0,
            "created_at": past - timedelta(minutes=2),
            "expires_at": past,
        })

        v_req = VerifyOTPRequest(contact=self.test_phone, otp=raw_otp)
        with self.assertRaises(HTTPException) as cm:
            await verify_otp(mock_request, v_req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "OTP expired")
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_brute_force_max_attempts_burns_otp(self, mock_get_users, mock_get_otps):
        """5 failed verify attempts burn the OTP and return 429."""
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_request = MagicMock()

        raw_otp = "999999"
        otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()
        now = utc_now()
        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp_hash": otp_hash,
            "verified": False,
            "failed_attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=2),
        })

        bad_req = VerifyOTPRequest(contact=self.test_phone, otp="000000")

        # 4 failed attempts -> 400 Invalid OTP
        for attempt in range(1, 5):
            with self.assertRaises(HTTPException) as cm:
                await verify_otp(mock_request, bad_req)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "Invalid OTP")
            rec = self.mock_otps.find_one({"contact": self.test_phone})
            self.assertEqual(rec["failed_attempts"], attempt)

        # 5th failed attempt -> 429 and OTP burned
        with self.assertRaises(HTTPException) as cm:
            await verify_otp(mock_request, bad_req)
        self.assertEqual(cm.exception.status_code, 429)
        self.assertIn("Too many failed attempts", cm.exception.detail)
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))


if __name__ == "__main__":
    unittest.main()
