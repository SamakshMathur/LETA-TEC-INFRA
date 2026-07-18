import os
import logging
import re
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import requests as _requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.database import get_user_collection, get_otp_collection
from app.security import create_access_token, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Pydantic models ────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    full_name: str
    phone: str
    profession: str
    gender: str
    email: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_valid(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        return digits[-10:]  # store last 10 digits (strip country code)

    @field_validator("profession")
    @classmethod
    def profession_valid(cls, v):
        allowed = {
            "Advocate / Lawyer", "Chartered Accountant (CA)",
            "Company Secretary (CS)", "Tax Consultant",
            "Business Owner", "Finance Professional",
            "Government Official", "Student", "Other"
        }
        if v not in allowed:
            raise ValueError(f"Profession must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("gender")
    @classmethod
    def gender_valid(cls, v):
        allowed = {"Male", "Female", "Other", "Prefer not to say"}
        if v not in allowed:
            raise ValueError("Gender must be one of: Male, Female, Other, Prefer not to say")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError("Invalid email address")
        return v or None


class SendOTPRequest(BaseModel):
    contact: str          # email address OR 10-digit phone number
    method: Literal["email", "phone"]


class VerifyOTPRequest(BaseModel):
    contact: str
    otp: str

    @field_validator("otp")
    @classmethod
    def otp_is_6_digits(cls, v):
        if not re.match(r'^\d{6}$', v.strip()):
            raise ValueError("OTP must be exactly 6 digits")
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


# DEV_MODE=true → return otp_preview in response and skip strict OTP check.
_DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() == "true"


# ── OTP helpers ────────────────────────────────────────────────────────────────

def _generate_otp() -> str:
    return str(_secrets.randbelow(900000) + 100000)  # 6-digit: 100000–999999


def _send_sms_otp(phone: str, otp: str) -> None:
    """Send OTP via AWS SNS. Uses task role credentials — no API key needed."""
    import boto3
    try:
        # Normalise to E.164: strip leading zeros, prepend +91 for India
        number = phone.strip().lstrip("+")
        if len(number) == 10:
            number = "91" + number
        e164 = "+" + number
        sns = boto3.client("sns", region_name=os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))
        sns.publish(
            PhoneNumber=e164,
            Message=f"Your LETA OTP is {otp}. Valid for 10 minutes. Do not share.",
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"},
                "AWS.SNS.SMS.SenderID": {"DataType": "String", "StringValue": "LETATEC"},
            },
        )
        logger.info(f"SMS OTP sent via SNS | phone=***{phone[-4:]}")
    except Exception as e:
        logger.error(f"SMS delivery failed: {e}")


def _send_email_otp(email: str, otp: str) -> None:
    """Send OTP via Resend.com. Requires RESEND_API_KEY env var."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — email not sent")
        return
    try:
        resp = _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": "LETA <noreply@letatec.com>",
                "to": [email],
                "subject": "Your LETA Login OTP",
                "html": f"""
                <div style="font-family:monospace;background:#0a0a0a;color:#fff;
                            padding:40px;border-radius:12px;max-width:480px;margin:auto;
                            border:1px solid rgba(78,222,163,0.2)">
                  <h2 style="color:#4edea3;letter-spacing:0.1em;margin:0 0 8px">LETA TITAN</h2>
                  <p style="color:rgba(255,255,255,0.4);font-size:11px;
                             letter-spacing:0.15em;text-transform:uppercase;margin:0 0 32px">
                    Sovereign Compliance Systems
                  </p>
                  <p style="color:rgba(255,255,255,0.7);font-size:14px;margin:0 0 16px">
                    Your one-time login code:
                  </p>
                  <div style="background:rgba(78,222,163,0.08);border:1px solid rgba(78,222,163,0.3);
                              border-radius:8px;padding:24px;text-align:center;margin:0 0 24px">
                    <span style="color:#4edea3;font-size:36px;letter-spacing:12px;font-weight:bold">
                      {otp}
                    </span>
                  </div>
                  <p style="color:rgba(255,255,255,0.3);font-size:11px;margin:0">
                    Valid for 10 minutes. Do not share this code with anyone.
                  </p>
                </div>
                """,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"Email OTP sent | email={email[:3]}***{email[email.find('@'):]}")
    except Exception as e:
        logger.error(f"Email delivery failed: {e}")


# ── Password helpers (admin login only) ────────────────────────────────────────

import hashlib

def _hash_password(password: str) -> str:
    salt = _secrets.token_bytes(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hash_hex = stored_hash.split('$')
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return pwd_hash.hex() == hash_hex
    except (ValueError, AttributeError):
        return False


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register_user(user: UserRegister):
    """Create a new user account. After this, call /send-otp to verify and login."""
    users_col = get_user_collection()
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    if users_col.find_one({"phone": user.phone}):
        raise HTTPException(status_code=400, detail="Phone number already registered")
    if user.email and users_col.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.email:
        username = re.sub(r'[^a-zA-Z0-9_]', '_', user.email.split('@')[0])[:30]
    else:
        username = f"user_{user.phone[-6:]}"

    users_col.insert_one({
        "username": username,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "profession": user.profession,
        "gender": user.gender,
        "verified": False,
        "role": "user",
        "created_at": datetime.now(),
    })

    return {
        "message": "Account created successfully. Please verify your phone to login.",
        "username": username,
    }


@router.post("/send-otp")
async def send_otp(req: SendOTPRequest):
    """Generate and send a 6-digit OTP to the given contact (email or phone)."""
    otp_col = get_otp_collection()
    if otp_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    users_col = get_user_collection()
    if users_col is not None:
        field = "email" if req.method == "email" else "phone"
        if not users_col.find_one({field: req.contact}):
            if _DEV_MODE:
                # Auto-create a test user so dev login works without registration
                username = f"dev_{req.contact.replace('@','_').replace('.','_')[-10:]}"
                users_col.update_one(
                    {field: req.contact},
                    {"$setOnInsert": {
                        "username": username,
                        "full_name": "Dev User",
                        "phone": req.contact if req.method == "phone" else "",
                        "email": req.contact if req.method == "email" else None,
                        "profession": "Other",
                        "gender": "Prefer not to say",
                        "verified": False,
                        "role": "user",
                        "created_at": datetime.now(),
                    }},
                    upsert=True,
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No account found with that {req.method}. Please register first."
                )

    # Rate limit: max 3 OTPs per contact per hour
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent_count = otp_col.count_documents({
        "contact": req.contact,
        "created_at": {"$gte": one_hour_ago},
    })
    if recent_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="Too many OTP requests. Please wait before requesting again."
        )

    otp = _generate_otp()
    expires_at = datetime.now() + timedelta(minutes=10)

    otp_col.update_one(
        {"contact": req.contact},
        {"$set": {
            "contact": req.contact,
            "method": req.method,
            "otp": otp,
            "expires_at": expires_at,
            "verified": False,
            "created_at": datetime.now(),
        }},
        upsert=True,
    )

    if req.method == "phone":
        _send_sms_otp(req.contact, otp)
    else:
        _send_email_otp(req.contact, otp)

    body: dict = {"message": f"OTP sent to your {req.method}.", "expires_in_minutes": 10}
    if _DEV_MODE:
        body["otp_preview"] = otp
    return body


@router.post("/verify-otp", response_model=Token)
async def verify_otp(req: VerifyOTPRequest):
    """Verify the 6-digit OTP and receive JWT tokens."""
    otp_col = get_otp_collection()
    users_col = get_user_collection()

    if otp_col is None or users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    record = otp_col.find_one({"contact": req.contact, "verified": False})
    if not record:
        raise HTTPException(
            status_code=400,
            detail="No pending OTP for this contact. Please request a new OTP."
        )

    if datetime.now() > record["expires_at"]:
        otp_col.delete_one({"contact": req.contact})
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if not _DEV_MODE and record["otp"] != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP. Please try again.")

    otp_col.delete_one({"contact": req.contact})

    user = users_col.find_one(
        {"$or": [{"email": req.contact}, {"phone": req.contact}]},
        {"_id": 0}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    users_col.update_one(
        {"$or": [{"email": req.contact}, {"phone": req.contact}]},
        {"$set": {"verified": True, "last_login": datetime.now()}}
    )

    from app.security import create_refresh_token
    access_token  = create_access_token({"sub": user.get("username")})
    refresh_token = create_refresh_token({"sub": user.get("username")})
    now = int(datetime.now(timezone.utc).timestamp() * 1000)

    user_info = {
        "id": str(user.get("_id", "unknown")),
        "username": user.get("username"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "user"),
    }

    return {
        "tokens": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": now + (15 * 60 * 1000),
            "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
            "tokenType": "bearer",
        },
        "user": user_info,
        "memberships": [{"organizationId": "org_default", "role": user_info["role"]}],
        "organizationId": "org_default",
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "username":   current_user.get("username"),
        "full_name":  current_user.get("full_name"),
        "email":      current_user.get("email"),
        "phone":      current_user.get("phone"),
        "profession": current_user.get("profession"),
        "gender":     current_user.get("gender"),
        "verified":   current_user.get("verified", False),
        "role":       current_user.get("role", "user"),
    }


# ── Admin-only password login (not shown in UI) ────────────────────────────────

@router.post("/login", response_model=Token)
async def login(req: LoginRequest):
    """Admin-only password login. Regular users authenticate via OTP flow."""
    users_col = get_user_collection()

    _ADMIN_SECRET = os.getenv("ADMIN_MASTER_SECRET", "")
    if req.email == "admin@letatec.com" and _ADMIN_SECRET and req.password == _ADMIN_SECRET:
        user_info = {"id": "admin", "username": "admin", "email": req.email, "role": "admin"}
    else:
        user = users_col.find_one({"email": req.email}) if users_col else None
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not _verify_password(req.password, user.get("password", "")):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user_info = {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "admin"),
        }

    from app.security import create_refresh_token
    access_token  = create_access_token({"sub": user_info["username"]})
    refresh_token = create_refresh_token({"sub": user_info["username"]})
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
        "memberships": [{"organizationId": "org_default", "role": user_info["role"]}],
        "organizationId": "org_default",
    }


@router.post("/refresh", response_model=Token)
async def refresh(req: RefreshRequest):
    from app.security import verify_token, create_refresh_token
    payload = verify_token(req.refresh_token, "refresh")
    username = payload.get("sub")
    access_token = create_access_token({"sub": username})
    new_refresh  = create_refresh_token({"sub": username})
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "tokens": {
            "accessToken": access_token,
            "refreshToken": new_refresh,
            "expiresAt": now + (15 * 60 * 1000),
            "refreshTokenExpiresAt": now + (7 * 24 * 60 * 60 * 1000),
            "tokenType": "bearer",
        },
        "user": {"username": username},
        "memberships": [{"organizationId": "org_default", "role": "user"}],
        "organizationId": "org_default",
    }


# ── Admin elevation ────────────────────────────────────────────────────────────

class AdminSeedRequest(BaseModel):
    master_secret: str
    contact: str

@router.post("/make-admin", status_code=200)
async def make_admin(req: AdminSeedRequest):
    if req.master_secret != os.getenv("ADMIN_MASTER_SECRET", "change-this-secret"):
        raise HTTPException(status_code=403, detail="Invalid master secret")
    users_col = get_user_collection()
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    result = users_col.update_one(
        {"$or": [{"email": req.contact}, {"phone": req.contact}]},
        {"$set": {"role": "admin"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User '{req.contact}' is now an admin"}
