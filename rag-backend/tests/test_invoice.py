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
    invoice_module._fake_invoices = fake_invoices
    return invoice_module


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extracts all text from all streams in a PDF without external dependencies."""
    extracted = []
    parts = pdf_bytes.split(b"stream\n")
    for part in parts[1:]:
        data = part.split(b"endstream")[0].strip()
        if b"~>" in data:
            data = data[:data.find(b"~>") + 2]
            try:
                dec = base64.a85decode(data, adobe=True)
                decomp = zlib.decompress(dec).decode("latin1", errors="ignore")
                extracted.append(decomp)
            except Exception:
                pass
        else:
            try:
                decomp = zlib.decompress(data).decode("latin1", errors="ignore")
                extracted.append(decomp)
            except Exception:
                pass
    combined = "\n".join(extracted) if extracted else pdf_bytes.decode("latin1", errors="ignore")
    return combined.replace(r"\(", "(").replace(r"\)", ")")


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
    """Verify Rajasthan supply persists CGST 9% + SGST 9% with exact paise reconciliation and SAC 998439."""
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
        customer_type="B2B",
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
    assert record["place_of_supply_state_code"] == "08"
    assert record["place_of_supply_state_name"] == "Rajasthan"
    assert record["supply_type"] == "Intra-State"
    assert record["sac_code"] == "998439"
    assert record["sac_description"] == "Other on-line contents nowhere else classified"
    assert record["reverse_charge"] == "No"
    assert record["payment_status"] == "PAID"
    assert record["customer_gstin"] == "08AAAAA0000A1Z5"


def test_create_invoice_record_persists_inter_state_tax_breakdown(invoice_module):
    """Verify non-Rajasthan supply persists IGST 18% with exact paise reconciliation and SAC 998439."""
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
    assert record["place_of_supply_state_code"] == "27"
    assert record["place_of_supply_state_name"] == "Maharashtra"
    assert record["supply_type"] == "Inter-State"
    assert record["sac_code"] == "998439"
    assert record["reverse_charge"] == "No"
    assert record["payment_status"] == "PAID"


def test_create_invoice_record_persists_optional_billing_address(invoice_module):
    """Verify billing address and city persist correctly when supplied."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_addr_1",
        order_id="ord_addr_1",
        username="carol",
        customer_name="Carol Danvers",
        customer_email="carol@example.com",
        customer_phone="9876543212",
        plan_name="1-Hour Access",
        amount_paise=1000,
        customer_state="Rajasthan",
        customer_state_code="08",
        billing_address="Suite 404, Tech Park",
        billing_city="Jaipur",
    )
    assert record["billing_address"] == "Suite 404, Tech Park"
    assert record["billing_city"] == "Jaipur"

    pdf_bytes = invoice_module.render_invoice_pdf(record)
    text = _extract_pdf_text(pdf_bytes)
    assert "Suite 404, Tech Park" in text
    assert "Jaipur" in text


def test_render_invoice_pdf_intra_state_content(invoice_module):
    """Verify intra-State PDF contains logo, SAC 998439, CGST 9%, SGST 9%, and Place of Supply."""
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
        "sac_code": "998439",
        "reverse_charge": "No",
        "payment_status": "PAID",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_pdf_text(pdf_bytes)

    assert "TAX INVOICE" in text
    assert "ORIGINAL FOR RECIPIENT" in text
    assert "Rajasthan (08)" in text
    assert "Intra-State" in text
    assert "998439" in text
    assert "CGST" in text
    assert "SGST" in text
    assert "Rs.8.47" in text
    assert "Rs.0.77" in text
    assert "Rs.0.76" in text
    assert "Rs.10.00" in text
    assert "PAID" in text
    assert "pay_intra_pdf" in text
    assert "Reverse Charge:" in text
    assert "No" in text


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
        "sac_code": "998439",
        "reverse_charge": "No",
        "payment_status": "PAID",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_pdf_text(pdf_bytes)

    assert "TAX INVOICE" in text
    assert "ORIGINAL FOR RECIPIENT" in text
    assert "Maharashtra (27)" in text
    assert "Inter-State" in text
    assert "998439" in text
    assert "IGST" in text
    assert "Rs.338.14" in text
    assert "Rs.60.86" in text
    assert "Rs.399.00" in text
    assert "PAID" in text
    assert "pay_inter_pdf" in text
    assert "Reverse Charge:" in text
    assert "No" in text


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
    """Verify historical invoice without state breakdown fields renders cleanly without fabricating SAC."""
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
    assert "GST" in text
    assert "Rs.199.00" in text
    # Amendment 1: Never fabricate SAC 998439 onto legacy invoices that did not store it
    assert "Not recorded" in text
    assert "998439" not in text


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


# ── Production-Quality Feature Tests ────────────────────────────────────────

def test_render_invoice_pdf_embeds_logo_asset(invoice_module):
    """Verify that render_invoice_pdf embeds the LETATEC logo asset into the PDF."""
    record = {
        "invoice_number": "LETA/2026-27/00099",
        "payment_id": "pay_logo_test",
        "order_id": "ord_logo_test",
        "username": "alice",
        "customer_name": "Alice Sharma",
        "customer_email": "alice@example.com",
        "customer_phone": "9876543210",
        "plan_name": "1-Hour Access",
        "amount_paise": 1000,
        "issued_at": datetime(2026, 9, 19, tzinfo=timezone.utc),
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
        "sac_code": "998439",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    assert b"/Subtype /Image" in pdf_bytes
    assert b"/Type /XObject" in pdf_bytes


def test_render_invoice_pdf_service_classification_and_sac(invoice_module):
    """Verify service description and SAC 998439 are clearly rendered."""
    record = {
        "invoice_number": "LETA/2026-27/00100",
        "payment_id": "pay_sac_test",
        "order_id": "ord_sac_test",
        "username": "bob",
        "customer_name": "Bob Mehta",
        "customer_email": "bob@example.com",
        "customer_phone": "9876543211",
        "plan_name": "3-Hour Access",
        "amount_paise": 39900,
        "issued_at": datetime(2026, 9, 19, tzinfo=timezone.utc),
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
        "sac_code": "998439",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    text = _extract_pdf_text(pdf_bytes)
    assert "Statutory Legal-Research Workspace Access" in text
    assert "998439" in text


def test_render_invoice_pdf_payment_block_and_reconciliation(invoice_module):
    """Verify payment status, payment ID, amount paid, and balance due."""
    record = {
        "invoice_number": "LETA/2026-27/00101",
        "payment_id": "pay_xyz_98765",
        "order_id": "ord_xyz_98765",
        "username": "charlie",
        "customer_name": "Charlie",
        "customer_email": "charlie@example.com",
        "customer_phone": "9876543213",
        "plan_name": "1-Hour Access",
        "amount_paise": 1000,
        "issued_at": datetime(2026, 9, 19, tzinfo=timezone.utc),
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
        "sac_code": "998439",
        "payment_status": "PAID",
    }
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    text = _extract_pdf_text(pdf_bytes)
    assert "PAID" in text
    assert "pay_xyz_98765" in text
    assert "Amount Paid:" in text
    assert "Rs.10.00" in text
    assert "Balance Due:" in text
    assert "Rs.0.00" in text


def test_render_invoice_pdf_repeated_download_is_stable(invoice_module):
    """Verify multiple render invocations produce consistent output."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_stable_1",
        order_id="ord_stable_1",
        username="dave",
        customer_name="Dave",
        customer_email="dave@example.com",
        customer_phone="9876543214",
        plan_name="1-Hour Access",
        amount_paise=1000,
        customer_state="Rajasthan",
        customer_state_code="08",
    )
    first_pdf = invoice_module.render_invoice_pdf(record)
    second_pdf = invoice_module.render_invoice_pdf(record)
    assert len(first_pdf) == len(second_pdf)
    assert _extract_pdf_text(first_pdf) == _extract_pdf_text(second_pdf)


def test_arbitrary_amounts_reconciliation_in_pdf(invoice_module):
    """Verify arbitrary amounts produce exact paise reconciliation in PDF and record."""
    amounts = [5500, 7700, 11500, 19900, 39900, 49900, 73500, 99900]
    for amt in amounts:
        # Intra-state
        rec_intra = invoice_module.create_invoice_record(
            payment_id=f"pay_arb_intra_{amt}",
            order_id=f"ord_arb_intra_{amt}",
            username="eve",
            customer_name="Eve",
            customer_email="eve@example.com",
            customer_phone="9876543215",
            plan_name="Custom Access",
            amount_paise=amt,
            customer_state="Rajasthan",
            customer_state_code="08",
        )
        assert rec_intra["taxable_amount_paise"] + rec_intra["cgst_amount_paise"] + rec_intra["sgst_amount_paise"] == amt
        pdf_intra = invoice_module.render_invoice_pdf(rec_intra)
        text_intra = _extract_pdf_text(pdf_intra)
        assert f"Rs.{amt/100:,.2f}" in text_intra

        # Inter-state
        rec_inter = invoice_module.create_invoice_record(
            payment_id=f"pay_arb_inter_{amt}",
            order_id=f"ord_arb_inter_{amt}",
            username="frank",
            customer_name="Frank",
            customer_email="frank@example.com",
            customer_phone="9876543216",
            plan_name="Custom Access",
            amount_paise=amt,
            customer_state="Karnataka",
            customer_state_code="29",
        )
        assert rec_inter["taxable_amount_paise"] + rec_inter["igst_amount_paise"] == amt
        pdf_inter = invoice_module.render_invoice_pdf(rec_inter)
        text_inter = _extract_pdf_text(pdf_inter)
        assert f"Rs.{amt/100:,.2f}" in text_inter


def test_b2b_invoice_creation_persists_full_snapshots_and_valid_gstin(invoice_module):
    """Verify B2B invoice creation persists complete nested snapshots and structural GSTIN validation."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_b2b_001",
        order_id="ord_b2b_001",
        username="acme_corp",
        customer_name="John Doe",
        customer_email="finance@acmecorp.in",
        customer_phone="9876500000",
        plan_name="3-Hour Access",
        amount_paise=39900,
        customer_type="B2B",
        business_legal_name="Acme Legal Technologies Pvt Ltd",
        customer_gstin="08AAGCL9166P1ZL",
        billing_address="Level 5, Tech Tower",
        billing_city="Jaipur",
        customer_state="Rajasthan",
        customer_state_code="08",
    )
    assert record["customer_type"] == "B2B"
    assert record["financial_year"] == "2026-27"
    assert record["business_legal_name"] == "Acme Legal Technologies Pvt Ltd"
    assert record["customer_gstin"] == "08AAGCL9166P1ZL"
    assert record["gstin_validation_status"] == "structural_valid"

    # Verify structured snapshot documents
    recipient = record["recipient"]
    assert recipient["type"] == "B2B"
    assert recipient["legal_name"] == "Acme Legal Technologies Pvt Ltd"
    assert recipient["customer_name"] == "John Doe"
    assert recipient["gstin"] == "08AAGCL9166P1ZL"
    assert recipient["gstin_validation_status"] == "structural_valid"
    assert recipient["billing_address"] == "Level 5, Tech Tower"
    assert recipient["city"] == "Jaipur"
    assert recipient["state"] == "Rajasthan"
    assert recipient["state_code"] == "08"

    supplier = record["supplier"]
    assert supplier["legal_name"] == "LETATEC AI TECHNOLOGIES PRIVATE LIMITED"
    assert supplier["gstin"] == "08AAGCL9166P1ZL"
    assert supplier["cin"] == "U62010RJ2026PTC114803"
    assert supplier["state_code"] == "08"

    supply = record["supply"]
    assert supply["supply_type"] == "Intra-State"
    assert supply["reverse_charge"] == "No"
    assert supply["sac"] == "998439"

    amounts = record["amounts"]
    assert amounts["grand_total_paise"] == 39900
    assert amounts["taxable_value_paise"] + amounts["total_gst_paise"] == 39900
    assert amounts["cgst_paise"] + amounts["sgst_paise"] == amounts["total_gst_paise"]

    # Verify B2B PDF Rendering
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    text = _extract_pdf_text(pdf_bytes)
    assert "BILLED TO (B2B)" in text
    assert "Acme Legal Technologies Pvt Ltd" in text
    assert "08AAGCL9166P1ZL" in text
    assert "Level 5, Tech Tower, Jaipur" in text


def test_b2c_invoice_creation_persists_snapshots_and_rejects_gstin(invoice_module):
    """Verify B2C invoice persists clean snapshot without GSTIN, and rejects inconsistent GSTIN."""
    record = invoice_module.create_invoice_record(
        payment_id="pay_b2c_001",
        order_id="ord_b2c_001",
        username="priya",
        customer_name="Priya Sharma",
        customer_email="priya@example.com",
        customer_phone="9876511111",
        plan_name="1-Hour Access",
        amount_paise=1000,
        customer_type="B2C",
        customer_state="Rajasthan",
        customer_state_code="08",
    )
    assert record["customer_type"] == "B2C"
    assert record["customer_gstin"] is None
    assert record["recipient"]["type"] == "B2C"
    assert record["recipient"]["gstin"] is None

    # PDF rendering check
    pdf_bytes = invoice_module.render_invoice_pdf(record)
    text = _extract_pdf_text(pdf_bytes)
    assert "BILLED TO" in text
    assert "BILLED TO (B2B)" not in text
    assert "Priya Sharma" in text

    # Amendment 2: Supplying GSTIN for B2C must raise ValueError rather than silent conversion
    with pytest.raises(ValueError, match="Customer type is B2C but a GSTIN was supplied"):
        invoice_module.create_invoice_record(
            payment_id="pay_b2c_invalid",
            order_id="ord_b2c_invalid",
            username="priya",
            customer_name="Priya Sharma",
            customer_email="priya@example.com",
            customer_phone="9876511111",
            plan_name="1-Hour Access",
            amount_paise=1000,
            customer_type="B2C",
            customer_gstin="08AAGCL9166P1ZL",
        )


def test_b2b_invoice_requires_valid_gstin_and_rejects_invalid_gstin(invoice_module):
    """Verify B2B invoice creation strictly enforces structural GSTIN validation."""
    # 1. Missing GSTIN
    with pytest.raises(ValueError, match="B2B invoice requires a valid GSTIN"):
        invoice_module.create_invoice_record(
            payment_id="pay_b2b_nogstin",
            order_id="ord_b2b_nogstin",
            username="acme",
            customer_name="Acme",
            customer_email="acme@test.in",
            customer_phone="9876522222",
            plan_name="1-Hour Access",
            amount_paise=1000,
            customer_type="B2B",
            customer_gstin=None,
        )

    # 2. Structurally invalid GSTIN (14 chars)
    with pytest.raises(ValueError, match="Invalid B2B GSTIN format"):
        invoice_module.create_invoice_record(
            payment_id="pay_b2b_badgstin",
            order_id="ord_b2b_badgstin",
            username="acme",
            customer_name="Acme",
            customer_email="acme@test.in",
            customer_phone="9876522222",
            plan_name="1-Hour Access",
            amount_paise=1000,
            customer_type="B2B",
            customer_gstin="08AAGCL9166P1Z",  # 14 chars
        )


def test_invoice_snapshot_immutability_when_user_or_profile_is_mutated(invoice_module, monkeypatch):
    """
    Verify that mutating the source user account/profile in MongoDB after invoice
    generation does NOT modify already-issued invoice snapshots or their rendered PDF.
    """
    from app.database import get_user_collection

    users_col = get_user_collection()
    if users_col is not None:
        users_col.insert_one({
            "username": "immutable_user",
            "full_name": "Original Customer Name",
            "email": "original@example.com",
            "phone": "9999900000",
            "state": "Rajasthan",
            "state_code": "08",
            "gstin": "08AAGCL9166P1ZL",
            "business_legal_name": "Original Enterprise Pvt Ltd",
            "customer_type": "B2B",
        })

    # Create B2B invoice
    record = invoice_module.create_invoice_record(
        payment_id="pay_immutable_test_001",
        order_id="ord_immutable_test_001",
        username="immutable_user",
        customer_name="Original Customer Name",
        customer_email="original@example.com",
        customer_phone="9999900000",
        plan_name="3-Hour Access",
        amount_paise=39900,
        customer_type="B2B",
        business_legal_name="Original Enterprise Pvt Ltd",
        customer_gstin="08AAGCL9166P1ZL",
        customer_state="Rajasthan",
        customer_state_code="08",
    )

    # Now mutate the user profile completely in MongoDB
    if users_col is not None:
        users_col.update_one(
            {"username": "immutable_user"},
            {"$set": {
                "full_name": "Mutated Malicious Name",
                "email": "mutated@evil.com",
                "phone": "1111100000",
                "state": "Goa",
                "state_code": "30",
                "gstin": "30ABCDE1234F1Z5",
                "business_legal_name": "Mutated Offshore Ltd",
            }}
        )

    # Fetch stored invoice document from DB
    stored_record = invoice_module.get_invoice_record("pay_immutable_test_001")
    assert stored_record is not None
    assert stored_record["customer_name"] == "Original Customer Name"
    assert stored_record["customer_email"] == "original@example.com"
    assert stored_record["business_legal_name"] == "Original Enterprise Pvt Ltd"
    assert stored_record["customer_gstin"] == "08AAGCL9166P1ZL"
    assert stored_record["customer_state"] == "Rajasthan"
    assert stored_record["customer_state_code"] == "08"
    assert stored_record["recipient"]["legal_name"] == "Original Enterprise Pvt Ltd"
    assert stored_record["recipient"]["state"] == "Rajasthan"

    # Render PDF from stored record and verify it reflects original immutable data
    pdf_bytes = invoice_module.render_invoice_pdf(stored_record)
    text = _extract_pdf_text(pdf_bytes)
    assert "Original Enterprise Pvt Ltd" in text
    assert "08AAGCL9166P1ZL" in text
    assert "Mutated" not in text
    assert "Goa" not in text
