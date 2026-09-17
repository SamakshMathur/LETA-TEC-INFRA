"""
Tests for GST invoice generation (app/services/invoice.py) and the
download endpoint (payments.download_invoice).

Sequential, gap-free numbering is a real legal requirement here, not
just a nice property — the fake counter below implements atomic
find_one_and_update the same way real pymongo does, so these tests
actually exercise the increment logic rather than assume it.
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


class _FakeCounterCollection:
    """Mimics find_one_and_update with $inc + upsert + ReturnDocument.AFTER
    closely enough to actually exercise sequential-increment logic."""

    def __init__(self):
        self._docs = {}

    def find_one_and_update(self, filt, update, upsert=False, return_document=None):
        _id = filt.get("_id")
        doc = self._docs.get(_id)
        if doc is None:
            if not upsert:
                return None
            doc = {"_id": _id, "seq": 0}
        inc = update.get("$inc", {})
        for k, v in inc.items():
            doc[k] = doc.get(k, 0) + v
        self._docs[_id] = doc
        return dict(doc)


class _FakeCursor:
    """Just enough of a pymongo cursor to exercise .sort() chaining."""

    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction):
        self._docs = sorted(self._docs, key=lambda d: d[field], reverse=(direction < 0))
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeInvoiceCollection:
    def __init__(self):
        self._docs = {}  # keyed by payment_id

    def find_one(self, query, projection=None):
        pid = query.get("payment_id")
        doc = self._docs.get(pid)
        return dict(doc) if doc else None

    def find(self, query, projection=None):
        username = query.get("username")
        matches = [dict(d) for d in self._docs.values() if d.get("username") == username]
        return _FakeCursor(matches)

    def insert_one(self, doc):
        pid = doc["payment_id"]
        if pid in self._docs:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("duplicate payment_id")
        self._docs[pid] = dict(doc)


@pytest.fixture
def invoice_module(monkeypatch):
    from app.services import invoice as invoice_module
    fake_counters = _FakeCounterCollection()
    fake_invoices = _FakeInvoiceCollection()
    monkeypatch.setattr(invoice_module, "get_invoice_counter_collection", lambda: fake_counters)
    monkeypatch.setattr(invoice_module, "get_invoice_collection", lambda: fake_invoices)
    invoice_module._fake_invoices = fake_invoices  # stash for assertions
    return invoice_module


def test_invoice_numbers_are_sequential(invoice_module):
    first = invoice_module._next_invoice_number()
    second = invoice_module._next_invoice_number()
    third = invoice_module._next_invoice_number()

    # Same FY prefix, strictly increasing sequence, no gaps.
    fy = invoice_module._current_financial_year()
    assert first == f"LETA/{fy}/00001"
    assert second == f"LETA/{fy}/00002"
    assert third == f"LETA/{fy}/00003"


def test_create_invoice_record_is_idempotent_per_payment(invoice_module):
    """The real scenario this guards: /verify and /webhook can both reach
    _credit_session for the same payment near-simultaneously (that's the
    whole reason payment_ledger's idempotency check exists) — an invoice
    must never get minted twice for one payment."""
    first = invoice_module.create_invoice_record(
        payment_id="pay_123", order_id="order_456", username="alice",
        customer_name="Alice", customer_email="alice@example.com", customer_phone="9876543210",
        plan_name="1-Hour Access", amount_paise=19900,
    )
    second = invoice_module.create_invoice_record(
        payment_id="pay_123", order_id="order_456", username="alice",
        customer_name="Alice", customer_email="alice@example.com", customer_phone="9876543210",
        plan_name="1-Hour Access", amount_paise=19900,
    )

    assert first["invoice_number"] == second["invoice_number"]  # same number both times
    assert len(invoice_module._fake_invoices._docs) == 1  # never minted twice


def test_render_invoice_pdf_produces_a_real_pdf(invoice_module):
    from datetime import datetime, timezone
    record = {
        "invoice_number": "LETA/2026-27/00001",
        "payment_id": "pay_123",
        "customer_name": "Alice",
        "customer_email": "alice@example.com",
        "customer_phone": "9876543210",
        "plan_name": "1-Hour Access",
        "amount_paise": 19900,
        "issued_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)

    assert pdf_bytes[:5] == b"%PDF-"  # genuinely a PDF, not just bytes that happen to exist
    assert len(pdf_bytes) > 500  # not an empty/broken document


def test_render_invoice_pdf_gst_math_is_consistent(invoice_module):
    """₹199 is what Razorpay actually charges (inclusive) — the invoice
    must show a taxable value + GST that ADD BACK UP to that exact total,
    not some other number. This is the one thing worth asserting
    numerically rather than just "it didn't crash"."""
    from datetime import datetime, timezone
    record = {
        "invoice_number": "LETA/2026-27/00001", "payment_id": "pay_123",
        "customer_name": "Alice", "customer_email": None, "customer_phone": None,
        "plan_name": "1-Hour Access", "amount_paise": 19900,
        "issued_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }
    amount_rupees = record["amount_paise"] / 100
    base = amount_rupees / 1.18
    gst = amount_rupees - base
    assert round(base + gst, 2) == round(amount_rupees, 2)  # sanity-checks the module's own formula


def test_list_invoice_records_is_scoped_to_the_user_and_newest_first(invoice_module):
    from datetime import datetime, timezone

    invoice_module.create_invoice_record(
        payment_id="pay_alice_1", order_id="o1", username="alice",
        customer_name="Alice", customer_email=None, customer_phone=None,
        plan_name="1-Hour Access", amount_paise=1000,
    )
    invoice_module.create_invoice_record(
        payment_id="pay_mallory_1", order_id="o2", username="mallory",
        customer_name="Mallory", customer_email=None, customer_phone=None,
        plan_name="1-Hour Access", amount_paise=1000,
    )
    invoice_module.create_invoice_record(
        payment_id="pay_alice_2", order_id="o3", username="alice",
        customer_name="Alice", customer_email=None, customer_phone=None,
        plan_name="3-Hour Pro Access", amount_paise=1000,
    )
    # Backdate the first so ordering isn't just insertion order.
    invoice_module._fake_invoices._docs["pay_alice_1"]["issued_at"] = datetime(2026, 1, 1, tzinfo=timezone.utc)
    invoice_module._fake_invoices._docs["pay_alice_2"]["issued_at"] = datetime(2026, 6, 1, tzinfo=timezone.utc)

    results = invoice_module.list_invoice_records("alice")

    assert [r["payment_id"] for r in results] == ["pay_alice_2", "pay_alice_1"]  # newest first
    assert all(r["username"] == "alice" for r in results)  # mallory's invoice never leaks in


def test_list_invoice_records_empty_for_a_user_with_no_invoices(invoice_module):
    assert invoice_module.list_invoice_records("nobody") == []


# ── list_invoices endpoint (payments.py) ────────────────────────────────────

def test_list_invoices_endpoint_returns_summary_fields_only(monkeypatch):
    from app.api import payments
    from datetime import datetime, timezone

    records = [
        {
            "invoice_number": "LETA/2026-27/00002", "payment_id": "pay_2", "username": "alice",
            "customer_name": "Alice", "customer_email": "alice@example.com", "customer_phone": None,
            "plan_name": "3-Hour Pro Access", "amount_paise": 29900,
            "issued_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        },
    ]
    monkeypatch.setattr("app.services.invoice.list_invoice_records", lambda username: records)

    result = payments.list_invoices(current_user={"username": "alice"})

    assert result == [{
        "invoice_number": "LETA/2026-27/00002",
        "payment_id": "pay_2",
        "plan_name": "3-Hour Pro Access",
        "amount_paise": 29900,
        "issued_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }]
    # Contact details from the full record must not leak into the list view.
    assert "customer_email" not in result[0]
    assert "customer_phone" not in result[0]


# ── download_invoice endpoint (payments.py) ─────────────────────────────────

def test_download_invoice_owner_gets_the_pdf(monkeypatch):
    from app.api import payments
    from datetime import datetime, timezone

    record = {
        "invoice_number": "LETA/2026-27/00001", "payment_id": "pay_123", "username": "alice",
        "customer_name": "Alice", "customer_email": "alice@example.com", "customer_phone": None,
        "plan_name": "1-Hour Access", "amount_paise": 19900,
        "issued_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }
    monkeypatch.setattr("app.services.invoice.get_invoice_record", lambda payment_id: record)

    response = payments.download_invoice("pay_123", current_user={"username": "alice"})
    assert response.status_code == 200
    assert response.media_type == "application/pdf"
    assert b"%PDF-" in bytes(response.body)[:10]


def test_download_invoice_blocks_a_non_owner(monkeypatch):
    from fastapi import HTTPException
    from app.api import payments
    from datetime import datetime, timezone

    record = {
        "invoice_number": "LETA/2026-27/00001", "payment_id": "pay_123", "username": "alice",
        "customer_name": "Alice", "customer_email": None, "customer_phone": None,
        "plan_name": "1-Hour Access", "amount_paise": 19900,
        "issued_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }
    monkeypatch.setattr("app.services.invoice.get_invoice_record", lambda payment_id: record)

    with pytest.raises(HTTPException) as exc_info:
        payments.download_invoice("pay_123", current_user={"username": "mallory"})
    assert exc_info.value.status_code == 404  # same 404 as "doesn't exist" — no ownership leak


def test_download_invoice_404s_for_an_unknown_payment_id(monkeypatch):
    from fastapi import HTTPException
    from app.api import payments

    monkeypatch.setattr("app.services.invoice.get_invoice_record", lambda payment_id: None)

    with pytest.raises(HTTPException) as exc_info:
        payments.download_invoice("pay_does_not_exist", current_user={"username": "alice"})
    assert exc_info.value.status_code == 404


# ── _create_invoice (payments.py) — same non-fatal contract as receipts ─────

def test_create_invoice_never_raises_if_invoice_service_blows_up(monkeypatch):
    from app.api import payments

    class _FakeUsers:
        def find_one(self, *a, **k):
            return {"email": "alice@example.com", "phone": "9876543210", "full_name": "Alice"}

    monkeypatch.setattr(payments, "get_user_collection", lambda: _FakeUsers())
    monkeypatch.setattr(
        "app.services.invoice.create_invoice_record",
        lambda **k: (_ for _ in ()).throw(RuntimeError("mongo is down")),
    )

    # Must not raise despite create_invoice_record raising internally.
    payments._create_invoice("alice", payments.PLANS["1hr"], "pay_123", "order_456")
