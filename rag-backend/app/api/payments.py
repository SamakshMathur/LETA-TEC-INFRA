"""Razorpay payment integration.

Routes
------
POST /api/payments/create-order   — create a Razorpay order (rate-limited 10/min)
POST /api/payments/verify          — verify payment signature after checkout (15/min)
POST /api/payments/webhook         — server-to-server Razorpay webhook (source of truth)
GET  /api/payments/config          — return Razorpay key_id to frontend (safe)
GET  /api/payments/invoice/{id}    — download GST tax invoice PDF

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
from app.utils.time import utc_now
from typing import Optional
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
        # TEMPORARY: ₹10 for live testing instead of the real ₹199 — revert
        # to 19900 once testing is confirmed done. Not a permanent price.
        "amount": 1000,          # paise (₹10 × 100)
        "currency": "INR",
        "duration_hours": 1,
    },
    "3hr": {
        "name": "3-Hour Access",
        "description": "Full module access for 3 hours",
        "amount": 39900,        # paise (₹399 × 100)
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
    try:
        import razorpay
        return razorpay.Client(auth=(key_id, key_secret))
    except ImportError:
        import requests

        class _OrderResource:
            def __init__(self, k_id: str, k_sec: str):
                self.k_id = k_id
                self.k_sec = k_sec

            def create(self, data: dict) -> dict:
                resp = requests.post(
                    "https://api.razorpay.com/v1/orders",
                    auth=(self.k_id, self.k_sec),
                    json=data,
                    timeout=15.0,
                )
                if not resp.ok:
                    try:
                        err = resp.json().get("error", {})
                        desc = err.get("description", resp.text)
                    except Exception:
                        desc = resp.text
                    raise HTTPException(
                        status_code=500,
                        detail=f"Razorpay order creation failed: {desc}"
                    )
                return resp.json()

        class _DirectRazorpayClient:
            def __init__(self, k_id: str, k_sec: str):
                self.order = _OrderResource(k_id, k_sec)

        return _DirectRazorpayClient(key_id, key_secret)


def _send_payment_receipt(username: str, plan_cfg: dict, payment_id: str, session_end_dt) -> None:
    """
    Best-effort only — this runs AFTER the plan is already activated, so a
    problem here (missing RESEND_API_KEY, Resend being down, no email on
    file) must never look like the payment itself failed. Every exit path
    is a log line, nothing raises.
    """
    try:
        users_col = get_user_collection()
        if users_col is None:
            return
        user = users_col.find_one({"username": username}, {"_id": 0, "email": 1, "full_name": 1})
        email = (user or {}).get("email")
        if not email:
            logger.info(f"No email on file for {username} — skipping payment receipt")
            return

        from app.services.email import send_email
        name = (user or {}).get("full_name") or "there"
        amount_rupees = plan_cfg.get("amount", 0) / 100
        sent = send_email(
            to=email,
            subject="Your LETATEC payment receipt",
            html=f"""
            <div style="font-family:Arial;padding:30px">
                <h2>LETATEC</h2>
                <p>Hi {name},</p>
                <p>Thank you for your payment. Here are your receipt details:</p>
                <table style="border-collapse:collapse;margin-top:12px">
                    <tr><td style="padding:4px 16px 4px 0;color:#666">Payment ID</td><td>{payment_id}</td></tr>
                    <tr><td style="padding:4px 16px 4px 0;color:#666">Plan</td><td>{plan_cfg.get('name', '')}</td></tr>
                    <tr><td style="padding:4px 16px 4px 0;color:#666">Amount</td><td>₹{amount_rupees:.2f}</td></tr>
                    <tr><td style="padding:4px 16px 4px 0;color:#666">Valid until</td><td>{session_end_dt.strftime('%d %b %Y, %I:%M %p')} UTC</td></tr>
                    <tr><td style="padding:4px 16px 4px 0;color:#666">Status</td><td>PAID</td></tr>
                </table>
                <p style="margin-top:20px">Thank you for using LETATEC.</p>
            </div>
            """,
        )
        if sent:
            logger.info(f"Payment receipt emailed | user={username} payment={payment_id}")
    except Exception as e:
        logger.error(f"Payment receipt send failed (non-fatal, plan is already active): {e}")


def _send_payment_receipt_sms(username: str, plan_cfg: dict, payment_id: str, session_end_dt) -> None:
    """
    SMS counterpart to _send_payment_receipt. Same non-fatal contract: a problem here
    must never look like the payment failed.
    """
    try:
        users_col = get_user_collection()
        if users_col is None:
            return
        user = users_col.find_one({"username": username}, {"_id": 0, "phone": 1})
        phone = (user or {}).get("phone")
        if not phone:
            return

        from app.services.sms.airtel import AIRTEL_DLT_RECEIPT_TEMPLATE_ID
        from app.services.sms.sms_service import send_transactional_sms

        amount_rupees = plan_cfg.get("amount", 0) / 100
        message = (
            f"Your LETATEC payment of Rs.{amount_rupees:.0f} for {plan_cfg.get('name', '')} is confirmed. "
            f"Payment ID: {payment_id}. Valid until {session_end_dt.strftime('%d %b %Y, %I:%M %p')} UTC. "
            f"Thank you for choosing LETATEC."
        )
        result = send_transactional_sms(phone, AIRTEL_DLT_RECEIPT_TEMPLATE_ID, message)
        if result.success:
            logger.info(f"Payment receipt texted | user={username} payment={payment_id}")
    except Exception as e:
        logger.error(f"Payment receipt SMS failed (non-fatal, plan is already active): {e}")


def _create_invoice(
    username: str,
    plan_cfg: dict,
    payment_id: str,
    order_id: str,
    customer_state: Optional[str] = None,
    customer_state_code: Optional[str] = None,
    customer_gstin: Optional[str] = None,
    billing_address: Optional[str] = None,
    billing_city: Optional[str] = None,
    customer_type: Optional[str] = None,
    business_legal_name: Optional[str] = None,
) -> None:
    """
    Creates the permanent invoice record backing the "Download Invoice"
    button, assigning it its sequential GST invoice number and tax breakdown.
    Same non-fatal contract: plan activation takes priority over reporting.
    """
    try:
        users_col = get_user_collection()
        user = users_col.find_one({"username": username}, {"_id": 0, "email": 1, "phone": 1, "full_name": 1, "state": 1, "state_code": 1, "gstin": 1, "address": 1, "city": 1, "customer_type": 1, "business_legal_name": 1}) if users_col is not None else None

        orders_col = get_payment_orders_collection()
        order_doc = orders_col.find_one({"order_id": order_id}) if (orders_col is not None and order_id) else None

        # If state/gstin/address not directly provided, resolve from stored order or user record
        if order_doc:
            if not customer_state and not customer_state_code:
                customer_state = order_doc.get("customer_state")
                customer_state_code = order_doc.get("customer_state_code")
            customer_gstin = customer_gstin or order_doc.get("customer_gstin")
            billing_address = billing_address or order_doc.get("billing_address")
            billing_city = billing_city or order_doc.get("billing_city")
            customer_type = customer_type or order_doc.get("customer_type")
            business_legal_name = business_legal_name or order_doc.get("business_legal_name")

        if user:
            if not customer_state and not customer_state_code:
                customer_state = user.get("state")
                customer_state_code = user.get("state_code")
            customer_gstin = customer_gstin or user.get("gstin")
            billing_address = billing_address or user.get("address")
            billing_city = billing_city or user.get("city")
            customer_type = customer_type or user.get("customer_type")
            business_legal_name = business_legal_name or user.get("business_legal_name")

        resolved_cust_type = customer_type or ("B2B" if customer_gstin else "B2C")

        from app.services.invoice import create_invoice_record
        record = create_invoice_record(
            payment_id=payment_id,
            order_id=order_id,
            username=username,
            customer_name=(user or {}).get("full_name") or username,
            customer_email=(user or {}).get("email"),
            customer_phone=(user or {}).get("phone"),
            plan_name=plan_cfg.get("name", ""),
            amount_paise=plan_cfg.get("amount", 0),
            customer_state=customer_state,
            customer_state_code=customer_state_code,
            place_of_supply_state=customer_state,
            place_of_supply_state_code=customer_state_code,
            customer_gstin=customer_gstin,
            billing_address=billing_address,
            billing_city=billing_city,
            customer_type=resolved_cust_type,
            business_legal_name=business_legal_name,
        )
        if record:
            logger.info(f"Invoice created | number={record['invoice_number']} payment={payment_id}")
    except Exception as e:
        logger.error(f"Invoice creation failed (non-fatal, plan is already active): {e}")


def _credit_session(
    username: str,
    plan_id: str,
    payment_id: str,
    order_id: str,
    customer_state: Optional[str] = None,
    customer_state_code: Optional[str] = None,
    customer_gstin: Optional[str] = None,
    billing_address: Optional[str] = None,
    billing_city: Optional[str] = None,
    customer_type: Optional[str] = None,
    business_legal_name: Optional[str] = None,
) -> dict:
    """
    Apply session extension to the user record.
    Called from both /verify (client-side) and /webhook (server-side).
    Returns the session info dict.
    """
    plan_cfg       = PLANS.get(plan_id, {})
    duration_hours = plan_cfg.get("duration_hours", 1)
    now_utc        = utc_now()
    session_end_dt = now_utc + timedelta(hours=duration_hours)
    session_end_ms = int(session_end_dt.timestamp() * 1000)
    plan_name      = "pro" if duration_hours >= 3 else "basic"

    users_col = get_user_collection()
    if users_col is not None and username:
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
        # 1. Create invoice immediately
        _create_invoice(
            username, plan_cfg, payment_id, order_id,
            customer_state=customer_state,
            customer_state_code=customer_state_code,
            customer_gstin=customer_gstin,
            billing_address=billing_address,
            billing_city=billing_city,
            customer_type=customer_type,
            business_legal_name=business_legal_name,
        )
        # 2. Trigger notifications
        _send_payment_receipt(username, plan_cfg, payment_id, session_end_dt)
        _send_payment_receipt_sms(username, plan_cfg, payment_id, session_end_dt)

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
        logger.warning("payment_ledger unavailable — skipping idempotency check")
        return True
    try:
        ledger.insert_one({
            "payment_id": payment_id,
            "order_id":   order_id,
            "user_id":    username,
            "plan_id":    plan_id,
            "created_at": utc_now(),
        })
        return True
    except DuplicateKeyError:
        logger.warning(f"Duplicate payment_id rejected: {payment_id} user={username}")
        return False


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan_id: str     # "1hr" or "3hr"
    module: str      # "gst" | "fema" | "company-law" | "income-tax"
    customer_state: Optional[str] = None
    customer_state_code: Optional[str] = None
    customer_gstin: Optional[str] = None
    customer_type: Optional[str] = None
    business_legal_name: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str
    module: str = "gst"
    customer_state: Optional[str] = None
    customer_state_code: Optional[str] = None
    customer_gstin: Optional[str] = None
    customer_type: Optional[str] = None
    business_legal_name: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────

@router.get("/config")
def get_payment_config():
    """Return the Razorpay key_id to the frontend (safe to expose — key_secret stays server-side)."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    return {
        "key_id": key_id,
        "configured": bool(key_id and key_secret),
    }


@router.get("/plans")
def get_plans():
    """Return the available access plans and pricing."""
    return {"plans": PLANS}


@router.post("/create-order")
@limiter.limit("10/minute")
def create_order(request: Request, req: CreateOrderRequest, current_user: dict = Depends(get_jwt_user)):
    """
    Create a Razorpay order and record it in payment_orders so the webhook can
    resolve order_id → user without needing a JWT in the callback.
    """
    plan = PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {req.plan_id}")

    if plan["amount"] < 100:
        raise HTTPException(status_code=400, detail="Minimum order amount is 100 paise.")

    username = current_user.get("username", "")

    users_col = get_user_collection()
    if users_col is not None:
        existing_user = users_col.find_one({"username": username}, {"_id": 0, "session_end": 1})
        if existing_user:
            session_end = existing_user.get("session_end")
            if session_end is not None:
                if session_end.tzinfo is None:
                    session_end = session_end.replace(tzinfo=timezone.utc)
                if utc_now() < session_end:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "You already have an active plan until "
                            f"{session_end.isoformat()}. You can buy a new plan once it expires."
                        ),
                    )

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

    # Persist order → user mapping with customer place-of-supply details
    orders_col = get_payment_orders_collection()
    if orders_col is not None:
        try:
            orders_col.insert_one({
                "order_id":            order["id"],
                "user_id":             username,
                "plan_id":             req.plan_id,
                "module":              req.module,
                "customer_state":      req.customer_state,
                "customer_state_code": req.customer_state_code,
                "customer_gstin":      req.customer_gstin,
                "customer_type":       req.customer_type,
                "business_legal_name": req.business_legal_name,
                "billing_address":     req.billing_address,
                "billing_city":        req.billing_city,
                "created_at":          utc_now(),
            })
        except DuplicateKeyError:
            pass
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

    # ── 2. Idempotency check ──────────────────────────────────────────────────
    if not _claim_payment_id(
        req.razorpay_payment_id, username, req.plan_id, req.razorpay_order_id
    ):
        ledger = get_payment_ledger_collection()
        existing_claim = ledger.find_one({"payment_id": req.razorpay_payment_id}) if ledger is not None else None

        # Scenario B: Payment was already claimed by the SAME authenticated user (e.g. webhook won the race)
        if existing_claim and existing_claim.get("user_id") == username:
            users_col = get_user_collection()
            user_doc = users_col.find_one({"username": username}, {"_id": 0, "session_end": 1, "plan": 1}) if users_col is not None else None
            session_end = (user_doc or {}).get("session_end")

            if session_end:
                if session_end.tzinfo is None:
                    session_end = session_end.replace(tzinfo=timezone.utc)
                session_end_ms = int(session_end.timestamp() * 1000)
            elif existing_claim.get("created_at"):
                claim_created = existing_claim["created_at"]
                if claim_created.tzinfo is None:
                    claim_created = claim_created.replace(tzinfo=timezone.utc)
                plan_cfg = PLANS.get(existing_claim.get("plan_id", req.plan_id), {})
                duration_hours = plan_cfg.get("duration_hours", 1)
                session_end_dt = claim_created + timedelta(hours=duration_hours)
                session_end_ms = int(session_end_dt.timestamp() * 1000)
                if users_col is not None:
                    users_col.update_one(
                        {"username": username},
                        {"$set": {"plan": "pro" if duration_hours >= 3 else "basic", "session_end": session_end_dt}},
                    )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Authoritative session state could not be resolved for this payment.",
                )

            plan_name = (user_doc or {}).get("plan") or ("pro" if PLANS.get(req.plan_id, {}).get("duration_hours", 1) >= 3 else "basic")

            _create_invoice(
                username, PLANS.get(req.plan_id, {}), req.razorpay_payment_id, req.razorpay_order_id,
                customer_state=req.customer_state,
                customer_state_code=req.customer_state_code,
                customer_gstin=req.customer_gstin,
                billing_address=req.billing_address,
                billing_city=req.billing_city,
                customer_type=req.customer_type,
                business_legal_name=req.business_legal_name,
            )

            logger.info(f"verify_payment: payment {req.razorpay_payment_id} already claimed by same user {username} — returning 200 with session state")
            return {
                "verified": True,
                "plan_name": plan_name,
                "duration_hours": PLANS.get(req.plan_id, {}).get("duration_hours", 1),
                "payment_id": req.razorpay_payment_id,
                "session_end_ms": session_end_ms,
                "module": req.module,
                "plan_id": req.plan_id,
                "already_credited": True,
            }

        # Scenario C: Payment belongs to a different account
        raise HTTPException(
            status_code=409,
            detail="This payment has already been claimed by another account.",
        )

    # ── 3. Scenario A: First time claiming payment ────────────────────────────
    info = _credit_session(
        username, req.plan_id, req.razorpay_payment_id, req.razorpay_order_id,
        customer_state=req.customer_state,
        customer_state_code=req.customer_state_code,
        customer_gstin=req.customer_gstin,
        billing_address=req.billing_address,
        billing_city=req.billing_city,
        customer_type=req.customer_type,
        business_legal_name=req.business_legal_name,
    )
    return {**info, "module": req.module, "plan_id": req.plan_id}


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """
    Server-to-server webhook endpoint — Razorpay calls this directly on payment events.
    """
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.warning("razorpay_webhook: RAZORPAY_WEBHOOK_SECRET not set — skipping verification")
        return {"status": "not_configured"}

    body         = await request.body()
    received_sig = request.headers.get("X-Razorpay-Signature", "")

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

    if event_type == "payment.captured":
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id", "")
        order_id   = payment.get("order_id", "")

        orders_col = get_payment_orders_collection()
        order_doc  = orders_col.find_one({"order_id": order_id}) if orders_col is not None else None

        if not order_doc:
            logger.warning(f"razorpay_webhook: no order record for order_id={order_id} payment_id={payment_id}")
            return {"status": "order_not_found"}

        username = order_doc.get("user_id", "")
        plan_id  = order_doc.get("plan_id", "1hr")
        customer_state = order_doc.get("customer_state")
        customer_state_code = order_doc.get("customer_state_code")
        customer_gstin = order_doc.get("customer_gstin")
        customer_type = order_doc.get("customer_type")
        business_legal_name = order_doc.get("business_legal_name")
        billing_address = order_doc.get("billing_address")
        billing_city = order_doc.get("billing_city")

        if not _claim_payment_id(payment_id, username, plan_id, order_id):
            logger.info(f"razorpay_webhook: duplicate event for payment_id={payment_id} — ACK and skip")
            return {"status": "already_processed"}

        _credit_session(
            username, plan_id, payment_id, order_id,
            customer_state=customer_state,
            customer_state_code=customer_state_code,
            customer_gstin=customer_gstin,
            billing_address=billing_address,
            billing_city=billing_city,
            customer_type=customer_type,
            business_legal_name=business_legal_name,
        )
        logger.info(f"razorpay_webhook: session credited via webhook | payment={payment_id} user={username}")

    else:
        logger.debug(f"razorpay_webhook: unhandled event type '{event_type}' — ACK")

    return {"status": "ok"}


@router.get("/invoices")
def list_invoices(current_user: dict = Depends(get_jwt_user)):
    """
    Lists the current user's own invoices, newest first — backs the
    invoice history page. Returns only the summary fields a history list
    needs; the full record (customer contact details etc.) stays behind
    the per-invoice download endpoint below.
    """
    from app.services.invoice import list_invoice_records

    records = list_invoice_records(current_user.get("username", ""))
    return [
        {
            "invoice_number": r["invoice_number"],
            "payment_id": r["payment_id"],
            "plan_name": r["plan_name"],
            "amount_paise": r["amount_paise"],
            "issued_at": r["issued_at"],
        }
        for r in records
    ]


@router.get("/invoice/{payment_id}")
def download_invoice(payment_id: str, current_user: dict = Depends(get_jwt_user)):
    """
    Serves the GST invoice PDF for a specific payment. Ownership-scoped.
    """
    from app.services.invoice import get_invoice_record, render_invoice_pdf
    from fastapi.responses import Response

    record = get_invoice_record(payment_id)
    if record is None:
        ledger = get_payment_ledger_collection()
        claim = ledger.find_one({"payment_id": payment_id}) if ledger is not None else None
        if claim and claim.get("user_id") == current_user.get("username"):
            plan_cfg = PLANS.get(claim.get("plan_id", "1hr"), {})
            _create_invoice(current_user.get("username"), plan_cfg, payment_id, claim.get("order_id", ""))
            record = get_invoice_record(payment_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if record.get("username") != current_user.get("username"):
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_bytes = render_invoice_pdf(record)
    filename = f"{record['invoice_number'].replace('/', '-')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
