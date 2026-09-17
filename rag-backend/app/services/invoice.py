"""
GST invoice generation for payments.

Design:
  - An `invoices` doc is created exactly once per payment, at credit time
    (called from payments._credit_session, alongside the email/SMS
    receipts) — NOT lazily on first download. This keeps invoice numbers
    assigned in true payment chronology, which is what GST's "sequential,
    no gaps" numbering requirement is actually about; generating a number
    only when someone happens to click download would number invoices in
    download order instead, and skip numbers entirely for invoices no one
    ever downloads.
  - Only the structured DATA is stored (amount, customer, invoice
    number, date) — never a rendered PDF blob. The PDF itself is
    regenerated on demand from that data every time someone downloads it.
    Cheap to redo, keeps the database lean, and means a template/styling
    fix applies retroactively to every past invoice's next download
    without a backfill.
  - Invoice numbers come from an atomically-incremented counter
    (invoice_counters, via find_one_and_update $inc) — never computed by
    counting existing documents, which isn't safe under concurrent
    requests and silently produces duplicates or gaps.

GST treatment — deliberately simplified, flagged rather than guessed at
with false confidence: this shows a single combined "GST" line rather
than splitting into CGST+SGST (intra-state) vs IGST (inter-state),
because that split legally depends on the CUSTOMER's billing state,
which nothing in this checkout flow collects today. Getting that split
wrong would be a real compliance mistake, not a cosmetic one; showing
one honest combined figure is safer than fabricating a state-based split
with no real data behind it. Revisit with an accountant once billing
address is actually collected.
"""
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from app.database import get_invoice_collection, get_invoice_counter_collection

logger = logging.getLogger(__name__)

# Real registered business details, from the Razorpay account's own KYC —
# shown to the user directly (screenshot of dashboard.razorpay.com/app/invoices).
# GST rate: 18%, the standard rate for most B2B/B2C digital/professional
# services in India — flagged, not silently assumed forever: confirm this
# matches LETA TEC's actual registered category.
COMPANY_NAME = "LETATEC AI TECHNOLOGIES PRIVATE LIMITED"
COMPANY_GSTIN = "08AAGCL9166P1ZL"
COMPANY_CIN = "U62010RJ2026PTC114803"
GST_RATE = 0.18


def _current_financial_year() -> str:
    """India's FY runs Apr 1 – Mar 31. e.g. Feb 2026 -> "2025-26"."""
    now = datetime.now(timezone.utc)
    if now.month >= 4:
        start_year = now.year
    else:
        start_year = now.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _next_invoice_number() -> str:
    """Atomically hands out the next sequential invoice number for the
    current financial year. Resets to 1 at the start of each FY (a
    separate counter document per FY) — both patterns (continuous
    numbering, or restart-per-FY) are permitted under GST rules as long
    as numbers stay sequential and gap-free within whichever scheme is
    chosen; restart-per-FY is the more common convention."""
    fy = _current_financial_year()
    counters = get_invoice_counter_collection()
    if counters is None:
        raise RuntimeError("Database unavailable — cannot assign an invoice number")

    from pymongo import ReturnDocument
    doc = counters.find_one_and_update(
        {"_id": f"invoice_seq_{fy}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = doc["seq"]
    return f"LETA/{fy}/{seq:05d}"


def create_invoice_record(
    *,
    payment_id: str,
    order_id: str,
    username: str,
    customer_name: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
    plan_name: str,
    amount_paise: int,
) -> Optional[dict]:
    """
    Creates the invoice's permanent record, assigning it its sequential
    number. Idempotent per payment_id (the unique index on it is the real
    guarantee) — if this payment already has an invoice, returns the
    EXISTING record instead of raising or minting a second number,
    matching /verify and /webhook's own "whichever path gets here first
    wins, the other is a no-op" idempotency pattern elsewhere in payments.

    Returns None (never raises) if the database is unavailable — the
    caller (payments._credit_session, via a wrapper) must treat a missing
    invoice the same non-fatal way it treats a missing receipt: the plan
    is already active regardless.
    """
    invoices = get_invoice_collection()
    if invoices is None:
        return None

    existing = invoices.find_one({"payment_id": payment_id}, {"_id": 0})
    if existing is not None:
        return existing

    invoice_number = _next_invoice_number()
    now = datetime.now(timezone.utc)
    record = {
        "invoice_number": invoice_number,
        "payment_id": payment_id,
        "order_id": order_id,
        "username": username,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "plan_name": plan_name,
        "amount_paise": amount_paise,
        "issued_at": now,
    }
    try:
        invoices.insert_one(dict(record))
    except Exception as e:
        # Duplicate payment_id from a genuine race between /verify and
        # /webhook crediting the same payment near-simultaneously — the
        # unique index caught it; fetch and return whichever record won.
        logger.warning(f"create_invoice_record: insert raced, reusing existing record: {e}")
        existing = invoices.find_one({"payment_id": payment_id}, {"_id": 0})
        return existing
    return record


def get_invoice_record(payment_id: str) -> Optional[dict]:
    invoices = get_invoice_collection()
    if invoices is None:
        return None
    return invoices.find_one({"payment_id": payment_id}, {"_id": 0})


def list_invoice_records(username: str) -> list:
    """All of a user's invoices, newest first — backs the invoice history
    page. Same ownership scoping as get_invoice_record: filtered by the
    invoice's own username field, never a client-supplied one."""
    invoices = get_invoice_collection()
    if invoices is None:
        return []
    return list(
        invoices.find({"username": username}, {"_id": 0}).sort("issued_at", -1)
    )


def render_invoice_pdf(record: dict) -> bytes:
    """Regenerates the PDF from a stored invoice record — never reads a
    cached PDF, always builds it fresh, so a layout fix applies to every
    invoice's next download without a backfill."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="RightAlign", parent=styles["Normal"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="CompanyName", parent=styles["Heading1"], fontSize=14, spaceAfter=2))
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], fontSize=9, textColor=colors.grey))

    amount_rupees = record["amount_paise"] / 100
    base_amount = amount_rupees / (1 + GST_RATE)
    gst_amount = amount_rupees - base_amount

    issued_at = record["issued_at"]
    issued_str = issued_at.strftime("%d %b %Y") if hasattr(issued_at, "strftime") else str(issued_at)

    elements = []

    header_table = Table(
        [[
            Paragraph(f"<b>{COMPANY_NAME}</b><br/>GSTIN: {COMPANY_GSTIN}<br/>CIN: {COMPANY_CIN}", styles["Normal"]),
            Paragraph(f"<b>TAX INVOICE</b><br/>{record['invoice_number']}<br/>Date: {issued_str}", styles["RightAlign"]),
        ]],
        colWidths=[100 * mm, 70 * mm],
    )
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(header_table)
    elements.append(Spacer(1, 10 * mm))

    billed_to = record.get("customer_name") or "Customer"
    contact_line = " / ".join(filter(None, [record.get("customer_email"), record.get("customer_phone")]))
    elements.append(Paragraph(f"<b>Billed To</b><br/>{billed_to}" + (f"<br/>{contact_line}" if contact_line else ""), styles["Normal"]))
    elements.append(Spacer(1, 8 * mm))

    line_items = [
        ["Description", "Amount (Incl. GST)"],
        [f"{record['plan_name']} — Payment ID: {record['payment_id']}", f"Rs.{amount_rupees:,.2f}"],
    ]
    items_table = Table(line_items, colWidths=[120 * mm, 50 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    summary_table = Table(
        [
            ["Taxable Value", f"Rs.{base_amount:,.2f}"],
            [f"GST @ {int(GST_RATE * 100)}%", f"Rs.{gst_amount:,.2f}"],
            ["Total (Paid)", f"Rs.{amount_rupees:,.2f}"],
        ],
        colWidths=[120 * mm, 50 * mm],
    )
    summary_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.75, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12 * mm))

    elements.append(Paragraph(
        "This is a system-generated invoice for a digital service subscription (statutory legal-research "
        "workspace access) and does not require a physical signature. GST shown as a single combined figure; "
        "does not reflect a CGST/SGST vs IGST place-of-supply determination.",
        styles["Meta"],
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Thank you for choosing LETA TEC.", styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()
