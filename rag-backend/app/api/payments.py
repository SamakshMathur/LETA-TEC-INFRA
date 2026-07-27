"""Razorpay payment integration.

Routes
------
POST /api/payments/create-order   — create a Razorpay order
POST /api/payments/verify          — verify payment signature after checkout
GET  /api/payments/config          — return Razorpay key_id to frontend (safe)
"""
import os
import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security import get_current_user
from app.database import get_user_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

# ── Plans ──────────────────────────────────────────────────────────────────────
PLANS = {
    "1hr": {
        "name": "1-Hour Access",
        "description": "Full module access for 1 hour",
        "amount": 49900,        # paise (₹499 × 100)
        "currency": "INR",
        "duration_hours": 1,
    },
    "3hr": {
        "name": "3-Hour Access",
        "description": "Full module access for 3 hours",
        "amount": 99900,        # paise (₹999 × 100)
        "currency": "INR",
        "duration_hours": 3,
    },
}


def _razorpay_client():
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail="Payment system not yet configured. Please add Razorpay keys to activate."
        )
    import razorpay
    return razorpay.Client(auth=(key_id, key_secret))


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan_id: str     # "1hr" or "3hr"
    module: str      # "gst" | "fema" | "company-law" | "income-tax"

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str
    module: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config")
def get_payment_config():
    """Return the Razorpay publishable key to the frontend. Never exposes the secret."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    return {
        "key_id": key_id,
        "configured": bool(key_id),
        "plans": PLANS,
    }


@router.post("/create-order")
def create_order(req: CreateOrderRequest):
    plan = PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {req.plan_id}")

    client = _razorpay_client()
    order = client.order.create({
        "amount": plan["amount"],
        "currency": plan["currency"],
        "receipt": f"{req.module}_{req.plan_id}",
        "notes": {
            "module": req.module,
            "plan_id": req.plan_id,
            "duration_hours": str(plan["duration_hours"]),
        },
    })
    logger.info(f"Razorpay order created: {order['id']} | {req.module}/{req.plan_id}")
    return {"order_id": order["id"], "amount": order["amount"], "currency": order["currency"]}


@router.post("/verify")
def verify_payment(
    req: VerifyPaymentRequest,
    current_user: dict = Depends(get_current_user),
):
    """Verify the HMAC signature returned by Razorpay and start the session timer."""
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_secret:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    expected = hmac.new(
        key_secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    plan_cfg       = PLANS.get(req.plan_id, {})
    duration_hours = plan_cfg.get("duration_hours", 1)
    now_utc        = datetime.now(timezone.utc)
    session_end_dt = now_utc + timedelta(hours=duration_hours)
    session_end_ms = int(session_end_dt.timestamp() * 1000)

    # Map plan_id to the internal plan name stored on the user record
    plan_name = "pro" if duration_hours >= 3 else "basic"

    username  = current_user.get("username")
    users_col = get_user_collection()
    if users_col and username:
        users_col.update_one(
            {"username": username},
            {"$set": {
                "plan":             plan_name,
                "session_end":      session_end_dt,   # UTC datetime — enforced by security.py
                "last_payment_id":  req.razorpay_payment_id,
                "last_payment_at":  now_utc,
            }},
        )
        logger.info(
            f"Session started: user={username} plan={plan_name} "
            f"payment={req.razorpay_payment_id} expires={session_end_dt.isoformat()}"
        )

    return {
        "verified":       True,
        "module":         req.module,
        "plan_id":        req.plan_id,
        "plan_name":      plan_name,        # "pro" | "basic" — frontend updates user.plan in session
        "duration_hours": duration_hours,
        "payment_id":     req.razorpay_payment_id,
        "session_end_ms": session_end_ms,  # frontend writes into localStorage → SessionClock starts
    }
