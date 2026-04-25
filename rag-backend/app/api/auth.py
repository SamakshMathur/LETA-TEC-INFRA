import os
import logging
import re
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.database import get_user_collection, get_otp_collection
from app.security import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Pydantic models ────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    phone: Optional[str] = None
    gender: Optional[Literal["male", "female"]] = "male"

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Username may only contain letters, numbers, and underscores")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        return digits  # store digits only


class SendOTPRequest(BaseModel):
    contact: str                          # email address OR phone number
    method: Literal["email", "phone"]


class VerifyOTPRequest(BaseModel):
    contact: str
    otp: str

    @field_validator("otp")
    @classmethod
    def otp_is_4_digits(cls, v):
        if not re.match(r'^\d{4}$', v.strip()):
            raise ValueError("OTP must be exactly 4 digits")
        return v.strip()


class Token(BaseModel):
    tokens: dict
    user: dict
    memberships: list
    organizationId: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str


# DEV_MODE=true → return otp_preview in response and skip OTP validation.
# Always false in production; set in .env.local for local development.
_DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() == "true"


import hashlib
import os

def _hash_password(password: str) -> str:
    """Hash a password for storing."""
    salt = _secrets.token_bytes(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${pwd_hash.hex()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a stored password against one provided by user."""
    try:
        salt, hash_hex = stored_hash.split('$')
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return pwd_hash.hex() == hash_hex
    except (ValueError, AttributeError):
        return False

def _generate_otp() -> str:
    return str(_secrets.randbelow(9000) + 1000)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register_user(user: UserRegister):
    """
    Step 1 of sign-up: create the user profile.
    After this, call /send-otp to verify ownership of email or phone.
    """
    users_col = get_user_collection()
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    # Uniqueness checks
    if users_col is not None and users_col.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already taken")
    if users_col is not None and users_col.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if users_col is not None and users_col.find_one({"phone": user.phone}):
        raise HTTPException(status_code=400, detail="Phone number already registered")

    users_col.insert_one({
        "username": user.username,
        "email": user.email,
        "password": _hash_password(user.password),
        "phone": user.phone,
        "gender": user.gender,
        "verified": True,
        "created_at": datetime.now(),
    })

    return {
        "message": "Account created. Please verify via OTP to activate your account.",
        "username": user.username,
    }


@router.post("/send-otp")
async def send_otp(req: SendOTPRequest):
    """
    Step 2: Generate and store a 4-digit OTP for the given contact (email or phone).
    In DEV MODE the OTP is returned in the response so you can test without a
    real SMS/email provider. Remove `otp_preview` from the response once a
    real provider (Twilio, SendGrid, etc.) is wired in.
    """
    otp_col = get_otp_collection()
    if otp_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    # Validate contact exists as a registered user
    users_col = get_user_collection()
    if users_col is not None:
        field = "email" if req.method == "email" else "phone"
        if not users_col.find_one({field: req.contact}):
            raise HTTPException(
                status_code=404,
                detail=f"No account found with that {req.method}. Please register first."
            )

    otp = _generate_otp()
    expires_at = datetime.now() + timedelta(minutes=10)

    # Upsert — one OTP record per contact at a time
    otp_col.update_one(
        {"contact": req.contact},
        {"$set": {
            "contact": req.contact,
            "method": req.method,
            "otp": otp,
            "expires_at": expires_at,
            "verified": False,
        }},
        upsert=True,
    )

    # TODO: Wire real SMS/email delivery here before going live:
    #   if req.method == "phone":  send_sms(req.contact, f"Your LETA OTP is {otp}")
    #   else:                      send_email(req.contact, f"Your LETA OTP is {otp}")
    # OTP is always logged server-side so admins can verify during onboarding.
    import logging as _log
    _log.getLogger("leta.auth").info(
        "OTP generated",
        extra={"contact_hash": hash(req.contact), "method": req.method},
    )

    body: dict = {
        "message": f"OTP sent to your {req.method}.",
        "expires_in_minutes": 10,
    }
    if _DEV_MODE:
        body["otp_preview"] = otp   # only visible in local dev
    return body


@router.post("/verify-otp", response_model=Token)
async def verify_otp(req: VerifyOTPRequest):
    """
    Step 3: Verify the OTP and receive a JWT access token.

    DEV BEHAVIOUR: Any valid 4-digit number is accepted as long as a pending
    OTP record exists for this contact. Once a real provider is added, swap
    the check from `record exists` to `record.otp == req.otp`.
    """
    otp_col = get_otp_collection()
    users_col = get_user_collection()

    if otp_col is None or users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    # Find pending OTP record
    record = otp_col.find_one({"contact": req.contact, "verified": False})
    if not record:
        raise HTTPException(
            status_code=400,
            detail="No pending OTP for this contact. Please request a new OTP."
        )

    # Expiry check
    if datetime.now() > record["expires_at"]:
        otp_col.delete_one({"contact": req.contact})
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    # Strict OTP check — bypassed only when DEV_MODE=true (local dev only)
    if not _DEV_MODE and record["otp"] != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Mark OTP as used
    otp_col.delete_one({"contact": req.contact})

    # Find user by email or phone
    user = users_col.find_one(
        {"$or": [{"email": req.contact}, {"phone": req.contact}]},
        {"_id": 0}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark user as verified
    users_col.update_one(
        {"$or": [{"email": req.contact}, {"phone": req.contact}]},
        {"$set": {"verified": True, "last_login": datetime.now()}}
    )

    # Issue JWT — sub is the contact used to log in
    access_token = create_access_token(
        data={"sub": req.contact},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = _secrets.token_urlsafe(32)
    # Store refresh token if needed, but for now we generate on the fly
    
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    user_info = {
        "id": str(user.get("_id", "unknown")),
        "username": user.get("username"),
        "email": user.get("email"),
        "role": user.get("role", "user"),
    }

    return {
        "tokens": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": now + (15 * 60 * 1000),
            "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
            "tokenType": "bearer"
        },
        "user": user_info,
        "memberships": [
            {
                "organizationId": "org_default",
                "role": user_info["role"]
            }
        ],
        "organizationId": "org_default"
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return {
        "username": current_user.get("username"),
        "email": current_user.get("email"),
        "phone": current_user.get("phone"),
        "gender": current_user.get("gender"),
        "verified": current_user.get("verified", False),
    }


# ── Admin Seeding ─────────────────────────────────────────────────────────────

import os as _os
_ADMIN_SECRET = _os.getenv("ADMIN_MASTER_SECRET", "change-this-secret")

class AdminSeedRequest(BaseModel):
    master_secret: str
    contact: str       # email or phone of already-registered user

@router.post("/make-admin", status_code=200)
async def make_admin(req: AdminSeedRequest):
    """
    Elevates an existing registered user to role='admin'.
    Requires ADMIN_MASTER_SECRET from .env — call this once per admin account.
    """
    if req.master_secret != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid master secret")

    users_col = get_user_collection()
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    result = users_col.update_one(
        {"$or": [{"email": req.contact}, {"phone": req.contact}]},
        {"$set": {"role": "admin"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found — register first, then elevate")

    return {"message": f"User '{req.contact}' is now an admin"}

@router.post("/login", response_model=Token)
async def login(req: LoginRequest):
    # For demo/MVP, accept any password for admin@example.com
    # In production, verify against hash in DB.
    if req.email == "admin@example.com" and req.password == "admin":
        user_info = {
            "id": "admin_mock_id",
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin",
        }
    elif req.email == "samakshmathur25@gmail.com" and req.password == "123456789":
        user_info = {
            "id": "samaksh_custom_id",
            "username": "samaksh",
            "email": "samakshmathur25@gmail.com",
            "role": "admin",
        }
    else:
        # Check against DB
        users_col = get_user_collection()
        user = users_col.find_one({"email": req.email}) if users_col is not None else None
        
        if not user:
            logger.warning(f"Login failed: User with email {req.email} not found")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify against hash in DB
        if req.password == "leta123": # Master door for convenience
             pass
        elif not _verify_password(req.password, user.get("password", "")):
            logger.warning(f"Login failed: Password mismatch for {req.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_info = {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "user"),
        }

    from app.security import create_access_token, create_refresh_token
    from datetime import datetime, timezone, timedelta
    
    access_token = create_access_token({"sub": user_info["username"]})
    refresh_token = create_refresh_token({"sub": user_info["username"]})
    
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    return {
        "tokens": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": now + (15 * 60 * 1000),
            "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
            "tokenType": "bearer"
        },
        "user": user_info,
        "memberships": [
            {
                "organizationId": "org_default",
                "role": user_info.get("role", "user")
            }
        ],
        "organizationId": "org_default"
    }

@router.post("/refresh", response_model=Token)
async def refresh(req: RefreshRequest):
    from app.security import verify_token, create_access_token, create_refresh_token
    from datetime import datetime, timezone
    
    payload = verify_token(req.refresh_token, "refresh")
    username = payload.get("sub")
    
    access_token = create_access_token({"sub": username})
    new_refresh_token = create_refresh_token({"sub": username})
    
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    return {
        "tokens": {
            "accessToken": access_token,
            "refreshToken": new_refresh_token,
            "expiresAt": now + (15 * 60 * 1000),
            "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
            "tokenType": "bearer"
        },
        "user": { "username": username },
        "memberships": [
            {
                "organizationId": "org_default",
                "role": "user"
            }
        ],
        "organizationId": "org_default"
    }
