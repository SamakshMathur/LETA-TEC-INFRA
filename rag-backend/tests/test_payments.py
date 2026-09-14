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
