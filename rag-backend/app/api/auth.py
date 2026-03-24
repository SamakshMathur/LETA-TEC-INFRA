import random
import re
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

from app.database import get_user_collection, get_otp_collection
from app.security import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

# ── Pydantic models ────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    email: str
    phone: str
    gender: Literal["male", "female"]

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
    access_token: str
    token_type: str
    user_info: dict


# ── Helper ─────────────────────────────────────────────────────────────────────

def _generate_otp() -> str:
    return str(random.randint(1000, 9999))


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
    if users_col.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already taken")
    if users_col.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if users_col.find_one({"phone": user.phone}):
        raise HTTPException(status_code=400, detail="Phone number already registered")

    users_col.insert_one({
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "gender": user.gender,
        "verified": False,
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

    # ── DEV MODE: return otp_preview ──────────────────────────────────────────
    # TODO: Replace this block with real SMS/email delivery before going live.
    # e.g.  send_sms(req.contact, f"Your LETA OTP is {otp}")
    #        send_email(req.contact, f"Your LETA OTP is {otp}")
    return {
        "message": f"OTP generated. In production it would be sent to your {req.method}.",
        "otp_preview": otp,          # ← REMOVE IN PRODUCTION
        "expires_in_minutes": 10,
    }


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

    # ── DEV MODE: accept any 4-digit number ───────────────────────────────────
    # Production: uncomment the strict check below and remove the pass.
    # if record["otp"] != req.otp:
    #     raise HTTPException(status_code=400, detail="Invalid OTP")
    # ─────────────────────────────────────────────────────────────────────────

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

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "username": user.get("username"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "gender": user.get("gender"),
        },
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
