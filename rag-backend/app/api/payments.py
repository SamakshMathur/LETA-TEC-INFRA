"""Razorpay payment integration.

Routes
------
POST /api/payments/create-order   — create a Razorpay order (rate-limited 10/min)
POST /api/payments/verify          — verify payment signature after checkout (15/min)
POST /api/payments/webhook         — server-to-server Razorpay webhook (source of truth)
GET  /api/payments/config          — return Razorpay key_id to frontend (safe)

Security
--------
• /verify:    HMAC-SHA256 signature check on razorpay_order_id|razorpay_payment_id.
• /webhook:   HMAC-SHA256 signature check on raw request body using RAZORPAY_WEBHOOK_SECRET.
• Idempotency: payment_id is written to the payment_ledger collection with a unique index.
  Any duplicate /verify call or repeated webhook fires are rejected with 409 before
  any DB mutation happens.
"""
import os
import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.security import get_jwt_user
from app.database import get_user_collection, get_payment_ledger_collection, get_payment_orders_collection
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

# ── Plans ──────────────────────────────────────────────────────────────────────
PLANS = {
    "1hr": {
        "name": "1-Hour Access",
        "description": "Full module access for 1 hour",
        "amount": 1000,         # paise (₹10 × 100) — TEST AMOUNT
        "currency": "INR",
        "duration_hours": 1,
    },
    "3hr": {
        "name": "3-Hour Access",
        "description": "Full module access for 3 hours",
        "amount": 1000,         # paise (₹10 × 100) — TEST AMOUNT
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


def _credit_session(username: str, plan_id: str, payment_id: str, order_id: str) -> dict:
    """
    Apply session extension to the user record.
    Called from both /verify (client-side) and /webhook (server-side).
    Returns the session info dict.
    """
    plan_cfg       = PLANS.get(plan_id, {})
    duration_hours = plan_cfg.get("duration_hours", 1)
    now_utc        = datetime.now(timezone.utc)
    session_end_dt = now_utc + timedelta(hours=duration_hours)
    session_end_ms = int(session_end_dt.timestamp() * 1000)
    plan_name      = "pro" if duration_hours >= 3 else "basic"

    users_col = get_user_collection()
    if users_col and username:
        users_col.update_one(
            {"username": username},
            {"$set": {
                "plan":            plan_name,
                "session_end":     session_end_dt,
                "last_payment_id": payment_id,
                "last_payment_at": now_utc,
            }},
        )
        logger.info(
            f"Session credited: user={username} plan={plan_name} "
            f"payment={payment_id} order={order_id} expires={session_end_dt.isoformat()}"
        )

    return {
        "verified":       True,
        "plan_name":      plan_name,
        "duration_hours": duration_hours,
        "payment_id":     payment_id,
        "session_end_ms": session_end_ms,
    }


def _claim_payment_id(payment_id: str, username: str, plan_id: str, order_id: str) -> bool:
    """
    Attempt to insert payment_id into the idempotency ledger.
    Returns True on success (first time we've seen this payment).
    Returns False if already recorded (duplicate — caller should return 409).
    """
    ledger = get_payment_ledger_collection()
    if ledger is None:
        # DB unavailable — allow through with a warning rather than blocking payment
        logger.warning("payment_ledger unavailable — skipping idempotency check")
        return True
    try:
        ledger.insert_one({
            "payment_id": payment_id,
            "order_id":   order_id,
            "user_id":    username,
            "plan_id":    plan_id,
            "created_at": datetime.now(timezone.utc),
        })
        return True
    except DuplicateKeyError:
        logger.warning(f"Duplicate payment_id rejected: {payment_id} user={username}")
        return False


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
@limiter.limit("10/minute")
def create_order(request: Request, req: CreateOrderRequest, current_user: dict = Depends(get_jwt_user)):
    """
    Create a Razorpay order and record it in payment_orders so the webhook can
    resolve order_id → user without needing a JWT in the callback.

    Rate-limited at 10/minute per user to prevent mass order creation from
    exhausting the Razorpay API quota or the frontend retry loop.
    """
    plan = PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {req.plan_id}")

    username = current_user.get("username", "")
    client   = _razorpay_client()
    order    = client.order.create({
        "amount":   plan["amount"],
        "currency": plan["currency"],
        "receipt":  f"{req.module}_{req.plan_id}",
        "notes": {
            "module":          req.module,
            "plan_id":         req.plan_id,
            "duration_hours":  str(plan["duration_hours"]),
        },
    })

    # Persist order → user mapping for server-side webhook resolution.
    orders_col = get_payment_orders_collection()
    if orders_col is not None:
        try:
            orders_col.insert_one({
                "order_id":   order["id"],
                "user_id":    username,
                "plan_id":    req.plan_id,
                "module":     req.module,
                "created_at": datetime.now(timezone.utc),
            })
        except DuplicateKeyError:
            pass  # same order somehow submitted twice — already recorded
        except Exception as exc:
            logger.warning(f"create_order: could not save to payment_orders: {exc}")

    logger.info(f"Razorpay order created: {order['id']} | user={username} | {req.module}/{req.plan_id}")
    return {"order_id": order["id"], "amount": order["amount"], "currency": order["currency"]}


@router.post("/verify")
@limiter.limit("15/minute")
def verify_payment(
    request: Request,
    req: VerifyPaymentRequest,
    current_user: dict = Depends(get_jwt_user),
):
    """
    Verify the HMAC signature returned by Razorpay and start the session timer.

    Idempotency: payment_id is written to the payment_ledger with a unique index.
    A duplicate /verify call (e.g. frontend retry) returns 409 so the session
    is not extended a second time.
    """
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_secret:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    # ── 1. Verify HMAC signature ──────────────────────────────────────────────
    body     = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    expected = hmac.new(key_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    username = current_user.get("username", "")

    # ── 2. Idempotency check — reject duplicate payment_ids ───────────────────
    if not _claim_payment_id(
        req.razorpay_payment_id, username, req.plan_id, req.razorpay_order_id
    ):
        raise HTTPException(
            status_code=409,
            detail="This payment has already been applied. If you believe this is an error, contact support.",
        )

    # ── 3. Credit the session ─────────────────────────────────────────────────
    info = _credit_session(username, req.plan_id, req.razorpay_payment_id, req.razorpay_order_id)
    return {**info, "module": req.module, "plan_id": req.plan_id}


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """
    Server-to-server webhook endpoint — Razorpay calls this directly on payment
    events, bypassing the frontend entirely.  This is the authoritative source
    of truth for payment.captured events.

    Configure in the Razorpay dashboard:
      URL: https://api.letatec.com/api/payments/webhook
      Events: payment.captured
      Secret: value of RAZORPAY_WEBHOOK_SECRET env var

    Idempotency: Razorpay may fire the same event more than once.  The
    payment_id unique index in payment_ledger prevents double-crediting.
    Always return 200 to ACK (Razorpay retries on non-200 for 24h).
    """
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        # Webhook not yet configured — ACK silently so Razorpay doesn't retry
        logger.warning("razorpay_webhook: RAZORPAY_WEBHOOK_SECRET not set — skipping verification")
        return {"status": "not_configured"}

    body         = await request.body()
    received_sig = request.headers.get("X-Razorpay-Signature", "")

    # ── 1. Verify HMAC-SHA256 over raw body ───────────────────────────────────
    expected_sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, received_sig):
        logger.warning("razorpay_webhook: invalid signature — possible spoofed request")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    import json
    try:
        event = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload.")

    event_type = event.get("event", "")

    # ── 2. Handle payment.captured ────────────────────────────────────────────
    if event_type == "payment.captured":
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id", "")
        order_id   = payment.get("order_id", "")
        notes      = payment.get("notes", {})

        # Resolve order → user via payment_orders (written by create_order)
        orders_col = get_payment_orders_collection()
        order_doc  = orders_col.find_one({"order_id": order_id}) if orders_col else None

        if not order_doc:
            logger.warning(f"razorpay_webhook: no order record for order_id={order_id} payment_id={payment_id}")
            # ACK anyway — we can reconcile manually from the Razorpay dashboard
            return {"status": "order_not_found"}

        username = order_doc.get("user_id", "")
        plan_id  = order_doc.get("plan_id", "1hr")

        # ── 3. Idempotency — bail out silently if already processed ──────────
        if not _claim_payment_id(payment_id, username, plan_id, order_id):
            logger.info(f"razorpay_webhook: duplicate event for payment_id={payment_id} — ACK and skip")
            return {"status": "already_processed"}

        # ── 4. Credit the session ─────────────────────────────────────────────
        _credit_session(username, plan_id, payment_id, order_id)
        logger.info(f"razorpay_webhook: session credited via webhook | payment={payment_id} user={username}")

    else:
        logger.debug(f"razorpay_webhook: unhandled event type '{event_type}' — ACK")

    return {"status": "ok"}
