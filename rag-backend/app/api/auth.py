import os
import logging
import re
import secrets as _secrets
import hashlib
import time

from datetime import datetime, timedelta, timezone
from app.utils.time import utc_now
from typing import Literal, Optional

import requests as _requests

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator, model_validator
from pymongo.errors import DuplicateKeyError

from app.activity_logger import log_activity
from app.database import (
    get_user_collection,
    get_otp_collection,
    get_session_collection,
)

from app.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    get_current_admin,
    is_admin,
    add_token_to_blocklist,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _utc_aware(value):
    """Normalize a datetime to timezone-aware UTC."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    return value


# =============================================================================
# CONFIG
# =============================================================================

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

OTP_EXPIRY_MINUTES = 2        # 2 minutes to match registered Airtel DLT template
OTP_RESEND_COOLDOWN_SECONDS = 60  # 60-second cooldown between resend requests
OTP_RATE_LIMIT_PER_HOUR = 3
MAX_OTP_ATTEMPTS = 5          # Max failed verify attempts before OTP is burned

ADMIN_MASTER_SECRET = os.getenv("ADMIN_MASTER_SECRET", "")

FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


# =============================================================================
# MODELS
# =============================================================================

class UserRegister(BaseModel):
    full_name: str
    phone: str
    profession: str
    gender: str
    email: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        v = v.strip()

        if len(v) < 2:
            raise ValueError("Full name must contain at least 2 characters")

        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        digits = re.sub(r"\D", "", v)

        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits")

        return digits[-10:]

    @field_validator("profession")
    @classmethod
    def validate_profession(cls, v):

        allowed = {
            "Advocate / Lawyer",
            "Chartered Accountant (CA)",
            "Company Secretary (CS)",
            "Tax Consultant",
            "Business Owner",
            "Finance Professional",
            "Government Official",
            "Student",
            "Other",
        }

        if v not in allowed:
            raise ValueError("Invalid profession")

        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):

        allowed = {
            "Male",
            "Female",
            "Other",
            "Prefer not to say",
        }

        if v not in allowed:
            raise ValueError("Invalid gender")

        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):

        if v is None:
            return None

        v = v.strip().lower()

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email")

        return v


class SendOTPRequest(BaseModel):
    contact: str
    method: Literal["email", "phone"]

    @model_validator(mode="after")
    def validate_contact(self):
        contact = self.contact.strip()

        if self.method == "email":
            contact = contact.lower()

            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", contact):
                raise ValueError("Invalid email")

        else:
            digits = re.sub(r"\D", "", contact)

            if len(digits) < 10:
                raise ValueError("Phone number must contain at least 10 digits")

            contact = digits[-10:]

        self.contact = contact
        return self


class VerifyOTPRequest(BaseModel):
    contact: str
    otp: str

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, v):
        v = v.strip()

        if "@" in v:
            v = v.lower()

            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                raise ValueError("Invalid email")

            return v

        digits = re.sub(r"\D", "", v)

        if len(digits) >= 10:
            return digits[-10:]

        return v

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v):

        v = v.strip()

        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be exactly 6 digits")

        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class AdminSeedRequest(BaseModel):
    master_secret: str
    contact: str


class Token(BaseModel):
    tokens: dict
    user: dict
    memberships: list
    organizationId: Optional[str] = None


# =============================================================================
# HELPERS
# =============================================================================
class RefreshRequest(BaseModel):
    refresh_token: str


# DEV_MODE=true → return otp_preview in response and skip strict OTP check.
# Default is false (production-safe). Set DEV_MODE=true only for local testing.
_DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() == "true"
if _DEV_MODE:
    logger.critical(
        "DEV_MODE=true — OTP verification is BYPASSED and users auto-create without registration. "
        "This MUST NOT be active in production. Remove DEV_MODE from the environment before deploying."
    )

# Session durations per plan (seconds). Admin role is exempt — no timer.
PLAN_DURATIONS: dict[str, int] = {
    "basic": 1 * 60 * 60,   # ₹500 → 1 hour
    "pro":   3 * 60 * 60,   # ₹1000 → 3 hours
}


# ── OTP helpers ────────────────────────────────────────────────────────────────

def _generate_otp() -> str:
    return str(_secrets.randbelow(900000) + 100000)


def _hash_password(password: str) -> str:
    salt = _secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        100000,
    )
    return f"{salt}${pwd_hash.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hash_hex = stored_hash.split("$")
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000,
        )
        return _secrets.compare_digest(pwd_hash.hex(), hash_hex)
    except Exception:
        return False


def _verify_secret(value: str, expected: str) -> bool:
    if not value or not expected:
        return False
    return _secrets.compare_digest(value, expected)


def send_sms_otp(phone: str, otp: str) -> bool:
    """Dispatch SMS OTP using configured provider (Airtel DLT primary, AWS SNS/Fast2SMS fallback)."""
    if DEV_MODE:
        logger.info(f"[DEV MODE] SMS OTP dispatched for ***{phone[-4:]} (mock delivery)")
        return True

    from app.services.sms import send_sms_otp as _dispatch_sms
    res = _dispatch_sms(phone, otp, template_type="registration")
    return res.success


def verify_sms_otp(phone: str, submitted_otp: str, expected_otp: str) -> bool:
    is_prod = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
    if DEV_MODE and not is_prod:
        return bool(re.match(r"^\d{6}$", submitted_otp))
    return _secrets.compare_digest(expected_otp, submitted_otp)



def _send_email_otp(email: str, otp: str) -> None:

    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY missing — Email not sent")
        return

    try:
        response = _requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": "LETA <noreply@letatec.com>",
                "to": [email],
                "subject": "Your LETA OTP",
                "html": f"""
                <div style="font-family:Arial;padding:30px">
                    <h2>LETA Login Verification</h2>
                    <p>Your OTP is:</p>
                    <h1>{otp}</h1>
                    <p>This OTP expires in {OTP_EXPIRY_MINUTES} minutes.</p>
                </div>
                """,
            },
            timeout=10,
        )

        response.raise_for_status()

        logger.info(f"Email OTP sent to {email}")

    except Exception as e:
        logger.error(f"Email sending failed: {e}")


def _build_auth_response(user_info: dict, session_end_ms: Optional[int] = None):

    access_token = create_access_token({
        "sub": user_info["username"]
    })

    refresh_token = create_refresh_token({
        "sub": user_info["username"]
    })

    now = int(utc_now().timestamp() * 1000)

    tokens = {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": now + (15 * 60 * 1000),
        "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
        "tokenType": "bearer",
    }
    if session_end_ms is not None:
        tokens["session_end_ms"] = session_end_ms

    return {
        "tokens": tokens,
        "user": user_info,
        "memberships": [
            {
                "organizationId": "org_default",
                "role": user_info["role"],
            }
        ],
        "organizationId": "org_default",
    }


def _elapsed_ms(started_at: float) -> float:
    return (time.monotonic() - started_at) * 1000


def _auth_contact_metadata(contact: str, method: Optional[str] = None) -> dict:
    metadata = {"method": method} if method else {}
    if method == "phone" or (method is None and "@" not in contact):
        metadata["phone"] = contact
    else:
        metadata["email"] = contact
    return metadata


def _log_auth_activity(
    *,
    request: Request,
    started_at: float,
    action: str,
    user: Optional[dict] = None,
    metadata: Optional[dict] = None,
    success: bool = True,
) -> None:
    log_activity(
        user=user,
        action=action,
        category="authentication",
        metadata=metadata or {},
        request=request,
        success=success,
        duration=_elapsed_ms(started_at),
    )


# =============================================================================
# REGISTER
# =============================================================================

@router.post("/register", status_code=201)
async def register_user(request: Request, user: UserRegister):
    started_at = time.monotonic()

    users_col = get_user_collection()

    if users_col is None:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="register",
            metadata={"phone": user.phone, "email": user.email, "error": "database_unavailable"},
            success=False,
        )
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    existing_phone = users_col.find_one({
        "phone": user.phone
    })

    if existing_phone:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="register",
            metadata={"phone": user.phone, "email": user.email, "error": "phone_already_registered"},
            success=False,
        )
        raise HTTPException(
            status_code=400,
            detail="Phone number already registered",
        )

    if user.email:

        existing_email = users_col.find_one({
            "email": user.email
        })

        if existing_email:
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="register",
                metadata={"phone": user.phone, "email": user.email, "error": "email_already_registered"},
                success=False,
            )
            raise HTTPException(
                status_code=400,
                detail="Email already registered",
            )

    username = (
        re.sub(r"[^a-zA-Z0-9_]", "_", user.email.split("@")[0])[:30]
        if user.email
        else f"user_{user.phone[-6:]}"
    )

    users_col.insert_one({
        "username": username,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "profession": user.profession,
        "gender": user.gender,
        "verified": False,
        "role": "user",
        "plan": "basic",
        "created_at": utc_now(),
        "last_login": None,
    })

    logger.info(f"User registered | username={username}")
    _log_auth_activity(
        request=request,
        started_at=started_at,
        action="register",
        user={
            "username": username,
            "phone": user.phone,
            "email": user.email,
        },
        metadata={"phone": user.phone, "email": user.email},
    )

    return {
        "message": "Account created successfully",
        "username": username,
    }


# =============================================================================
# SEND OTP
# =============================================================================

@router.post("/send-otp")
async def send_otp(request: Request, req: SendOTPRequest):
    started_at = time.monotonic()

    otp_col = get_otp_collection()
    users_col = get_user_collection()

    if otp_col is None or users_col is None:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="send_otp",
            metadata={**_auth_contact_metadata(req.contact, req.method), "error": "database_unavailable"},
            success=False,
        )
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    field = "email" if req.method == "email" else "phone"

    user = users_col.find_one({
        field: req.contact
    })

    if not user:
        if not DEV_MODE:
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="send_otp",
                metadata={**_auth_contact_metadata(req.contact, req.method), "error": "account_not_found"},
                success=False,
            )
            raise HTTPException(
                status_code=404,
                detail=f"No account found with that {req.method}. Please register first.",
            )

        username = f"dev_{re.sub(r'[^a-zA-Z0-9_]', '_', req.contact)[-30:]}"
        user_doc = {
            "username": username,
            "full_name": "Dev User",
            "profession": "Other",
            "gender": "Prefer not to say",
            "verified": False,
            "role": "user",
            "created_at": utc_now(),
            "last_login": None,
        }

        if req.method == "phone":
            user_doc["phone"] = req.contact
        else:
            user_doc["email"] = req.contact

        try:
            users_col.update_one(
                {field: req.contact},
                {"$setOnInsert": user_doc},
                upsert=True,
            )
        except DuplicateKeyError:
            logger.warning(
                "Duplicate user key while creating dev OTP user",
                extra={"method": req.method},
            )
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="send_otp",
                metadata={**_auth_contact_metadata(req.contact, req.method), "error": "duplicate_user_key"},
                success=False,
            )
            raise HTTPException(
                status_code=409,
                detail=f"An account with that {req.method} already exists.",
            )
        user = users_col.find_one({
            field: req.contact
        })

    now = utc_now()
    one_hour_ago = now - timedelta(hours=1)

    otp_record = otp_col.find_one({
        "contact": req.contact
    })

    rate_window_start = None
    request_count = 0

    if otp_record:
        # Enforce 60-second resend cooldown
        created_at = _utc_aware(otp_record.get("created_at"))
        if created_at and (now - created_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
            cooldown_remaining = max(1, int(OTP_RESEND_COOLDOWN_SECONDS - (now - created_at).total_seconds()))
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="send_otp",
                user=user,
                metadata={**_auth_contact_metadata(req.contact, req.method), "error": "resend_cooldown_active"},
                success=False,
            )
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {cooldown_remaining} seconds before requesting a new OTP.",
            )

        rate_window_start = _utc_aware(
            otp_record.get("rate_window_start")
            or otp_record.get("created_at")
        )

        if rate_window_start and rate_window_start >= one_hour_ago:
            request_count = otp_record.get("request_count", 1)
        else:
            rate_window_start = None

    if request_count >= OTP_RATE_LIMIT_PER_HOUR:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="send_otp",
            user=user,
            metadata={**_auth_contact_metadata(req.contact, req.method), "error": "rate_limited"},
            success=False,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many OTP requests. Please try again in an hour.",
        )

    otp = _generate_otp()
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    rate_window_start = rate_window_start or now
    request_count += 1

    expires_at = now + timedelta(
        minutes=OTP_EXPIRY_MINUTES
    )

    otp_col.update_one(
        {"contact": req.contact},
        {
            "$set": {
                "contact": req.contact,
                "method": req.method,
                "otp_hash": otp_hash,        # hashed — raw OTP never stored
                "verified": False,
                "failed_attempts": 0,         # brute-force counter reset on fresh OTP
                "created_at": now,
                "expires_at": expires_at,
                "rate_window_start": rate_window_start,
                "request_count": request_count,
            }
        },
        upsert=True,
    )

    if req.method == "phone":
        sms_ok = send_sms_otp(req.contact, otp)
        if not sms_ok and not DEV_MODE:
            # Transactional safety: don't leave active OTP record if provider failed
            otp_col.delete_one({"contact": req.contact})
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="send_otp",
                user=user,
                metadata={**_auth_contact_metadata(req.contact, req.method), "error": "sms_delivery_failed"},
                success=False,
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to send SMS OTP. Please check the mobile number and try again.",
            )
    else:
        _send_email_otp(req.contact, otp)

    response = {
        "message": "OTP sent successfully",
        "expires_in_minutes": OTP_EXPIRY_MINUTES,
        "cooldown_seconds": OTP_RESEND_COOLDOWN_SECONDS,
    }

    if DEV_MODE:
        response["otp_preview"] = otp


    _log_auth_activity(
        request=request,
        started_at=started_at,
        action="send_otp",
        user=user,
        metadata=_auth_contact_metadata(req.contact, req.method),
    )

    return response


# =============================================================================
# VERIFY OTP
# =============================================================================

@router.post("/verify-otp", response_model=Token)
async def verify_otp(request: Request, req: VerifyOTPRequest):
    started_at = time.monotonic()

    otp_col = get_otp_collection()
    users_col = get_user_collection()

    if otp_col is None or users_col is None:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="verify_otp",
            metadata={**_auth_contact_metadata(req.contact), "error": "database_unavailable"},
            success=False,
        )
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    otp_record = otp_col.find_one({
        "contact": req.contact,
        "verified": False,
    })

    if not otp_record:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="verify_otp",
            metadata={**_auth_contact_metadata(req.contact), "error": "no_pending_otp"},
            success=False,
        )
        raise HTTPException(
            status_code=400,
            detail="No pending OTP found",
        )

    expires_at = _utc_aware(otp_record.get("expires_at"))

    if expires_at and utc_now() > expires_at:

        otp_col.delete_one({
            "contact": req.contact
        })

        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="verify_otp",
            metadata={**_auth_contact_metadata(req.contact, otp_record.get("method")), "error": "otp_expired"},
            success=False,
        )
        raise HTTPException(
            status_code=400,
            detail="OTP expired",
        )

    # ── OTP Verification (hash-based, brute-force protected) ────────────────────────────────────
    def _otp_matches() -> bool:
        """Return True if the submitted OTP matches the stored hash (or legacy plaintext)."""
        stored_hash = otp_record.get("otp_hash")
        if stored_hash:
            submitted_hash = hashlib.sha256(req.otp.encode()).hexdigest()
            return _secrets.compare_digest(stored_hash, submitted_hash)
        # Legacy records written before this migration: compare plaintext (migration window only)
        legacy_otp = otp_record.get("otp", "")
        return _secrets.compare_digest(legacy_otp, req.otp)

    is_prod = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
    if DEV_MODE and not is_prod:
        otp_valid = bool(re.match(r"^\d{6}$", req.otp))  # any valid 6-digit OTP passes in dev
    else:
        otp_valid = _otp_matches()


    if not otp_valid:
        new_attempts = otp_record.get("failed_attempts", 0) + 1
        if new_attempts >= MAX_OTP_ATTEMPTS:
            # Burn the OTP — attacker must request a fresh one
            otp_col.delete_one({"contact": req.contact})
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="verify_otp",
                metadata={
                    **_auth_contact_metadata(req.contact, otp_record.get("method")),
                    "error": "otp_max_attempts_exceeded",
                },
                success=False,
            )
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Please request a new OTP.",
            )
        otp_col.update_one(
            {"contact": req.contact},
            {"$set": {"failed_attempts": new_attempts}},
        )
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="verify_otp",
            metadata={
                **_auth_contact_metadata(req.contact, otp_record.get("method")),
                "error": "invalid_otp",
                "attempts_remaining": MAX_OTP_ATTEMPTS - new_attempts,
            },
            success=False,
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP",
        )

    # OTP correct — consume it immediately to prevent replay
    otp_col.delete_one({"contact": req.contact})

    user = users_col.find_one({
        "$or": [
            {"email": req.contact},
            {"phone": req.contact},
        ]
    })

    if not user:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="verify_otp",
            metadata={**_auth_contact_metadata(req.contact, otp_record.get("method")), "error": "user_not_found"},
            success=False,
        )
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    role    = user.get("role", "user")
    plan    = user.get("plan", "basic")
    now_utc = utc_now()
    now_ms  = int(now_utc.timestamp() * 1000)

    # Session timer is NOT started at login — it only starts after payment (see payments.py).
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "verified":   True,
            "last_login": now_utc,
        }}
    )

    user_info = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user.get("email"),
        "phone": user.get("phone"),
        "full_name": user.get("full_name"),
        "role":      role,
        "plan":      plan,
    }

    _log_auth_activity(
        request=request,
        started_at=started_at,
        action="verify_otp",
        user=user_info,
        metadata=_auth_contact_metadata(req.contact, otp_record.get("method")),
    )

    session_end_ms = user.get("session_end_ms")
    return _build_auth_response(user_info, session_end_ms=session_end_ms)


# =============================================================================
# LOGIN
# =============================================================================

@router.post("/login", response_model=Token)
async def login(request: Request, req: LoginRequest):
    started_at = time.monotonic()

    users_col = get_user_collection()

    if req.email == "admin@letatec.com":

        if not ADMIN_MASTER_SECRET:
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="login",
                metadata={"email": req.email, "error": "admin_secret_not_configured"},
                success=False,
            )
            raise HTTPException(
                status_code=500,
                detail="Admin secret not configured",
            )

        if not _verify_secret(req.password, ADMIN_MASTER_SECRET):
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="login",
                metadata={"email": req.email, "error": "invalid_credentials"},
                success=False,
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials",
            )

        admin_info = {
            "id": "admin",
            "username": "admin",
            "email": req.email,
            "role": "admin",
        }

        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="login",
            user=admin_info,
            metadata={"email": req.email},
        )
        return _build_auth_response(admin_info)

    if users_col is None:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="login",
            metadata={"email": req.email, "error": "database_unavailable"},
            success=False,
        )
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    user = users_col.find_one({
        "email": req.email
    })

    if not user:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="login",
            metadata={"email": req.email, "error": "invalid_credentials"},
            success=False,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    if not is_admin(user):
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="login",
            user=user,
            metadata={"email": req.email, "error": "password_login_forbidden"},
            success=False,
        )
        raise HTTPException(
            status_code=403,
            detail="Only admins can login with password",
        )

    if not _verify_password(
        req.password,
        user.get("password", ""),
    ):
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="login",
            user=user,
            metadata={"email": req.email, "error": "invalid_credentials"},
            success=False,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    user_info = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "role": user.get("role", "admin"),
    }

    _log_auth_activity(
        request=request,
        started_at=started_at,
        action="login",
        user=user_info,
        metadata={"email": req.email},
    )

    return _build_auth_response(user_info)


# =============================================================================
# REFRESH
# =============================================================================

@router.post("/refresh", response_model=Token)
async def refresh(request: Request, req: RefreshRequest):
    started_at = time.monotonic()

    try:
        payload = verify_token(
            req.refresh_token,
            "refresh",
        )
    except HTTPException as e:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="refresh_token",
            metadata={"error": "invalid_refresh_token", "status_code": e.status_code},
            success=False,
        )
        raise

    username = payload.get("sub")

    users_col = get_user_collection()

    if username == "admin":
        if not ADMIN_MASTER_SECRET:
            _log_auth_activity(
                request=request,
                started_at=started_at,
                action="refresh_token",
                metadata={"username": username, "error": "admin_secret_not_configured"},
                success=False,
            )
            raise HTTPException(
                status_code=500,
                detail="Admin secret not configured",
            )

        admin_info = {
            "id": "admin",
            "username": "admin",
            "email": "admin@letatec.com",
            "role": "admin",
        }

        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="refresh_token",
            user=admin_info,
            metadata={"username": username},
        )
        return _build_auth_response(admin_info)

    if users_col is None:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="refresh_token",
            metadata={"username": username, "error": "database_unavailable"},
            success=False,
        )
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    user = users_col.find_one({
        "username": username
    })

    if not user:
        _log_auth_activity(
            request=request,
            started_at=started_at,
            action="refresh_token",
            metadata={"username": username, "error": "user_not_found"},
            success=False,
        )
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user_info = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user.get("email"),
        "phone": user.get("phone"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "user"),
    }

    _log_auth_activity(
        request=request,
        started_at=started_at,
        action="refresh_token",
        user=user_info,
        metadata={"username": username},
    )

    return _build_auth_response(user_info)


# =============================================================================
# CURRENT USER
# =============================================================================

@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user)
):
    return current_user


# =============================================================================
# LOGOUT
# =============================================================================

@router.post("/logout")
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    started_at = time.monotonic()

    # Revoke the current access token by adding its jti to the blocklist
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[len("Bearer "):].strip()
        try:
            payload = verify_token(raw_token, "access")
            jti = payload.get("jti")
            if jti:
                # TTL: remainder of the token's 15-minute window (worst case = full window)
                add_token_to_blocklist(jti, ttl_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        except Exception:
            pass  # expired/invalid token — no need to blocklist

    _log_auth_activity(
        request=request,
        started_at=started_at,
        action="logout",
        user=current_user,
        metadata={"username": current_user.get("username")},
    )
    return {"message": "Logged out successfully"}


# =============================================================================
# MAKE ADMIN
# =============================================================================

@router.post("/make-admin")
async def make_admin(
    req: AdminSeedRequest,
    _admin: dict = Depends(get_current_admin),  # must be authenticated admin
):

    if not _verify_secret(req.master_secret, ADMIN_MASTER_SECRET):
        raise HTTPException(
            status_code=403,
            detail="Invalid master secret",
        )

    users_col = get_user_collection()

    if users_col is None:
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    result = users_col.update_one(
        {
            "$or": [
                {"email": req.contact},
                {"phone": req.contact},
            ]
        },
        {
            "$set": {
                "role": "admin",
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    logger.info(f"Admin elevated | contact={req.contact}")

    return {
        "message": f"{req.contact} is now admin"
    }
