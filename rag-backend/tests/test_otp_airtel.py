"""
Dedicated OTP hardening & Airtel DLT compliance test suite.

Validates:
1. 2-minute OTP expiry (OTP_EXPIRY_MINUTES == 2)
2. 60-second resend cooldown (HTTP 429 with remaining seconds)
3. Hourly rate limiting (OTP_RATE_LIMIT_PER_HOUR == 3, message: "Too many OTP requests. Please try again in an hour.")
4. SHA-256 hashed OTP storage (raw plaintext 'otp' never stored)
5. OTP verification (constant-time hash comparison)
6. Legacy plaintext OTP compatibility fallback
7. Failed-attempt tracking and 5-attempt burn (HTTP 429 after MAX_OTP_ATTEMPTS == 5)
8. Attempt remaining reporting on invalid OTP
9. Expired OTP rejection and deletion
10. Offset-naive MongoDB datetime normalization (no TypeError)
11. SMS delegation to app.services.sms with template_type="registration"
12. SMS delivery failure rollback (HTTP 502 Bad Gateway and DB cleanup)
13. Production-safe DEV_MODE guard (arbitrary bypass disabled in production/prod)
14. API response contract (expires_in_minutes: 2, cooldown_seconds: 60)
"""
import copy
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import (
    MAX_OTP_ATTEMPTS,
    OTP_EXPIRY_MINUTES,
    OTP_RATE_LIMIT_PER_HOUR,
    OTP_RESEND_COOLDOWN_SECONDS,
    SendOTPRequest,
    UserRegister,
    VerifyOTPRequest,
    register_user,
    send_otp,
    verify_otp,
)
from app.services.sms.base import SMSResult
from app.utils.time import normalize_to_utc, utc_now


from pymongo.errors import DuplicateKeyError


class MockMongoCollection:
    """In-memory mock of a MongoDB collection supporting $set, $unset, $inc, and unique/sparse index constraints."""

    def __init__(self, unique_indexes=None):
        self.docs = []
        # list of (field, is_sparse_bool)
        self.unique_indexes = unique_indexes or []

    def _check_unique_constraints(self, doc, exclude_doc=None):
        for field, is_sparse in self.unique_indexes:
            if is_sparse and field not in doc:
                continue
            val = doc.get(field)
            for d in self.docs:
                if exclude_doc is not None and d is exclude_doc:
                    continue
                if exclude_doc is not None and d.get("_id") and d.get("_id") == exclude_doc.get("_id"):
                    continue
                if is_sparse and field not in d:
                    continue
                if d.get(field) == val:
                    raise DuplicateKeyError(
                        f"E11000 duplicate key error collection: mock.{field} index: {field}_1 dup key: {{{field}: {val}}}"
                    )

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "$or":
                if not any(self._matches(doc, subq) for subq in v):
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, query):
        for d in self.docs:
            if self._matches(d, query):
                return copy.deepcopy(d)
        return None

    def insert_one(self, doc):
        stored = copy.deepcopy(doc)
        if "_id" not in stored:
            stored["_id"] = str(len(self.docs) + 1)
        self._check_unique_constraints(stored)
        self.docs.append(stored)
        return MagicMock(inserted_id=stored["_id"])

    def update_one(self, query, update, upsert=False):
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                updated_doc = copy.deepcopy(d)
                if "$set" in update:
                    for k, v in update["$set"].items():
                        updated_doc[k] = copy.deepcopy(v)
                if "$unset" in update:
                    for k in update["$unset"]:
                        updated_doc.pop(k, None)
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        updated_doc[k] = updated_doc.get(k, 0) + v
                self._check_unique_constraints(updated_doc, exclude_doc=d)
                self.docs[i] = updated_doc
                return MagicMock(matched_count=1, modified_count=1)

        if upsert:
            new_doc = copy.deepcopy(query)
            if "$setOnInsert" in update:
                new_doc.update(copy.deepcopy(update["$setOnInsert"]))
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            if "$inc" in update:
                for k, v in update["$inc"].items():
                    new_doc[k] = new_doc.get(k, 0) + v
            if "_id" not in new_doc:
                new_doc["_id"] = str(len(self.docs) + 1)
            self._check_unique_constraints(new_doc)
            self.docs.append(new_doc)
            return MagicMock(matched_count=0, upserted_id=new_doc["_id"])

        return MagicMock(matched_count=0, modified_count=0)

    def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                self.docs.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)


class TestOTPAirtelHardening(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_users = MockMongoCollection(
            unique_indexes=[("phone", True), ("email", True)]
        )
        self.mock_otps = MockMongoCollection(
            unique_indexes=[("contact", False)]
        )
        self.test_phone = "9876543210"
        self.test_email = "testuser@letatec.com"
        self.mock_request = MagicMock()

        # Seed test user
        self.mock_users.insert_one({
            "_id": "user_001",
            "username": "testuser",
            "phone": self.test_phone,
            "email": self.test_email,
            "role": "user",
            "plan": "basic",
            "verified": True,
            "created_at": utc_now(),
            "last_login": None,
        })

    # =========================================================================
    # 1. OTP EXPIRY (2-minute DLT template compliance)
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_01_otp_expiry_2_minutes(self, mock_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        self.assertEqual(OTP_EXPIRY_MINUTES, 2)
        req = SendOTPRequest(contact=self.test_phone, method="phone")
        res = await send_otp(self.mock_request, req)

        self.assertEqual(res["expires_in_minutes"], 2)
        stored = self.mock_otps.find_one({"contact": self.test_phone})
        self.assertIsNotNone(stored)

        created_at = normalize_to_utc(stored["created_at"])
        expires_at = normalize_to_utc(stored["expires_at"])
        delta_seconds = (expires_at - created_at).total_seconds()
        self.assertAlmostEqual(delta_seconds, 120, delta=2)

    # =========================================================================
    # 2. RESEND COOLDOWN (60-second throttling)
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_02_resend_cooldown_60_seconds(self, mock_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        self.assertEqual(OTP_RESEND_COOLDOWN_SECONDS, 60)

        req = SendOTPRequest(contact=self.test_phone, method="phone")
        # 1st request succeeds
        res1 = await send_otp(self.mock_request, req)
        self.assertEqual(res1["cooldown_seconds"], 60)
        self.assertEqual(mock_sms.call_count, 1)

        # 2nd immediate request within cooldown window raises 429
        with self.assertRaises(HTTPException) as cm:
            await send_otp(self.mock_request, req)
        self.assertEqual(cm.exception.status_code, 429)
        self.assertIn("Please wait", cm.exception.detail)
        self.assertIn("seconds before requesting a new OTP", cm.exception.detail)
        # SMS was not dispatched again
        self.assertEqual(mock_sms.call_count, 1)

    # =========================================================================
    # 3. HOURLY RATE LIMIT (3 requests per hour)
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_03_hourly_rate_limit(self, mock_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        self.assertEqual(OTP_RATE_LIMIT_PER_HOUR, 3)

        req = SendOTPRequest(contact=self.test_phone, method="phone")

        # Simulate 3 successful requests outside cooldown by advancing created_at
        for count in range(1, 4):
            now = utc_now()
            self.mock_otps.docs = [{
                "contact": self.test_phone,
                "method": "phone",
                "otp_hash": "dummy_hash",
                "verified": False,
                "failed_attempts": 0,
                "created_at": now - timedelta(seconds=70),
                "expires_at": now + timedelta(minutes=2),
                "rate_window_start": now - timedelta(minutes=10),
                "request_count": count - 1,
            }]
            await send_otp(self.mock_request, req)

        # 4th request within the same hour raises 429
        self.mock_otps.docs[0]["created_at"] = utc_now() - timedelta(seconds=70)
        with self.assertRaises(HTTPException) as cm:
            await send_otp(self.mock_request, req)
        self.assertEqual(cm.exception.status_code, 429)
        self.assertEqual(cm.exception.detail, "Too many OTP requests. Please try again in an hour.")

    # =========================================================================
    # 4. OTP HASH STORAGE (SHA-256, no plaintext in MongoDB)
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_04_otp_hash_storage_no_plaintext(self, mock_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        req = SendOTPRequest(contact=self.test_phone, method="phone")
        await send_otp(self.mock_request, req)

        stored = self.mock_otps.find_one({"contact": self.test_phone})
        self.assertIsNotNone(stored)
        self.assertIn("otp_hash", stored)
        self.assertEqual(len(stored["otp_hash"]), 64)  # 64 hex chars for SHA-256
        self.assertNotIn("otp", stored)  # Plaintext MUST NOT exist
        self.assertEqual(stored["failed_attempts"], 0)

    # =========================================================================
    # 5. OTP VERIFICATION (Success with hash & single-use consumption)
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_05_otp_verification_success_and_single_use(self, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        raw_otp = "741852"
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
        token_res = await verify_otp(self.mock_request, v_req)

        self.assertIn("tokens", token_res)
        self.assertIn("accessToken", token_res["tokens"])
        self.assertEqual(token_res["user"]["phone"], self.test_phone)

        # Record consumed immediately (cannot replay)
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

        # Replay attempt fails with 400
        with self.assertRaises(HTTPException) as cm:
            await verify_otp(self.mock_request, v_req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "No pending OTP found")

    # =========================================================================
    # 6. LEGACY OTP COMPATIBILITY (Plaintext fallback)
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_06_legacy_plaintext_otp_compatibility(self, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        raw_otp = "654321"
        now = utc_now()
        # Old schema record with plaintext 'otp' and no 'otp_hash'
        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp": raw_otp,
            "verified": False,
            "failed_attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=2),
        })

        v_req = VerifyOTPRequest(contact=self.test_phone, otp=raw_otp)
        token_res = await verify_otp(self.mock_request, v_req)
        self.assertIn("accessToken", token_res["tokens"])
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

    # =========================================================================
    # 7. FAILED ATTEMPTS & 5-ATTEMPT BURN (MAX_OTP_ATTEMPTS == 5)
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_07_failed_attempts_and_5_attempt_burn(self, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        self.assertEqual(MAX_OTP_ATTEMPTS, 5)

        raw_otp = "333444"
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

        # 4 failed attempts -> 400 Invalid OTP, counter increments
        for attempt in range(1, 5):
            with self.assertRaises(HTTPException) as cm:
                await verify_otp(self.mock_request, bad_req)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "Invalid OTP")
            rec = self.mock_otps.find_one({"contact": self.test_phone})
            self.assertEqual(rec["failed_attempts"], attempt)

        # 5th failed attempt -> 429 Too Many Requests, OTP deleted/burned
        with self.assertRaises(HTTPException) as cm:
            await verify_otp(self.mock_request, bad_req)
        self.assertEqual(cm.exception.status_code, 429)
        self.assertEqual(cm.exception.detail, "Too many failed attempts. Please request a new OTP.")
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

    # =========================================================================
    # 8. ATTEMPTS REMAINING LOGGING / TRACKING
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_08_attempts_remaining_logged(self, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        raw_otp = "111222"
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
        with self.assertRaises(HTTPException):
            await verify_otp(self.mock_request, bad_req)

        # Check that log_activity was called with attempts_remaining == 4
        self.assertTrue(mock_log_act.called)
        last_call_kwargs = mock_log_act.call_args[1]
        self.assertEqual(last_call_kwargs["metadata"].get("attempts_remaining"), 4)

    # =========================================================================
    # 9. EXPIRED OTP REJECTION
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_09_expired_otp_rejection(self, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        raw_otp = "123123"
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
            await verify_otp(self.mock_request, v_req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "OTP expired")
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

    # =========================================================================
    # 10. DATETIME NORMALIZATION (Naive UTC MongoDB timestamps)
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_10_naive_mongo_datetime_normalization(self, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        raw_otp = "555666"
        otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()
        # Create offset-naive datetime (as returned by PyMongo)
        naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
        naive_expires_at = naive_now + timedelta(minutes=2)

        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp_hash": otp_hash,
            "verified": False,
            "failed_attempts": 0,
            "created_at": naive_now,
            "expires_at": naive_expires_at,
        })

        v_req = VerifyOTPRequest(contact=self.test_phone, otp=raw_otp)
        # MUST NOT raise TypeError: can't compare offset-naive and offset-aware datetimes
        token_res = await verify_otp(self.mock_request, v_req)
        self.assertIn("accessToken", token_res["tokens"])

    # =========================================================================
    # 11. SMS DISPATCH DELEGATION SUCCESS
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.services.sms.send_sms_otp")
    async def test_11_sms_dispatch_success(self, mock_dispatch_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_dispatch_sms.return_value = SMSResult(success=True, provider="airtel", message_id="AIRTEL_99")

        req = SendOTPRequest(contact=self.test_phone, method="phone")
        res = await send_otp(self.mock_request, req)

        self.assertEqual(res["message"], "OTP sent successfully")
        mock_dispatch_sms.assert_called_once()
        self.assertEqual(mock_dispatch_sms.call_args[1]["template_type"], "registration")
        self.assertEqual(mock_dispatch_sms.call_args[0][0], self.test_phone)

    # =========================================================================
    # 12. SMS DELIVERY FAILURE ROLLBACK (HTTP 502 + DB cleanup)
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.services.sms.send_sms_otp")
    async def test_12_sms_delivery_failure_rollback(self, mock_dispatch_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps
        mock_dispatch_sms.return_value = SMSResult(success=False, provider="airtel", error="Delivery timeout")

        req = SendOTPRequest(contact=self.test_phone, method="phone")
        with self.assertRaises(HTTPException) as cm:
            await send_otp(self.mock_request, req)

        self.assertEqual(cm.exception.status_code, 502)
        self.assertIn("Failed to send SMS OTP", cm.exception.detail)
        # OTP record rolled back / deleted from DB
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

    # =========================================================================
    # 13. DEV_MODE PRODUCTION GUARD
    # =========================================================================

    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_13_dev_mode_production_guard(self, mock_get_users, mock_get_otps):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

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

        arbitrary_otp_req = VerifyOTPRequest(contact=self.test_phone, otp="999999")

        # 1. In PRODUCTION: DEV_MODE=true + ENVIRONMENT=production -> arbitrary bypass DISABLED
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "production"}):
            with self.assertRaises(HTTPException) as cm:
                await verify_otp(self.mock_request, arbitrary_otp_req)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "Invalid OTP")

        # 2. In PROD: DEV_MODE=true + ENVIRONMENT=prod -> arbitrary bypass DISABLED
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "prod"}):
            with self.assertRaises(HTTPException) as cm:
                await verify_otp(self.mock_request, arbitrary_otp_req)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "Invalid OTP")

        # 3. In NON-PRODUCTION: DEV_MODE=true + ENVIRONMENT=development -> arbitrary 6-digit bypass ENABLED
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "development"}):
            token_res = await verify_otp(self.mock_request, arbitrary_otp_req)
            self.assertIn("accessToken", token_res["tokens"])

    # =========================================================================
    # 14. RESPONSE CONTRACT
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_14_response_contract(self, mock_sms, mock_get_users, mock_get_otps, mock_log_act):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        req = SendOTPRequest(contact=self.test_phone, method="phone")
        res = await send_otp(self.mock_request, req)

        self.assertEqual(res["message"], "OTP sent successfully")
        self.assertEqual(res["expires_in_minutes"], 2)
        self.assertEqual(res["cooldown_seconds"], 60)


    # =========================================================================
    # 15. AIRTEL PREPAID ENDPOINT & BASIC AUTH USERNAME/PASSWORD
    # =========================================================================

    @patch.dict(os.environ, {"AIRTEL_USERNAME": "", "AIRTEL_PASSWORD": "", "AIRTEL_API_KEY": "", "AIRTEL_API_SECRET": "", "AIRTEL_CUSTOMER_ID": ""})
    @patch("requests.post")
    def test_15_airtel_provider_prepaid_endpoint_and_basic_auth(self, mock_post):
        from app.services.sms.airtel import AirtelSMSProvider

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messageId": "AIRTEL_MSG_001"}
        mock_post.return_value = mock_resp

        provider = AirtelSMSProvider(
            customer_id="CUST_LETATEC_01",
            username="IQ_USER_LETATEC",
            password="SECRET_PASSWORD_123",
        )

        # 1. Verify default endpoint is the v1 prepaid route
        self.assertEqual(provider.api_url, "https://iqsms.airtel.in/api/v1/send-prepaid-sms")
        self.assertTrue(provider.is_configured())

        res = provider.send_otp(self.test_phone, "852963")
        self.assertTrue(res.success)
        self.assertEqual(res.provider, "airtel")
        self.assertEqual(res.message_id, "AIRTEL_MSG_001")

        # 2. Verify requests.post call arguments
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], "https://iqsms.airtel.in/api/v1/send-prepaid-sms")
        # Basic auth must use (username, password)
        self.assertEqual(call_kwargs["auth"], ("IQ_USER_LETATEC", "SECRET_PASSWORD_123"))

        # 3. Verify JSON payload contains CustomerID, DLT values, and masked destination
        payload = call_kwargs["json"]
        self.assertEqual(payload["customerId"], "CUST_LETATEC_01")
        self.assertEqual(payload["sourceAddress"], "LTATEC")
        self.assertEqual(payload["entityId"], "1001355597545597385")
        self.assertEqual(payload["dltTemplateId"], "1077380560017332633")
        self.assertEqual(payload["messageType"], "SERVICE_IMPLICIT")
        self.assertEqual(payload["destinationAddress"], [f"91{self.test_phone}"])
        self.assertIn("852963", payload["message"])

    # =========================================================================
    # 16. AIRTEL PROVIDER BACKWARD-COMPATIBLE FALLBACK
    # =========================================================================

    @patch.dict(os.environ, {"AIRTEL_USERNAME": "", "AIRTEL_PASSWORD": "", "AIRTEL_API_KEY": "", "AIRTEL_API_SECRET": "", "AIRTEL_CUSTOMER_ID": ""})
    @patch("requests.post")
    def test_16_airtel_provider_backward_compat_fallback(self, mock_post):
        from app.services.sms.airtel import AirtelSMSProvider

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"msgId": "AIRTEL_MSG_002"}
        mock_post.return_value = mock_resp

        # When username/password are not explicitly provided, fall back to customer_id & api_secret
        provider = AirtelSMSProvider(
            customer_id="CUST_FALLBACK_02",
            api_secret="LEGACY_API_SECRET_999",
        )
        self.assertTrue(provider.is_configured())

        res = provider.send_otp(self.test_phone, "147258")
        self.assertTrue(res.success)
        mock_post.assert_called_once()
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["auth"], ("CUST_FALLBACK_02", "LEGACY_API_SECRET_999"))
        self.assertEqual(call_kwargs["json"]["customerId"], "CUST_FALLBACK_02")

    # =========================================================================
    # 17. AIRTEL PROVIDER FALLBACK CHAIN PRESERVATION
    # =========================================================================

    def test_17_sms_service_fallback_chain_preservation(self):
        from app.services.sms.sms_service import SMSService
        from app.services.sms.base import SMSResult

        service = SMSService(primary_provider_name="airtel")
        mock_airtel = MagicMock()
        mock_airtel.send_otp.return_value = SMSResult(success=False, provider="airtel", error="Airtel timeout")
        mock_sns = MagicMock()
        mock_sns.send_otp.return_value = SMSResult(success=True, provider="aws_sns", message_id="SNS_OK_123")

        service.airtel_provider = mock_airtel
        service.sns_provider = mock_sns
        service.dev_mode = False

        res = service.send_otp(self.test_phone, "654321")
        self.assertTrue(res.success)
        self.assertEqual(res.provider, "aws_sns")
        self.assertEqual(res.message_id, "SNS_OK_123")
        mock_airtel.send_otp.assert_called_once()
        mock_sns.send_otp.assert_called_once()

    # =========================================================================
    # 18. NEW REGISTRATION CREATES UNVERIFIED USER & ENABLES OTP ONBOARDING
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_18_new_registration_creates_unverified_and_completes_via_otp(
        self, mock_sms, mock_get_users, mock_get_otps, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        new_phone = "9988776655"
        reg_data = UserRegister(
            full_name="New Pilot Tester",
            phone=new_phone,
            profession="Chartered Accountant (CA)",
            gender="Female",
        )

        # 1. Register creates unverified account
        reg_res = await register_user(self.mock_request, reg_data)
        self.assertEqual(reg_res["message"], "Account created successfully")

        user_doc = self.mock_users.find_one({"phone": new_phone})
        self.assertIsNotNone(user_doc)
        self.assertFalse(user_doc["verified"])
        self.assertEqual(user_doc["full_name"], "New Pilot Tester")

        # 2. Registration requests OTP
        send_req = SendOTPRequest(contact=new_phone, method="phone")
        send_res = await send_otp(self.mock_request, send_req)
        self.assertEqual(send_res["message"], "OTP sent successfully")
        self.assertEqual(send_res["expires_in_minutes"], 2)
        self.assertEqual(send_res["cooldown_seconds"], 60)

        # Retrieve generated OTP hash and verify
        otp_doc = self.mock_otps.find_one({"contact": new_phone})
        self.assertIsNotNone(otp_doc)

        # 3. Simulate OTP verification with DEV_MODE=false
        with patch.dict(os.environ, {"DEV_MODE": "false", "ENVIRONMENT": "production"}):
            # Find the plain OTP that was passed to send_sms_otp
            sent_otp = mock_sms.call_args[0][1]
            verify_req = VerifyOTPRequest(contact=new_phone, otp=sent_otp)
            auth_res = await verify_otp(self.mock_request, verify_req)

            # 4. Verified becomes True and tokens are returned
            self.assertIn("accessToken", auth_res["tokens"])
            self.assertEqual(auth_res["user"]["phone"], new_phone)

            updated_user = self.mock_users.find_one({"phone": new_phone})
            self.assertTrue(updated_user["verified"])
            self.assertIsNotNone(updated_user["last_login"])

    # =========================================================================
    # 19. UNKNOWN NUMBER ON LOGIN STILL RECEIVES 404
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=True)
    async def test_19_unknown_number_on_login_receives_404(
        self, mock_sms, mock_get_users, mock_get_otps, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        unknown_phone = "9111222333"
        send_req = SendOTPRequest(contact=unknown_phone, method="phone")

        with self.assertRaises(HTTPException) as cm:
            await send_otp(self.mock_request, send_req)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIn("Please register first", cm.exception.detail)
        mock_sms.assert_not_called()

    # =========================================================================
    # 20. UNVERIFIED REGISTRATION RESTART UPDATES PENDING USER WITHOUT DUPLICATE
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_user_collection")
    async def test_20_unverified_registration_restart_updates_pending_user_without_duplicate(
        self, mock_get_users, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users

        pending_phone = "9888777666"
        # Initial registration attempt
        reg1 = UserRegister(
            full_name="Original Name",
            phone=pending_phone,
            profession="Student",
            gender="Other",
        )
        res1 = await register_user(self.mock_request, reg1)
        self.assertEqual(res1["message"], "Account created successfully")

        # Second registration attempt before OTP verification (e.g. user corrected details)
        reg2 = UserRegister(
            full_name="Corrected Name",
            phone=pending_phone,
            profession="Tax Consultant",
            gender="Male",
        )
        res2 = await register_user(self.mock_request, reg2)
        self.assertEqual(res2["message"], "Account created successfully")

        # Must not create a duplicate user; details must be updated in place
        matching_users = [u for u in self.mock_users.docs if u.get("phone") == pending_phone]
        self.assertEqual(len(matching_users), 1)
        self.assertEqual(matching_users[0]["full_name"], "Corrected Name")
        self.assertEqual(matching_users[0]["profession"], "Tax Consultant")
        self.assertFalse(matching_users[0]["verified"])

    # =========================================================================
    # 21. VERIFIED USER CANNOT BE OVERWRITTEN BY SIGNUP
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_user_collection")
    async def test_21_verified_user_cannot_be_overwritten_by_signup(
        self, mock_get_users, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users

        # self.test_phone is already verified
        reg_attempt = UserRegister(
            full_name="Impostor",
            phone=self.test_phone,
            profession="Advocate / Lawyer",
            gender="Male",
        )

        with self.assertRaises(HTTPException) as cm:
            await register_user(self.mock_request, reg_attempt)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "Phone number already registered")

        # Verify original user data remains intact
        existing = self.mock_users.find_one({"phone": self.test_phone})
        self.assertEqual(existing["username"], "testuser")
        self.assertTrue(existing["verified"])

    # =========================================================================
    # 22. SMS FAILURE ROLLS BACK NEW UNVERIFIED REGISTRATION (NO ORPHAN)
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=False)
    async def test_22_sms_failure_rolls_back_new_unverified_registration(
        self, mock_sms, mock_get_users, mock_get_otps, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        orphan_candidate_phone = "9777666555"
        reg = UserRegister(
            full_name="Temporary User",
            phone=orphan_candidate_phone,
            profession="Business Owner",
            gender="Female",
        )
        await register_user(self.mock_request, reg)
        self.assertIsNotNone(self.mock_users.find_one({"phone": orphan_candidate_phone}))

        send_req = SendOTPRequest(contact=orphan_candidate_phone, method="phone")

        with self.assertRaises(HTTPException) as cm:
            await send_otp(self.mock_request, send_req)
        self.assertEqual(cm.exception.status_code, 502)

        # 1. OTP record is cleaned up
        self.assertIsNone(self.mock_otps.find_one({"contact": orphan_candidate_phone}))
        # 2. Newly-created unverified account is rolled back so no orphan remains
        self.assertIsNone(self.mock_users.find_one({"phone": orphan_candidate_phone}))

    # =========================================================================
    # 23. SMS FAILURE ON RESEND OR VERIFIED USER DOES NOT DELETE ACCOUNT
    # =========================================================================

    @patch("app.api.auth.DEV_MODE", False)
    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    @patch("app.api.auth.send_sms_otp", return_value=False)
    async def test_23_sms_failure_on_verified_user_does_not_delete_account(
        self, mock_sms, mock_get_users, mock_get_otps, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        send_req = SendOTPRequest(contact=self.test_phone, method="phone")

        with self.assertRaises(HTTPException) as cm:
            await send_otp(self.mock_request, send_req)
        self.assertEqual(cm.exception.status_code, 502)

        # Verified user MUST NOT be deleted merely because SMS failed
        self.assertIsNotNone(self.mock_users.find_one({"phone": self.test_phone}))

    # =========================================================================
    # 24. MISSING OR INVALID EXPIRES_AT IS REJECTED AS EXPIRED
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_otp_collection")
    @patch("app.api.auth.get_user_collection")
    async def test_24_missing_expires_at_is_rejected_as_expired(
        self, mock_get_users, mock_get_otps, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users
        mock_get_otps.return_value = self.mock_otps

        raw_otp = "445566"
        otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()
        # Seed record missing expires_at
        self.mock_otps.insert_one({
            "contact": self.test_phone,
            "method": "phone",
            "otp_hash": otp_hash,
            "verified": False,
            "failed_attempts": 0,
            "created_at": utc_now(),
            "expires_at": None,
        })

        req = VerifyOTPRequest(contact=self.test_phone, otp=raw_otp)

        with self.assertRaises(HTTPException) as cm:
            await verify_otp(self.mock_request, req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "OTP expired")
        self.assertIsNone(self.mock_otps.find_one({"contact": self.test_phone}))

    # =========================================================================
    # 25. PHONE-ONLY REGISTRATIONS OMIT EMAIL FIELD & COEXIST WITHOUT DUPLICATE KEY ERROR
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_user_collection")
    async def test_25_phone_only_registrations_omit_email_field_and_coexist(
        self, mock_get_users, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users

        phone_a = "9811111111"
        phone_b = "9822222222"
        phone_c = "9833333333"

        reg_a = UserRegister(full_name="User A", phone=phone_a, profession="Student", gender="Male")
        reg_b = UserRegister(full_name="User B", phone=phone_b, profession="Other", gender="Female")
        reg_c = UserRegister(full_name="User C", phone=phone_c, profession="Tax Consultant", gender="Other")

        res_a = await register_user(self.mock_request, reg_a)
        res_b = await register_user(self.mock_request, reg_b)
        res_c = await register_user(self.mock_request, reg_c)

        self.assertEqual(res_a["message"], "Account created successfully")
        self.assertEqual(res_b["message"], "Account created successfully")
        self.assertEqual(res_c["message"], "Account created successfully")

        # Verify email field is strictly absent (not email: None / null)
        for phone in (phone_a, phone_b, phone_c):
            doc = self.mock_users.find_one({"phone": phone})
            self.assertIsNotNone(doc)
            self.assertNotIn("email", doc, f"User with phone {phone} must not contain 'email' key when no email was supplied")

    # =========================================================================
    # 26. REGISTRATION WITH DUPLICATE EMAIL RAISES 400
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_user_collection")
    async def test_26_registration_with_duplicate_email_raises_400(
        self, mock_get_users, mock_log_act
    ):
        mock_get_users.return_value = self.mock_users

        shared_email = "lawyer@letatec.com"
        reg1 = UserRegister(
            full_name="Lawyer One",
            phone="9711111111",
            email=shared_email,
            profession="Advocate / Lawyer",
            gender="Male",
        )
        res1 = await register_user(self.mock_request, reg1)
        self.assertEqual(res1["message"], "Account created successfully")

        reg2 = UserRegister(
            full_name="Lawyer Two",
            phone="9722222222",
            email=shared_email,
            profession="Advocate / Lawyer",
            gender="Female",
        )
        with self.assertRaises(HTTPException) as cm:
            await register_user(self.mock_request, reg2)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "Email already registered")

    # =========================================================================
    # 27. DUPLICATE KEY RACE CONVERSION CATCHES CONCURRENT INSERT ERRORS
    # =========================================================================

    @patch("app.api.auth.log_activity")
    @patch("app.api.auth.get_user_collection")
    async def test_27_duplicate_key_error_on_insert_converts_to_400(
        self, mock_get_users, mock_log_act
    ):
        mock_col = MagicMock()
        mock_col.find_one.return_value = None
        mock_col.insert_one.side_effect = DuplicateKeyError("E11000 duplicate key error collection: leta_history.users index: phone_1 dup key: { phone: '9733333333' }")
        mock_get_users.return_value = mock_col

        reg = UserRegister(
            full_name="Race User",
            phone="9733333333",
            profession="Student",
            gender="Male",
        )
        with self.assertRaises(HTTPException) as cm:
            await register_user(self.mock_request, reg)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "Phone number already registered")


if __name__ == "__main__":
    unittest.main()
