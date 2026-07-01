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
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
def verify_payment(req: VerifyPaymentRequest):
    """Verify the HMAC signature returned by Razorpay after payment."""
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_secret:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    expected = hmac.new(
        key_secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    plan = PLANS.get(req.plan_id, {})
    logger.info(f"Payment verified: {req.razorpay_payment_id} | {req.module}/{req.plan_id}")
    return {
        "verified": True,
        "module": req.module,
        "plan_id": req.plan_id,
        "duration_hours": plan.get("duration_hours", 1),
        "payment_id": req.razorpay_payment_id,
    }
