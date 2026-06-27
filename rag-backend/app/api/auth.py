import os
import logging
import re
import secrets as _secrets
import hashlib

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import requests as _requests

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator, model_validator

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
)

router = APIRouter()
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG
# =============================================================================

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

OTP_EXPIRY_MINUTES = 10
OTP_RATE_LIMIT_PER_HOUR = 3

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


class RefreshRequest(BaseModel):
    refresh_token: str


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

        return pwd_hash.hex() == hash_hex

    except Exception:
        return False


def _send_sms_otp(phone: str, otp: str) -> None:

    if not FAST2SMS_API_KEY:
        logger.warning("FAST2SMS_API_KEY missing — SMS not sent")
        return

    try:
        response = _requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={
                "authorization": FAST2SMS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "route": "otp",
                "variables_values": otp,
                "numbers": phone,
            },
            timeout=10,
        )

        response.raise_for_status()

        logger.info(f"SMS OTP sent to ***{phone[-4:]}")

    except Exception as e:
        logger.error(f"SMS sending failed: {e}")


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


def _build_auth_response(user_info: dict):

    access_token = create_access_token({
        "sub": user_info["username"]
    })

    refresh_token = create_refresh_token({
        "sub": user_info["username"]
    })

    now = int(datetime.now(timezone.utc).timestamp() * 1000)

    return {
        "tokens": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": now + (15 * 60 * 1000),
            "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
            "tokenType": "bearer",
        },
        "user": user_info,
        "memberships": [
            {
                "organizationId": "org_default",
                "role": user_info["role"],
            }
        ],
        "organizationId": "org_default",
    }


# =============================================================================
# REGISTER
# =============================================================================

@router.post("/register", status_code=201)
async def register_user(user: UserRegister):

    users_col = get_user_collection()

    if users_col is None:
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    existing_phone = users_col.find_one({
        "phone": user.phone
    })

    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="Phone number already registered",
        )

    if user.email:

        existing_email = users_col.find_one({
            "email": user.email
        })

        if existing_email:
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
        "created_at": datetime.utcnow(),
        "last_login": None,
    })

    logger.info(f"User registered | username={username}")

    return {
        "message": "Account created successfully",
        "username": username,
    }


# =============================================================================
# SEND OTP
# =============================================================================

@router.post("/send-otp")
async def send_otp(req: SendOTPRequest):

    otp_col = get_otp_collection()
    users_col = get_user_collection()

    if otp_col is None or users_col is None:
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
            raise HTTPException(
                status_code=404,
                detail=f"No account found with that {req.method}. Please register first.",
            )

        username = f"dev_{re.sub(r'[^a-zA-Z0-9_]', '_', req.contact)[-30:]}"
        users_col.update_one(
            {field: req.contact},
            {
                "$setOnInsert": {
                    "username": username,
                    "full_name": "Dev User",
                    "phone": req.contact if req.method == "phone" else "",
                    "email": req.contact if req.method == "email" else None,
                    "profession": "Other",
                    "gender": "Prefer not to say",
                    "verified": False,
                    "role": "user",
                    "created_at": datetime.utcnow(),
                    "last_login": None,
                }
            },
            upsert=True,
        )
        user = users_col.find_one({
            field: req.contact
        })

    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)

    otp_record = otp_col.find_one({
        "contact": req.contact
    })

    rate_window_start = None
    request_count = 0

    if otp_record:
        rate_window_start = (
            otp_record.get("rate_window_start")
            or otp_record.get("created_at")
        )

        if rate_window_start and rate_window_start >= one_hour_ago:
            request_count = otp_record.get("request_count", 1)
        else:
            rate_window_start = None

    if request_count >= OTP_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many OTP requests",
        )

    otp = _generate_otp()
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
                "otp": otp,
                "verified": False,
                "created_at": now,
                "expires_at": expires_at,
                "rate_window_start": rate_window_start,
                "request_count": request_count,
            }
        },
        upsert=True,
    )

    if req.method == "phone":
        _send_sms_otp(req.contact, otp)
    else:
        _send_email_otp(req.contact, otp)

    response = {
        "message": "OTP sent successfully",
        "expires_in_minutes": OTP_EXPIRY_MINUTES,
    }

    if DEV_MODE:
        response["otp_preview"] = otp

    return response


# =============================================================================
# VERIFY OTP
# =============================================================================

@router.post("/verify-otp", response_model=Token)
async def verify_otp(req: VerifyOTPRequest):

    otp_col = get_otp_collection()
    users_col = get_user_collection()

    if otp_col is None or users_col is None:
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    otp_record = otp_col.find_one({
        "contact": req.contact,
        "verified": False,
    })

    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="No pending OTP found",
        )

    if datetime.utcnow() > otp_record["expires_at"]:

        otp_col.delete_one({
            "contact": req.contact
        })

        raise HTTPException(
            status_code=400,
            detail="OTP expired",
        )

    if not DEV_MODE and otp_record["otp"] != req.otp:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP",
        )

    otp_col.delete_one({
        "contact": req.contact
    })

    user = users_col.find_one({
        "$or": [
            {"email": req.contact},
            {"phone": req.contact},
        ]
    })

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    users_col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "verified": True,
                "last_login": datetime.utcnow(),
            }
        },
    )

    user_info = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user.get("email"),
        "phone": user.get("phone"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "user"),
    }

    return _build_auth_response(user_info)


# =============================================================================
# LOGIN
# =============================================================================

@router.post("/login", response_model=Token)
async def login(req: LoginRequest):

    users_col = get_user_collection()

    if req.email == "admin@letatec.com":

        if not ADMIN_MASTER_SECRET:
            raise HTTPException(
                status_code=500,
                detail="Admin secret not configured",
            )

        if req.password != ADMIN_MASTER_SECRET:
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

        return _build_auth_response(admin_info)

    if users_col is None:
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    user = users_col.find_one({
        "email": req.email
    })

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can login with password",
        )

    if not _verify_password(
        req.password,
        user.get("password", ""),
    ):
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

    return _build_auth_response(user_info)


# =============================================================================
# REFRESH
# =============================================================================

@router.post("/refresh", response_model=Token)
async def refresh(req: RefreshRequest):

    payload = verify_token(
        req.refresh_token,
        "refresh",
    )

    username = payload.get("sub")

    users_col = get_user_collection()

    if users_col is None:
        raise HTTPException(
            status_code=500,
            detail="Database not connected",
        )

    user = users_col.find_one({
        "username": username
    })

    if not user:
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
# MAKE ADMIN
# =============================================================================

@router.post("/make-admin")
async def make_admin(req: AdminSeedRequest):

    if req.master_secret != ADMIN_MASTER_SECRET:
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
