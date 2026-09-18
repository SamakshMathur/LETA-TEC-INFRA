"""
GST invoice generation for payments.

Design:
  - An `invoices` doc is created exactly once per payment, at credit time
    (called from payments._credit_session, alongside the email/SMS receipts)
    — NOT lazily on first download. This keeps invoice numbers assigned in true
    payment chronology.
  - Only the structured DATA is stored (amount, customer, invoice number, date,
    and immutable tax breakdown fields) — never a rendered PDF blob. The PDF
    itself is regenerated on demand from that data every time someone downloads it.
  - Invoice numbers come from an atomically-incremented counter (invoice_counters,
    via find_one_and_update $inc) per financial year.
  - Tax calculation is handled deterministically by `app.services.tax.calculate_gst`,
    deriving taxable amount and applicable CGST+SGST (intra-state Rajasthan) vs
    IGST (inter-state outside Rajasthan) from the actual charged amount.
  - Backward compatibility: Historical invoices created before tax breakdown
    continue to render cleanly with legacy representation without data rewrite.
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
from app.services.tax import (
    COMPANY_NAME,
    COMPANY_GSTIN,
    COMPANY_CIN,
    SUPPLIER_STATE_CODE,
    SUPPLIER_STATE_NAME,
    GST_RATE,
    CGST_RATE,
    SGST_RATE,
    IGST_RATE,
    calculate_gst,
    resolve_place_of_supply,
)

logger = logging.getLogger(__name__)


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
    separate counter document per FY)."""
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
    customer_state: Optional[str] = None,
    customer_state_code: Optional[str] = None,
    customer_gstin: Optional[str] = None,
) -> Optional[dict]:
    """
    Creates the invoice's permanent record, assigning it its sequential
    number and computing immutable tax breakdown fields.
    Idempotent per payment_id.
    """
    invoices = get_invoice_collection()
    if invoices is None:
        return None

    existing = invoices.find_one({"payment_id": payment_id}, {"_id": 0})
    if existing is not None:
        return existing

    tax = calculate_gst(
        amount_paise=amount_paise,
        customer_state=customer_state,
        customer_state_code=customer_state_code,
    )

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

        # Immutable tax fields
        "taxable_amount_paise": tax.taxable_amount_paise,
        "total_gst_paise": tax.total_gst_paise,
        "cgst_rate": tax.cgst_rate,
        "cgst_amount_paise": tax.cgst_amount_paise,
        "sgst_rate": tax.sgst_rate,
        "sgst_amount_paise": tax.sgst_amount_paise,
        "igst_rate": tax.igst_rate,
        "igst_amount_paise": tax.igst_amount_paise,
        "is_inter_state": tax.is_inter_state,
        "supplier_state_code": tax.supplier_state_code,
        "supplier_state_name": tax.supplier_state_name,
        "customer_state": tax.customer_state_name,
        "customer_state_code": tax.customer_state_code,
        "place_of_supply": tax.place_of_supply,
        "customer_gstin": customer_gstin,
    }
    try:
        invoices.insert_one(dict(record))
    except Exception as e:
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
    """Regenerates the PDF from a stored invoice record — builds fresh
    so styling applies dynamically while preserving stored financial data."""
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
    issued_at = record["issued_at"]
    issued_str = issued_at.strftime("%d %b %Y") if hasattr(issued_at, "strftime") else str(issued_at)

    elements = []

    pos_display = record.get("place_of_supply") or "Not Specified"
    header_right = f"<b>TAX INVOICE</b><br/>{record['invoice_number']}<br/>Date: {issued_str}<br/>Place of Supply: {pos_display}"

    header_table = Table(
        [[
            Paragraph(
                f"<b>{COMPANY_NAME}</b><br/>"
                f"GSTIN: {COMPANY_GSTIN}<br/>"
                f"CIN: {COMPANY_CIN}<br/>"
                f"State: {SUPPLIER_STATE_NAME} ({SUPPLIER_STATE_CODE})",
                styles["Normal"],
            ),
            Paragraph(header_right, styles["RightAlign"]),
        ]],
        colWidths=[100 * mm, 70 * mm],
    )
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(header_table)
    elements.append(Spacer(1, 10 * mm))

    billed_to = record.get("customer_name") or "Customer"
    contact_parts = list(filter(None, [record.get("customer_email"), record.get("customer_phone")]))
    contact_line = " / ".join(contact_parts)

    billed_lines = [f"<b>Billed To</b>", billed_to]
    if contact_line:
        billed_lines.append(contact_line)
    if record.get("customer_state"):
        code_str = f" ({record.get('customer_state_code')})" if record.get("customer_state_code") else ""
        billed_lines.append(f"State: {record.get('customer_state')}{code_str}")
    if record.get("customer_gstin"):
        billed_lines.append(f"Customer GSTIN: {record.get('customer_gstin')}")

    elements.append(Paragraph("<br/>".join(billed_lines), styles["Normal"]))
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

    # Determine summary breakdown
    is_inter_state = record.get("is_inter_state")
    if "taxable_amount_paise" in record and is_inter_state is not None:
        taxable_rupees = record["taxable_amount_paise"] / 100
        cgst_rupees = record.get("cgst_amount_paise", 0) / 100
        sgst_rupees = record.get("sgst_amount_paise", 0) / 100
        igst_rupees = record.get("igst_amount_paise", 0) / 100
        total_gst_rupees = record.get("total_gst_paise", 0) / 100

        if not is_inter_state:
            # Intra-State Supply (Rajasthan -> Rajasthan)
            cgst_pct = int(record.get("cgst_rate", CGST_RATE) * 100)
            sgst_pct = int(record.get("sgst_rate", SGST_RATE) * 100)
            summary_rows = [
                ["Taxable Value", f"Rs.{taxable_rupees:,.2f}"],
                [f"CGST @ {cgst_pct}%", f"Rs.{cgst_rupees:,.2f}"],
                [f"SGST @ {sgst_pct}%", f"Rs.{sgst_rupees:,.2f}"],
                ["Total GST @ 18%", f"Rs.{total_gst_rupees:,.2f}"],
                ["Grand Total (Paid)", f"Rs.{amount_rupees:,.2f}"],
            ]
            bold_idx = 4
        else:
            # Inter-State Supply (Rajasthan -> Outside Rajasthan)
            igst_pct = int(record.get("igst_rate", IGST_RATE) * 100)
            summary_rows = [
                ["Taxable Value", f"Rs.{taxable_rupees:,.2f}"],
                ["CGST @ 0%", "Rs.0.00"],
                ["SGST @ 0%", "Rs.0.00"],
                [f"IGST @ {igst_pct}%", f"Rs.{igst_rupees:,.2f}"],
                ["Grand Total (Paid)", f"Rs.{amount_rupees:,.2f}"],
            ]
            bold_idx = 4
    else:
        # Legacy fallback for historical invoices generated without state breakdown
        base_amount = amount_rupees / (1 + GST_RATE)
        gst_amount = amount_rupees - base_amount
        summary_rows = [
            ["Taxable Value", f"Rs.{base_amount:,.2f}"],
            [f"GST @ {int(GST_RATE * 100)}%", f"Rs.{gst_amount:,.2f}"],
            ["Total (Paid)", f"Rs.{amount_rupees:,.2f}"],
        ]
        bold_idx = 2

    summary_table = Table(summary_rows, colWidths=[120 * mm, 50 * mm])
    summary_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, bold_idx), (-1, bold_idx), "Helvetica-Bold"),
        ("LINEABOVE", (0, bold_idx), (-1, bold_idx), 0.75, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12 * mm))

    if is_inter_state is False:
        tax_meta = (
            "This is a system-generated tax invoice for digital legal research services. "
            "Supply is intra-State (Place of Supply: Rajasthan); taxes charged as CGST (9%) and SGST (9%)."
        )
    elif is_inter_state is True:
        tax_meta = (
            f"This is a system-generated tax invoice for digital legal research services. "
            f"Supply is inter-State (Place of Supply: {pos_display}); tax charged as IGST (18%)."
        )
    else:
        tax_meta = (
            "This is a system-generated invoice for a digital service subscription (statutory legal-research "
            "workspace access) and does not require a physical signature. GST shown as a single combined figure; "
            "does not reflect a CGST/SGST vs IGST place-of-supply determination."
        )

    elements.append(Paragraph(tax_meta, styles["Meta"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Thank you for choosing LETA TEC.", styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()
