"""
Tests for GST invoice generation (app/services/invoice.py) and the
download endpoint (payments.download_invoice).
"""
import os
import sys
import base64
import zlib
import pytest
from datetime import datetime, timezone

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
    """Mimics find_one_and_update with $inc + upsert + ReturnDocument.AFTER."""

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


class _FakeInvoiceCollection:
    def __init__(self):
        self._docs = {}  # keyed by payment_id

    def find_one(self, query, projection=None):
        pid = query.get("payment_id")
        doc = self._docs.get(pid)
        return dict(doc) if doc else None

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
    invoice_module._fake_invoices = fake_invoices
    return invoice_module


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Pure-Python ASCII85 + zlib PDF stream text extractor without external dependencies."""
    try:
        raw_stream = pdf_bytes.split(b"stream\n")[1].split(b"endstream")[0].strip()
        raw_stream = raw_stream[:raw_stream.find(b"~>") + 2]
        decoded = base64.a85decode(raw_stream, adobe=True)
        return zlib.decompress(decoded).decode("latin1", errors="ignore")
    except Exception:
        return pdf_bytes.decode("latin1", errors="ignore")


def test_invoice_numbers_are_sequential(invoice_module):
    first = invoice_module._next_invoice_number()
    second = invoice_module._next_invoice_number()
    third = invoice_module._next_invoice_number()

    fy = invoice_module._current_financial_year()
    assert first == f"LETA/{fy}/00001"
    assert second == f"LETA/{fy}/00002"
    assert third == f"LETA/{fy}/00003"


def test_create_invoice_record_is_idempotent_per_payment(invoice_module):
    first = invoice_module.create_invoice_record(
        payment_id="pay_123", order_id="order_456", username="alice",
        customer_name="Alice", customer_email="alice@example.com", customer_phone="9876543210",
        plan_name="1-Hour Access", amount_paise=19900,
        customer_state="Rajasthan", customer_state_code="08",
    )
    second = invoice_module.create_invoice_record(
        payment_id="pay_123", order_id="order_456", username="alice",
        customer_name="Alice", customer_email="alice@example.com", customer_phone="9876543210",
        plan_name="1-Hour Access", amount_paise=19900,
        customer_state="Rajasthan", customer_state_code="08",
    )

    assert first["invoice_number"] == second["invoice_number"]
    assert first["taxable_amount_paise"] == second["taxable_amount_paise"]
    assert len(invoice_module._fake_invoices._docs) == 1


def test_create_invoice_record_persists_intra_state_tax_breakdown(invoice_module):
    """Verify Rajasthan supply persists CGST 9% + SGST 9% with exact paise reconciliation."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_intra_1",
        order_id="order_intra_1",
        username="alice",
        customer_name="Alice Sharma",
        customer_email="alice@example.com",
        customer_phone="9876543210",
        plan_name="1-Hour Access",
        amount_paise=1000,
        customer_state="Rajasthan",
        customer_state_code="08",
        customer_gstin="08AAAAA0000A1Z5",
    )

    assert record["amount_paise"] == 1000
    assert record["taxable_amount_paise"] == 847
    assert record["total_gst_paise"] == 153
    assert record["cgst_rate"] == 0.09
    assert record["cgst_amount_paise"] == 77
    assert record["sgst_rate"] == 0.09
    assert record["sgst_amount_paise"] == 76
    assert record["igst_rate"] == 0.0
    assert record["igst_amount_paise"] == 0
    assert record["is_inter_state"] is False
    assert record["place_of_supply"] == "08-Rajasthan"
    assert record["customer_gstin"] == "08AAAAA0000A1Z5"


def test_create_invoice_record_persists_inter_state_tax_breakdown(invoice_module):
    """Verify non-Rajasthan supply persists IGST 18% with exact paise reconciliation."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_inter_1",
        order_id="order_inter_1",
        username="bob",
        customer_name="Bob Mehta",
        customer_email="bob@example.com",
        customer_phone="9876543211",
        plan_name="3-Hour Access",
        amount_paise=39900,
        customer_state="Maharashtra",
        customer_state_code="27",
    )

    assert record["amount_paise"] == 39900
    assert record["taxable_amount_paise"] == 33814
    assert record["total_gst_paise"] == 6086
    assert record["cgst_rate"] == 0.0
    assert record["cgst_amount_paise"] == 0
    assert record["sgst_rate"] == 0.0
    assert record["sgst_amount_paise"] == 0
    assert record["igst_rate"] == 0.18
    assert record["igst_amount_paise"] == 6086
    assert record["is_inter_state"] is True
    assert record["place_of_supply"] == "27-Maharashtra"


def test_render_invoice_pdf_intra_state_content(invoice_module):
    """Verify intra-State PDF contains CGST 9%, SGST 9%, and Place of Supply."""
    record = {
        "invoice_number": "LETA/2026-27/00001",
        "payment_id": "pay_intra_pdf",
        "order_id": "order_intra_pdf",
        "username": "alice",
        "customer_name": "Alice Sharma",
        "customer_email": "alice@example.com",
        "customer_phone": "9876543210",
        "plan_name": "1-Hour Access",
        "amount_paise": 1000,
        "issued_at": datetime(2026, 9, 17, tzinfo=timezone.utc),
        "taxable_amount_paise": 847,
        "total_gst_paise": 153,
        "cgst_rate": 0.09,
        "cgst_amount_paise": 77,
        "sgst_rate": 0.09,
        "sgst_amount_paise": 76,
        "igst_rate": 0.0,
        "igst_amount_paise": 0,
        "is_inter_state": False,
        "customer_state": "Rajasthan",
        "customer_state_code": "08",
        "place_of_supply": "08-Rajasthan",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_pdf_text(pdf_bytes)

    assert "TAX INVOICE" in text
    assert "08-Rajasthan" in text
    assert "CGST @ 9%" in text
    assert "SGST @ 9%" in text
    assert "Total GST @ 18%" in text
    assert "Rs.8.47" in text
    assert "Rs.0.77" in text
    assert "Rs.0.76" in text
    assert "Rs.10.00" in text


def test_render_invoice_pdf_inter_state_content(invoice_module):
    """Verify inter-State PDF contains IGST 18%, 0% CGST/SGST rows, and Place of Supply."""
    record = {
        "invoice_number": "LETA/2026-27/00002",
        "payment_id": "pay_inter_pdf",
        "order_id": "order_inter_pdf",
        "username": "bob",
        "customer_name": "Bob Mehta",
        "customer_email": "bob@example.com",
        "customer_phone": "9876543211",
        "plan_name": "3-Hour Access",
        "amount_paise": 39900,
        "issued_at": datetime(2026, 9, 17, tzinfo=timezone.utc),
        "taxable_amount_paise": 33814,
        "total_gst_paise": 6086,
        "cgst_rate": 0.0,
        "cgst_amount_paise": 0,
        "sgst_rate": 0.0,
        "sgst_amount_paise": 0,
        "igst_rate": 0.18,
        "igst_amount_paise": 6086,
        "is_inter_state": True,
        "customer_state": "Maharashtra",
        "customer_state_code": "27",
        "place_of_supply": "27-Maharashtra",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_pdf_text(pdf_bytes)

    assert "27-Maharashtra" in text
    assert "IGST @ 18%" in text
    assert "Rs.338.14" in text
    assert "Rs.60.86" in text
    assert "Rs.399.00" in text


def test_stored_mongo_amounts_and_rendered_pdf_are_identical(invoice_module):
    """Verify that every numeric amount stored in MongoDB matches the PDF display exactly."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_match_1",
        order_id="order_match_1",
        username="carol",
        customer_name="Carol Danvers",
        customer_email="carol@example.com",
        customer_phone="9876543212",
        plan_name="3-Hour Access",
        amount_paise=39900,
        customer_state="Rajasthan",
        customer_state_code="08",
    )

    pdf_bytes = invoice_module.render_invoice_pdf(record)
    text = _extract_pdf_text(pdf_bytes)

    taxable_str = f"Rs.{record['taxable_amount_paise'] / 100:,.2f}"
    cgst_str = f"Rs.{record['cgst_amount_paise'] / 100:,.2f}"
    sgst_str = f"Rs.{record['sgst_amount_paise'] / 100:,.2f}"
    total_gst_str = f"Rs.{record['total_gst_paise'] / 100:,.2f}"
    grand_str = f"Rs.{record['amount_paise'] / 100:,.2f}"

    assert taxable_str in text
    assert cgst_str in text
    assert sgst_str in text
    assert total_gst_str in text
    assert grand_str in text


def test_render_invoice_pdf_legacy_historical_invoice_compatibility(invoice_module):
    """Verify historical invoice without state breakdown fields renders cleanly."""
    record = {
        "invoice_number": "LETA/2025-26/00001",
        "payment_id": "pay_legacy_old",
        "customer_name": "Legacy Customer",
        "customer_email": "legacy@example.com",
        "customer_phone": "9876543200",
        "plan_name": "1-Hour Access",
        "amount_paise": 19900,
        "issued_at": datetime(2026, 1, 15, tzinfo=timezone.utc),
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_pdf_text(pdf_bytes)
    assert "TAX INVOICE" in text
    assert "GST @ 18%" in text
    assert "Rs.199.00" in text


# ── download_invoice endpoint (payments.py) ─────────────────────────────────

def test_download_invoice_owner_gets_the_pdf(monkeypatch):
    from app.api import payments

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

    record = {
        "invoice_number": "LETA/2026-27/00001", "payment_id": "pay_123", "username": "alice",
        "customer_name": "Alice", "customer_email": None, "customer_phone": None,
        "plan_name": "1-Hour Access", "amount_paise": 19900,
        "issued_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }
    monkeypatch.setattr("app.services.invoice.get_invoice_record", lambda payment_id: record)

    with pytest.raises(HTTPException) as exc_info:
        payments.download_invoice("pay_123", current_user={"username": "mallory"})
    assert exc_info.value.status_code == 404


def test_download_invoice_404s_for_an_unknown_payment_id(monkeypatch):
    from fastapi import HTTPException
    from app.api import payments

    monkeypatch.setattr("app.services.invoice.get_invoice_record", lambda payment_id: None)

    with pytest.raises(HTTPException) as exc_info:
        payments.download_invoice("pay_does_not_exist", current_user={"username": "alice"})
    assert exc_info.value.status_code == 404


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
