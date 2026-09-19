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
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

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
    SAC_CODE,
    SAC_DESCRIPTION,
    REVERSE_CHARGE,
    calculate_gst,
    resolve_place_of_supply,
    validate_gstin_structure,
    get_financial_year,
)

logger = logging.getLogger(__name__)


def _get_logo_path() -> Optional[str]:
    """Resolves local path to the LETATEC logo asset for PDF embedding."""
    # 1. Self-contained backend assets
    candidate = os.path.join(os.path.dirname(__file__), "..", "assets", "leta-logo.png")
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
    candidate = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
    # 2. Frontend public asset fallback
    candidate = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "LETA_WHITE_ON_BLACK_4K.png")
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
    return None


def _format_place_of_supply(
    pos_str: Optional[str],
    state_name: Optional[str] = None,
    state_code: Optional[str] = None,
) -> str:
    """Formats place of supply as 'State Name (Code)' e.g. 'Rajasthan (08)'."""
    if state_name and state_code:
        return f"{state_name} ({state_code})"
    if not pos_str:
        return "Not Specified"
    if "-" in pos_str:
        parts = pos_str.split("-", 1)
        if len(parts) == 2 and parts[0].isdigit():
            return f"{parts[1]} ({parts[0]})"
    return pos_str


def _current_financial_year() -> str:
    """India's FY runs Apr 1 – Mar 31. e.g. Feb 2026 -> "2025-26"."""
    return get_financial_year()


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
    billing_address: Optional[str] = None,
    billing_city: Optional[str] = None,
    place_of_supply_state: Optional[str] = None,
    place_of_supply_state_code: Optional[str] = None,
    customer_type: str = "B2C",
    business_legal_name: Optional[str] = None,
) -> Optional[dict]:
    """
    Creates the invoice's permanent record, assigning it its sequential
    number and computing immutable tax breakdown fields via authoritative tax.py.
    Builds structured recipient/supplier snapshots for GST reporting and accounting.
    Idempotent per payment_id.
    """
    invoices = get_invoice_collection()
    if invoices is None:
        return None

    existing = invoices.find_one({"payment_id": payment_id}, {"_id": 0})
    if existing is not None:
        return existing

    # Explicit B2B / B2C validation and normalization
    cust_type = (customer_type or "B2C").strip().upper()
    if cust_type not in ("B2B", "B2C"):
        raise ValueError(f"Invalid customer_type '{customer_type}'. Must be 'B2B' or 'B2C'.")

    clean_gstin = customer_gstin.strip().upper() if customer_gstin else None
    gstin_validation_status = None
    legal_name = (business_legal_name or customer_name).strip() if business_legal_name or customer_name else customer_name

    if cust_type == "B2B":
        if not clean_gstin:
            raise ValueError("B2B invoice requires a valid GSTIN.")
        is_valid, gstin_state_code, err = validate_gstin_structure(clean_gstin)
        if not is_valid:
            raise ValueError(f"Invalid B2B GSTIN format: {err}")
        gstin_validation_status = "structural_valid"
        # If place-of-supply or customer state code not provided, derive from GSTIN prefix
        if not customer_state_code and not customer_state and not place_of_supply_state_code and not place_of_supply_state:
            customer_state_code = gstin_state_code
    elif cust_type == "B2C":
        if clean_gstin:
            raise ValueError("Customer type is B2C but a GSTIN was supplied. GSTIN is only permitted for B2B invoices.")
        clean_gstin = None
        gstin_validation_status = None
        legal_name = None

    tax = calculate_gst(
        amount_paise=amount_paise,
        customer_state=customer_state,
        customer_state_code=customer_state_code,
        place_of_supply_state=place_of_supply_state,
        place_of_supply_state_code=place_of_supply_state_code,
    )

    invoice_number = _next_invoice_number()
    now = datetime.now(timezone.utc)
    fy = get_financial_year(now)

    # 1. Structured snapshots for GST reporting & accounting
    supplier_snapshot = {
        "legal_name": COMPANY_NAME,
        "gstin": COMPANY_GSTIN,
        "cin": COMPANY_CIN,
        "state": SUPPLIER_STATE_NAME,
        "state_code": SUPPLIER_STATE_CODE,
    }

    recipient_snapshot = {
        "type": cust_type,
        "legal_name": legal_name if cust_type == "B2B" else customer_name,
        "customer_name": customer_name,
        "email": customer_email,
        "phone": customer_phone,
        "gstin": clean_gstin,
        "gstin_validation_status": gstin_validation_status,
        "billing_address": billing_address,
        "city": billing_city,
        "state": tax.customer_state_name,
        "state_code": tax.customer_state_code,
    }

    supply_snapshot = {
        "place_of_supply": tax.place_of_supply,
        "place_of_supply_state_code": tax.place_of_supply_state_code,
        "place_of_supply_state_name": tax.place_of_supply_state_name,
        "supply_type": tax.supply_type,
        "reverse_charge": tax.reverse_charge,
        "sac": tax.sac_code,
    }

    amounts_snapshot = {
        "taxable_value_paise": tax.taxable_amount_paise,
        "cgst_paise": tax.cgst_amount_paise,
        "sgst_paise": tax.sgst_amount_paise,
        "igst_paise": tax.igst_amount_paise,
        "total_gst_paise": tax.total_gst_paise,
        "grand_total_paise": tax.grand_total_paise,
    }

    payment_snapshot = {
        "payment_id": payment_id,
        "order_id": order_id,
        "payment_status": "PAID",
        "paid_at": now,
    }

    service_snapshot = {
        "plan_name": plan_name,
        "description": f"Statutory Legal-Research Workspace Access — {plan_name}",
        "sac": tax.sac_code,
        "sac_description": tax.sac_description,
    }

    record = {
        "invoice_number": invoice_number,
        "financial_year": fy,
        "payment_id": payment_id,
        "order_id": order_id,
        "username": username,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "plan_name": plan_name,
        "amount_paise": amount_paise,
        "issued_at": now,

        # Nested snapshots
        "supplier": supplier_snapshot,
        "recipient": recipient_snapshot,
        "supply": supply_snapshot,
        "amounts": amounts_snapshot,
        "payment": payment_snapshot,
        "service": service_snapshot,

        # Immutable flat tax & customer fields for backward compatibility
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
        "place_of_supply_state_code": tax.place_of_supply_state_code,
        "place_of_supply_state_name": tax.place_of_supply_state_name,
        "supply_type": tax.supply_type,
        "sac_code": tax.sac_code,
        "sac_description": tax.sac_description,
        "reverse_charge": tax.reverse_charge,
        "customer_type": cust_type,
        "business_legal_name": legal_name if cust_type == "B2B" else None,
        "customer_gstin": clean_gstin,
        "gstin_validation_status": gstin_validation_status,
        "billing_address": billing_address,
        "billing_city": billing_city,
        "payment_status": "PAID",
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
        buf,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="InvoiceRightAlign",
        parent=styles["Normal"],
        alignment=TA_RIGHT,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        name="SupplierText",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        name="BilledToText",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="FooterText",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    ))

    amount_rupees = record["amount_paise"] / 100
    issued_at = record.get("issued_at") or record.get("invoice_date") or datetime.now(timezone.utc)
    issued_str = issued_at.strftime("%d %b %Y") if hasattr(issued_at, "strftime") else str(issued_at)

    elements = []

    # 1. HEADER SECTION: Company info + Logo on Left, Tax Invoice particulars on Right
    logo_path = _get_logo_path()
    company_lines = [
        f"<b>{COMPANY_NAME}</b>",
        f"GSTIN: {COMPANY_GSTIN}",
        f"CIN: {COMPANY_CIN}",
        f"State: {SUPPLIER_STATE_NAME} ({SUPPLIER_STATE_CODE})",
    ]
    company_para = Paragraph("<br/>".join(company_lines), styles["SupplierText"])

    if logo_path:
        logo_img = Image(logo_path, width=20 * mm, height=20 * mm)
        left_header = Table([[logo_img, company_para]], colWidths=[24 * mm, 81 * mm])
        left_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        left_header = company_para

    # Place of supply formatting
    pos_display = _format_place_of_supply(
        record.get("place_of_supply"),
        record.get("place_of_supply_state_name") or record.get("customer_state"),
        record.get("place_of_supply_state_code") or record.get("customer_state_code"),
    )

    supply_type = record.get("supply_type")
    if not supply_type:
        is_inter = record.get("is_inter_state")
        if is_inter is True:
            supply_type = "Inter-State"
        elif is_inter is False:
            supply_type = "Intra-State"
        else:
            supply_type = "Unspecified"

    reverse_charge = record.get("reverse_charge", REVERSE_CHARGE)

    right_header_lines = [
        '<font color="#475569"><b>ORIGINAL FOR RECIPIENT</b></font>',
        '<font size="12"><b>TAX INVOICE</b></font>',
        f"<b>Invoice No:</b> {record['invoice_number']}",
        f"<b>Invoice Date:</b> {issued_str}",
        f"<b>Place of Supply:</b> {pos_display}",
        f"<b>Supply Type:</b> {supply_type}",
        f"<b>Reverse Charge:</b> {reverse_charge}",
    ]
    right_header = Paragraph("<br/>".join(right_header_lines), styles["InvoiceRightAlign"])

    header_table = Table([[left_header, right_header]], colWidths=[105 * mm, 75 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # 2. CUSTOMER / BILLED TO SECTION (B2B vs B2C aware)
    recipient = record.get("recipient") or {}
    cust_type = record.get("customer_type") or recipient.get("type") or ("B2B" if (record.get("customer_gstin") or recipient.get("gstin")) else "B2C")

    billed_lines = []
    if cust_type == "B2B":
        billed_lines.append("<b>BILLED TO (B2B)</b>")
        legal_name = record.get("business_legal_name") or recipient.get("legal_name") or record.get("customer_name") or "Business Customer"
        billed_lines.append(f"<b>{legal_name}</b>")
        gstin_val = record.get("customer_gstin") or recipient.get("gstin")
        if gstin_val:
            billed_lines.append(f"<b>GSTIN:</b> {gstin_val}")
        contact_person = record.get("customer_name") or recipient.get("customer_name")
        if contact_person and contact_person != legal_name:
            billed_lines.append(f"Attention: {contact_person}")
    else:
        billed_lines.append("<b>BILLED TO</b>")
        cust_name = record.get("customer_name") or recipient.get("customer_name") or "Customer"
        billed_lines.append(f"<b>{cust_name}</b>")

    phone = record.get("customer_phone") or recipient.get("phone")
    if phone:
        billed_lines.append(f"Phone: {phone}")
    email = record.get("customer_email") or recipient.get("email")
    if email:
        billed_lines.append(f"Email: {email}")
    addr = record.get("billing_address") or recipient.get("billing_address")
    city = record.get("billing_city") or recipient.get("city")
    if addr:
        full_addr = f"{addr}, {city}" if city else addr
        billed_lines.append(f"Billing Address: {full_addr}")
    state = record.get("customer_state") or recipient.get("state")
    state_code = record.get("customer_state_code") or recipient.get("state_code")
    if state:
        code_str = f" ({state_code})" if state_code else ""
        billed_lines.append(f"State: {state}{code_str}")

    elements.append(Paragraph("<br/>".join(billed_lines), styles["BilledToText"]))
    elements.append(Spacer(1, 6 * mm))

    # 3. SERVICE CLASSIFICATION / LINE ITEMS TABLE
    raw_plan = record.get("plan_name", "")
    if "1-Hour" in raw_plan or "1hr" in raw_plan.lower():
        desc = "Statutory Legal-Research Workspace Access — 1 Hour"
    elif "3-Hour" in raw_plan or "3hr" in raw_plan.lower():
        desc = "Statutory Legal-Research Workspace Access — 3 Hours"
    elif raw_plan:
        desc = f"Statutory Legal-Research Workspace Access — {raw_plan}"
    else:
        desc = "Statutory Legal-Research Workspace Access"

    # Amendment 1: Never fabricate SAC 998439 onto legacy invoices that did not store it.
    sac_display = record.get("sac_code") or "Not recorded"

    line_items = [
        ["Description", "SAC", "Amount (Incl. GST)"],
        [desc, sac_display, f"Rs.{amount_rupees:,.2f}"],
    ]
    items_table = Table(line_items, colWidths=[110 * mm, 30 * mm, 40 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 6 * mm))

    # 4. PAYMENT INFORMATION BLOCK & TAX BREAKUP TABLE
    payment_status = record.get("payment_status", "PAID")
    payment_id = record.get("payment_id", "N/A")
    pay_data = [
        ["<b>PAYMENT INFORMATION</b>", ""],
        ["Payment Status:", f"<b>{payment_status}</b>"],
        ["Payment ID:", payment_id],
        ["Payment Date:", issued_str],
        ["Amount Paid:", f"Rs.{amount_rupees:,.2f}"],
        ["Balance Due:", "Rs.0.00"],
    ]
    t_pay = Table(
        [[Paragraph(c, styles["Normal"]) if "<b>" in c else c for c in row] for row in pay_data],
        colWidths=[38 * mm, 44 * mm],
    )
    t_pay.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#475569")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))

    # Determine summary breakdown from stored immutable fields
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
            tax_data = [
                ["<b>TAX BREAKUP</b>", "Rate", "Amount"],
                ["Taxable Value", "—", f"Rs.{taxable_rupees:,.2f}"],
                ["CGST", f"{cgst_pct}%", f"Rs.{cgst_rupees:,.2f}"],
                ["SGST", f"{sgst_pct}%", f"Rs.{sgst_rupees:,.2f}"],
                ["IGST", "0%", "Rs.0.00"],
                ["Total GST", "18%", f"Rs.{total_gst_rupees:,.2f}"],
                ["Grand Total (Paid)", "—", f"Rs.{amount_rupees:,.2f}"],
            ]
        else:
            # Inter-State Supply (Rajasthan -> Outside Rajasthan)
            igst_pct = int(record.get("igst_rate", IGST_RATE) * 100)
            tax_data = [
                ["<b>TAX BREAKUP</b>", "Rate", "Amount"],
                ["Taxable Value", "—", f"Rs.{taxable_rupees:,.2f}"],
                ["CGST", "0%", "Rs.0.00"],
                ["SGST", "0%", "Rs.0.00"],
                ["IGST", f"{igst_pct}%", f"Rs.{igst_rupees:,.2f}"],
                ["Total GST", "18%", f"Rs.{total_gst_rupees:,.2f}"],
                ["Grand Total (Paid)", "—", f"Rs.{amount_rupees:,.2f}"],
            ]
    else:
        # Legacy fallback for historical invoices generated without state breakdown
        base_amount = amount_rupees / (1 + GST_RATE)
        gst_amount = amount_rupees - base_amount
        tax_data = [
            ["<b>TAX BREAKUP</b>", "Rate", "Amount"],
            ["Taxable Value", "—", f"Rs.{base_amount:,.2f}"],
            ["GST", f"{int(GST_RATE * 100)}%", f"Rs.{gst_amount:,.2f}"],
            ["Grand Total (Paid)", "—", f"Rs.{amount_rupees:,.2f}"],
        ]

    t_tax = Table(
        [[Paragraph(c, styles["Normal"]) if "<b>" in c else c for c in row] for row in tax_data],
        colWidths=[44 * mm, 20 * mm, 28 * mm],
    )
    t_tax.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#0f172a")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))

    split_table = Table([[t_pay, t_tax]], colWidths=[85 * mm, 95 * mm])
    split_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(split_table)
    elements.append(Spacer(1, 10 * mm))

    # 5. FOOTER
    footer_lines = [
        "This is a system-generated tax invoice and does not require a physical signature.",
        "For billing support: support@letatec.com",
    ]
    elements.append(Paragraph("<br/>".join(footer_lines), styles["FooterText"]))

    doc.build(elements)
    return buf.getvalue()
