"""
Regression coverage for a live production incident: every real payment
since the payments router went live crashed with

    NotImplementedError: Collection objects do not implement truth value
    testing or bool(). Please compare with None instead: collection is
    not None

Razorpay charged the customer successfully; both server-side paths that
were supposed to credit the account for it then crashed before doing so:

  - /verify (the primary, client-driven path) crashed in _credit_session:
    `if users_col and username:` — pymongo Collection objects override
    __bool__ to raise, specifically to stop exactly this mistake, but the
    raise happens at runtime, not at write time, so it shipped anyway.
  - /webhook (the server-to-server safety net, meant to catch exactly
    this kind of client-side failure) crashed on the SAME class of bug
    in its own order-lookup: `orders_col.find_one(...) if orders_col
    else None`.

Both are now `is not None` checks. The fakes below deliberately raise
NotImplementedError on __bool__/__len__, matching real pymongo exactly —
a fake that's simply truthy by default (the pattern used elsewhere in
this test suite, e.g. test_session_sharing.py's _FakeSessionCollection)
would NOT catch a regression of this exact bug, since a plain object's
default truthiness silently masks it.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ANTHROPIC_API_KEY",       "ci-placeholder")
os.environ.setdefault("MONGODB_URI",             "mongodb://localhost:27017/ci_test")
os.environ.setdefault("SECRET_KEY",              "ci-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",               "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET",     "ci-placeholder")
os.environ.setdefault("RAZORPAY_KEY_ID",         "ci-placeholder")
os.environ.setdefault("RAZORPAY_KEY_SECRET",     "ci-placeholder")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "ci-placeholder")
os.environ.setdefault("DEV_MODE",                "true")


class _RealisticFakeCollection:
    """Mimics real pymongo.Collection's __bool__/__len__, which both
    unconditionally raise NotImplementedError — the exact behavior that
    made `if some_collection:` a silent landmine in production instead of
    an immediate, obvious error at write time."""

    def __init__(self, docs=None, update_calls=None):
        self._docs = {d["order_id"]: d for d in (docs or [])} if docs and "order_id" in docs[0] else {}
        self._raw_docs = docs or []
        self.update_calls = update_calls if update_calls is not None else []

    def __bool__(self):
        raise NotImplementedError(
            "Collection objects do not implement truth value testing or bool(). "
            "Please compare with None instead: collection is not None"
        )

    __len__ = __bool__

    def find_one(self, query, *args, **kwargs):
        oid = query.get("order_id")
        return self._docs.get(oid)

    def update_one(self, query, update, *args, **kwargs):
        self.update_calls.append((query, update))
        return type("Result", (), {"matched_count": 1, "modified_count": 1})()


class _RealisticFakeUserCollection:
    """Same __bool__-raises-NotImplementedError contract as
    _RealisticFakeCollection above, but keyed by username (with email/
    full_name fields) for the payment-receipt tests, which look a user up
    by username rather than an order_id."""

    def __init__(self, docs=None):
        self._docs = {d["username"]: dict(d) for d in (docs or [])}
        self.update_calls = []

    def __bool__(self):
        raise NotImplementedError(
            "Collection objects do not implement truth value testing or bool(). "
            "Please compare with None instead: collection is not None"
        )

    __len__ = __bool__

    def find_one(self, query, projection=None):
        doc = self._docs.get(query.get("username"))
        if doc is None:
            return None
        result = dict(doc)
        if projection:
            include = {k for k, v in projection.items() if v}
            for k in list(result.keys()):
                if include and k not in include:
                    result.pop(k, None)
        return result

    def update_one(self, query, update):
        doc = self._docs.setdefault(query.get("username"), {"username": query.get("username")})
        self.update_calls.append((query, update))
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        return type("Result", (), {"matched_count": 1, "modified_count": 1})()


def test_credit_session_does_not_crash_on_a_real_collection(monkeypatch):
    """The exact vulnerability in _credit_session: `if users_col and
    username:` used to raise NotImplementedError for ANY real (non-None)
    collection, meaning /verify crashed for every successful payment."""
    from app.api import payments

    fake_users = _RealisticFakeCollection()
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)

    result = payments._credit_session("alice", "1hr", "pay_123", "order_456")

    assert result["verified"] is True
    assert result["plan_name"] == "basic"
    assert len(fake_users.update_calls) == 1
    query, update = fake_users.update_calls[0]
    assert query == {"username": "alice"}
    assert update["$set"]["plan"] == "basic"
    assert update["$set"]["last_payment_id"] == "pay_123"


def test_credit_session_handles_no_db_gracefully():
    """get_user_collection() returning None (DB unavailable) still works —
    this path was already correct; pinning it alongside the fix."""
    from app.api import payments
    import app.api.app as app_module  # ensure app module import doesn't error
    result = payments._credit_session("alice", "1hr", "pay_123", "order_456")
    assert result["verified"] is True


@pytest.mark.asyncio
async def test_webhook_order_lookup_does_not_crash_on_a_real_collection(monkeypatch):
    """The exact vulnerability in razorpay_webhook: `orders_col.find_one(...)
    if orders_col else None` used to raise NotImplementedError for ANY real
    (non-None) orders collection — meaning the server-to-server safety net
    crashed on every event too, so a /verify failure had nothing to fall
    back on."""
    from app.api import payments
    import hmac, hashlib, json

    fake_orders = _RealisticFakeCollection(docs=[
        {"order_id": "order_456", "user_id": "alice", "plan_id": "1hr"},
    ])
    fake_users = _RealisticFakeCollection()
    fake_ledger_calls = []

    monkeypatch.setattr(payments, "get_payment_orders_collection", lambda: fake_orders)
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)

    class _FakeLedger:
        def insert_one(self, doc):
            fake_ledger_calls.append(doc)
    monkeypatch.setattr(payments, "get_payment_ledger_collection", lambda: _FakeLedger())

    webhook_secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_123", "order_id": "order_456", "notes": {},
        }}},
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    class _FakeRequest:
        headers = {"X-Razorpay-Signature": sig}
        async def body(self):
            return body

    result = await payments.razorpay_webhook(_FakeRequest())

    assert result == {"status": "ok"}
    assert len(fake_users.update_calls) == 1  # _credit_session actually ran


# ── Payment receipt email ───────────────────────────────────────────────────

def test_send_payment_receipt_emails_when_user_has_an_email_on_file(monkeypatch):
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "email": "alice@example.com", "full_name": "Alice Singh"},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)

    sent_calls = []
    monkeypatch.setattr(
        "app.services.email.send_email",
        lambda to, subject, html: sent_calls.append((to, subject, html)) or True,
    )

    from datetime import datetime, timezone
    session_end = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    payments._send_payment_receipt("alice", payments.PLANS["1hr"], "pay_123", session_end)

    assert len(sent_calls) == 1
    to, subject, html = sent_calls[0]
    assert to == "alice@example.com"
    assert "receipt" in subject.lower()
    assert "pay_123" in html
    # Derived from PLANS["1hr"]["amount"] rather than hardcoded — that
    # figure is a live business price (currently discounted for testing),
    # not a fixed constant this test should need editing to track.
    expected_rupees = payments.PLANS["1hr"]["amount"] / 100
    assert f"{expected_rupees:.2f}" in html


def test_send_payment_receipt_skips_silently_when_no_email_on_file(monkeypatch):
    """Phone-only signups have nowhere to send this yet — must not raise,
    must not block anything (the plan is already active by this point)."""
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "bob"},  # no email field at all
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)

    sent_calls = []
    monkeypatch.setattr(
        "app.services.email.send_email",
        lambda *a, **k: sent_calls.append((a, k)) or True,
    )

    from datetime import datetime, timezone
    session_end = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    payments._send_payment_receipt("bob", payments.PLANS["1hr"], "pay_123", session_end)  # must not raise

    assert sent_calls == []


def test_send_payment_receipt_never_raises_if_email_sending_itself_fails(monkeypatch):
    """A Resend outage must never surface as a payment-verify error — the
    plan is already credited by the time this runs."""
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "email": "alice@example.com", "full_name": "Alice"},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr(
        "app.services.email.send_email",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("resend is down")),
    )

    from datetime import datetime, timezone
    session_end = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    # Must not raise despite send_email raising internally.
    payments._send_payment_receipt("alice", payments.PLANS["1hr"], "pay_123", session_end)


def test_credit_session_still_credits_even_if_receipt_email_blows_up(monkeypatch):
    """The actual end-to-end guarantee: whatever goes wrong with the
    receipt, the session is still credited — _credit_session's own
    return value and DB write must be unaffected."""
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "email": "alice@example.com", "full_name": "Alice"},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr(
        "app.services.email.send_email",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("resend is down")),
    )

    result = payments._credit_session("alice", "1hr", "pay_123", "order_456")

    assert result["verified"] is True
    assert fake_users._docs["alice"]["plan"] == "basic"


# ── Payment receipt SMS ──────────────────────────────────────────────────────

class _RealisticFakeUserCollectionWithPhone(_RealisticFakeUserCollection):
    """Same contract as _RealisticFakeUserCollection, just documented
    separately here since these tests specifically exercise the
    phone-lookup path (find_one keyed by username, returning phone)."""
    pass


def test_send_payment_receipt_sms_sends_when_phone_and_template_exist(monkeypatch):
    from app.api import payments

    fake_users = _RealisticFakeUserCollectionWithPhone([
        {"username": "alice", "phone": "9876543210"},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr("app.services.sms.airtel.AIRTEL_DLT_RECEIPT_TEMPLATE_ID", "template_abc")

    sent_calls = []
    from app.services.sms.base import SMSResult
    monkeypatch.setattr(
        "app.services.sms.sms_service.send_transactional_sms",
        lambda phone, template_id, message: sent_calls.append((phone, template_id, message))
        or SMSResult(success=True, provider="airtel"),
    )

    from datetime import datetime, timezone
    session_end = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    payments._send_payment_receipt_sms("alice", payments.PLANS["1hr"], "pay_123", session_end)

    assert len(sent_calls) == 1
    phone, template_id, message = sent_calls[0]
    assert phone == "9876543210"
    assert template_id == "template_abc"
    assert "pay_123" in message
    # Same reasoning as the email receipt test above — derive from the
    # live PLANS value instead of hardcoding a price that's expected to
    # change back after testing.
    assert f"{payments.PLANS['1hr']['amount'] // 100}" in message


def test_send_payment_receipt_sms_skips_silently_with_no_phone_on_file(monkeypatch):
    from app.api import payments

    fake_users = _RealisticFakeUserCollectionWithPhone([{"username": "bob"}])  # no phone field
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)

    sent_calls = []
    monkeypatch.setattr(
        "app.services.sms.sms_service.send_transactional_sms",
        lambda *a, **k: sent_calls.append((a, k)),
    )

    from datetime import datetime, timezone
    session_end = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    payments._send_payment_receipt_sms("bob", payments.PLANS["1hr"], "pay_123", session_end)  # must not raise

    assert sent_calls == []


def test_send_payment_receipt_sms_never_raises_if_sms_send_itself_fails(monkeypatch):
    from app.api import payments

    fake_users = _RealisticFakeUserCollectionWithPhone([
        {"username": "alice", "phone": "9876543210"},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr(
        "app.services.sms.sms_service.send_transactional_sms",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("airtel gateway down")),
    )

    from datetime import datetime, timezone
    session_end = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    # Must not raise despite send_transactional_sms raising internally.
    payments._send_payment_receipt_sms("alice", payments.PLANS["1hr"], "pay_123", session_end)


def test_credit_session_still_credits_even_if_receipt_sms_blows_up(monkeypatch):
    """Same end-to-end guarantee as the email version: whatever goes
    wrong with either receipt channel, the session is still credited.
    Gives the fake user a phone number specifically so the SMS
    send-attempt genuinely happens and raises — without one, the SMS
    path would just skip silently and this would pass without actually
    proving anything."""
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "phone": "9876543210"},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr(
        "app.services.sms.sms_service.send_transactional_sms",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("airtel gateway down")),
    )
    monkeypatch.setattr("app.services.email.send_email", lambda *a, **k: False)

    result = payments._credit_session("alice", "1hr", "pay_123", "order_456")

    assert result["verified"] is True
    assert fake_users._docs["alice"]["plan"] == "basic"  # crediting genuinely happened


# ── create_order — blocks buying a new plan while one is already active ────
#
# _credit_session always overwrites session_end with now()+duration rather
# than extending it, so letting a purchase through mid-plan would let a
# customer pay again and end up with LESS time than they had (and get
# silently downgraded from "pro" back to "basic" on a 1hr top-up). These
# tests exercise create_order for real — not a helper function — since
# that's where the guard actually lives and it's reachable directly by
# anyone with a valid JWT, active plan or not.
#
# slowapi's @limiter.limit decorator requires a genuine
# starlette.requests.Request (rejects a Mock outright, confirmed while
# writing this), so these build one against the real app instance rather
# than stub it out.

def _fake_request():
    from starlette.requests import Request
    from app.api.app import app as real_app
    scope = {
        "type": "http", "method": "POST", "path": "/api/payments/create-order",
        "headers": [], "client": ("127.0.0.1", 12345), "app": real_app,
        "query_string": b"",
    }
    return Request(scope)


def test_create_order_blocks_purchase_while_a_plan_is_still_active(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "session_end": datetime.now(timezone.utc) + timedelta(hours=2)},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)

    with pytest.raises(HTTPException) as exc_info:
        payments.create_order(
            _fake_request(),
            payments.CreateOrderRequest(plan_id="1hr", module="gst"),
            current_user={"username": "alice"},
        )
    assert exc_info.value.status_code == 409
    assert "already have an active plan" in exc_info.value.detail


class _FakeRazorpayClient:
    """Stands in for a real razorpay.Client — no network call, no real
    credentials needed. Records what it was asked to create so a test can
    assert on it if it ever needs to."""

    def __init__(self):
        self.order = self
        self.created_with = None

    def create(self, payload):
        self.created_with = payload
        return {"id": "order_test123", "amount": payload["amount"], "currency": payload["currency"]}


def test_create_order_allows_purchase_once_the_active_plan_has_expired(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "session_end": datetime.now(timezone.utc) - timedelta(minutes=1)},
    ])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr(payments, "_razorpay_client", lambda: _FakeRazorpayClient())
    monkeypatch.setattr(payments, "get_payment_orders_collection", lambda: None)

    result = payments.create_order(
        _fake_request(),
        payments.CreateOrderRequest(plan_id="1hr", module="gst"),
        current_user={"username": "alice"},
    )
    assert result["order_id"] == "order_test123"


def test_create_order_allows_purchase_with_no_prior_plan_at_all(monkeypatch):
    """A brand-new user with no session_end field on their record yet —
    must not be treated as blocked."""
    from app.api import payments

    fake_users = _RealisticFakeUserCollection([{"username": "bob"}])
    monkeypatch.setattr(payments, "get_user_collection", lambda: fake_users)
    monkeypatch.setattr(payments, "_razorpay_client", lambda: _FakeRazorpayClient())
    monkeypatch.setattr(payments, "get_payment_orders_collection", lambda: None)

    result = payments.create_order(
        _fake_request(),
        payments.CreateOrderRequest(plan_id="1hr", module="gst"),
        current_user={"username": "bob"},
    )
    assert result["order_id"] == "order_test123"
