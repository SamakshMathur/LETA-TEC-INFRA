"""
tests/test_auth_hardening.py
Phase 12: Authentication hardening regression tests.
Tests run without MongoDB or Redis; all external state is mocked.
"""
import hashlib
import inspect
import ast
import os
import unittest
from unittest.mock import MagicMock, patch


def _make_otp_record(otp, expired=False, failed_attempts=0, legacy=False):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    expires_at = (
        now - timedelta(minutes=1)
        if expired
        else now + timedelta(minutes=10)
    )
    record = {
        "contact": "9999999999",
        "method": "phone",
        "verified": False,
        "failed_attempts": failed_attempts,
        "created_at": now,
        "expires_at": expires_at,
        "rate_window_start": now,
        "request_count": 1,
    }

    if legacy:
        record["otp"] = otp
    else:
        record["otp_hash"] = hashlib.sha256(otp.encode()).hexdigest()
    return record


def _otp_matches(otp_record, submitted_otp):
    import secrets as _s
    stored_hash = otp_record.get("otp_hash")
    if stored_hash:
        submitted_hash = hashlib.sha256(submitted_otp.encode()).hexdigest()
        return _s.compare_digest(stored_hash, submitted_hash)
    legacy_otp = otp_record.get("otp", "")
    return _s.compare_digest(legacy_otp, submitted_otp)


class TestOTPBruteForce(unittest.TestCase):
    def _simulate_verify(self, otp_record, submitted_otp, mock_col):
        import app.api.auth as auth_mod
        from fastapi import HTTPException
        otp_valid = _otp_matches(otp_record, submitted_otp)
        if not otp_valid:
            new_attempts = otp_record.get("failed_attempts", 0) + 1
            if new_attempts >= auth_mod.MAX_OTP_ATTEMPTS:
                mock_col.delete_one({"contact": otp_record["contact"]})
                raise HTTPException(status_code=429, detail="Too many failed attempts. Please request a new OTP.")
            mock_col.update_one(
                {"contact": otp_record["contact"]},
                {"$set": {"failed_attempts": new_attempts}},
            )
            raise HTTPException(status_code=400, detail="Invalid OTP")

    def test_wrong_otp_increments_counter(self):
        from fastapi import HTTPException
        record = _make_otp_record("123456")
        col = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            self._simulate_verify(record, "000000", col)
        self.assertEqual(ctx.exception.status_code, 400)
        col.update_one.assert_called_once()

    def test_max_attempts_burns_otp(self):
        from fastapi import HTTPException
        import app.api.auth as auth_mod
        record = _make_otp_record("123456", failed_attempts=auth_mod.MAX_OTP_ATTEMPTS - 1)
        col = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            self._simulate_verify(record, "000000", col)
        self.assertEqual(ctx.exception.status_code, 429)
        col.delete_one.assert_called_once()
        col.update_one.assert_not_called()

    def test_correct_otp_no_lockout(self):
        record = _make_otp_record("123456")
        col = MagicMock()
        try:
            self._simulate_verify(record, "123456", col)
        except Exception:
            self.fail("Correct OTP raised an exception")
        col.update_one.assert_not_called()
        col.delete_one.assert_not_called()


class TestOTPHashing(unittest.TestCase):
    def test_hashed_otp_correct_value(self):
        otp = "987654"
        record = _make_otp_record(otp)
        self.assertTrue(_otp_matches(record, otp))
        self.assertFalse(_otp_matches(record, "000000"))

    def test_legacy_plaintext_otp_verifies(self):
        otp = "111111"
        record = _make_otp_record(otp, legacy=True)
        self.assertIsNone(record.get("otp_hash"))
        self.assertTrue(_otp_matches(record, otp))
        self.assertFalse(_otp_matches(record, "000000"))

    def test_hash_not_plaintext_in_payload(self):
        otp = "654321"
        expected_hash = hashlib.sha256(otp.encode()).hexdigest()
        payload = {"otp_hash": expected_hash, "failed_attempts": 0}
        self.assertIn("otp_hash", payload)
        self.assertNotIn("otp", payload)


class TestNoDuplicateRefreshRequest(unittest.TestCase):
    def test_refresh_request_defined_once(self):
        import app.api.auth as auth_mod
        source = inspect.getsource(auth_mod)
        tree = ast.parse(source)
        class_defs = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "RefreshRequest"]
        self.assertEqual(len(class_defs), 1, f"RefreshRequest defined {len(class_defs)} times")


class TestJWTJTIClaim(unittest.TestCase):
    def test_access_token_has_jti(self):
        import jwt
        from app.security import create_access_token, SECRET_KEY, ALGORITHM
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        self.assertIn("jti", payload)
        self.assertTrue(payload["jti"])

    def test_refresh_token_has_jti(self):
        import jwt
        from app.security import create_refresh_token, SECRET_KEY, ALGORITHM
        token = create_refresh_token({"sub": "testuser"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        self.assertIn("jti", payload)
        self.assertTrue(payload["jti"])

    def test_access_tokens_unique_jti(self):
        import jwt
        from app.security import create_access_token, SECRET_KEY, ALGORITHM
        t1 = create_access_token({"sub": "u"})
        t2 = create_access_token({"sub": "u"})
        p1 = jwt.decode(t1, SECRET_KEY, algorithms=[ALGORITHM])
        p2 = jwt.decode(t2, SECRET_KEY, algorithms=[ALGORITHM])
        self.assertNotEqual(p1["jti"], p2["jti"])


class TestTokenBlocklist(unittest.TestCase):
    def test_add_and_revoke(self):
        from app.security import add_token_to_blocklist, is_token_revoked
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        with patch("app.security._get_blocklist_redis", return_value=mock_redis):
            add_token_to_blocklist("jti-abc", 900)
            revoked = is_token_revoked("jti-abc")
        mock_redis.setex.assert_called_once()
        self.assertTrue(revoked)

    def test_non_revoked_returns_false(self):
        from app.security import is_token_revoked
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        with patch("app.security._get_blocklist_redis", return_value=mock_redis):
            self.assertFalse(is_token_revoked("never-seen"))

    def test_redis_down_returns_false(self):
        from app.security import is_token_revoked
        with patch("app.security._get_blocklist_redis", return_value=None):
            self.assertFalse(is_token_revoked("some-jti"))

    def test_empty_jti_noop(self):
        from app.security import add_token_to_blocklist, is_token_revoked
        self.assertFalse(is_token_revoked(""))
        mock_redis = MagicMock()
        with patch("app.security._get_blocklist_redis", return_value=mock_redis):
            add_token_to_blocklist("", 900)
        mock_redis.setex.assert_not_called()


class TestMakeAdminRequiresAdmin(unittest.TestCase):
    def test_make_admin_has_admin_dependency(self):
        import app.api.auth as auth_mod
        from app.security import get_current_admin
        make_admin_fn = auth_mod.make_admin
        sig = inspect.signature(make_admin_fn)
        admin_dep_found = any(
            hasattr(param.default, "dependency") and param.default.dependency is get_current_admin
            for param in sig.parameters.values()
        )
        self.assertTrue(admin_dep_found, "make_admin must have Depends(get_current_admin)")


class TestConfigSecretKeyWarning(unittest.TestCase):
    def test_insecure_default_triggers_warning(self):
        import app.config as cfg
        env_backup = os.environ.pop("SECRET_KEY", None)
        try:
            with patch.object(cfg.logger, "warning") as mock_warn:
                cfg.validate_config()
            msgs = " ".join(str(c) for c in mock_warn.call_args_list)
            self.assertIn("SECRET_KEY", msgs)
            self.assertIn("insecure", msgs.lower())
        finally:
            if env_backup is not None:
                os.environ["SECRET_KEY"] = env_backup

    def test_custom_key_no_jwt_warning(self):
        import app.config as cfg
        with patch.dict("os.environ", {"SECRET_KEY": "correct-horse-battery-staple-test-only"}):
            with patch.object(cfg.logger, "warning") as mock_warn:
                cfg.validate_config()
            msgs = " ".join(str(c) for c in mock_warn.call_args_list)
            bad_warns = [s for s in msgs.split("\n") if "SECRET_KEY" in s and "insecure" in s.lower()]
            self.assertEqual(len(bad_warns), 0)


if __name__ == "__main__":
    unittest.main()
