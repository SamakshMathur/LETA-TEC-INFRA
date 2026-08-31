"""
LETA Calculation Engine — Stage 5A of TITAN architecture.

Deterministic GST computation for Rule 42/43, Section 50 interest,
and basic GST liability. The LLM explains; this engine computes.

Keeps all arithmetic out of the LLM to eliminate hallucinated figures
and remove thousands of thinking-tokens from the generation budget.
"""
import re
import datetime
import calendar
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class CalculationResult:
    applicable: bool
    formula: str
    computation: str
    result_text: str
    statutory_ref: str


# ─── Amount / rate extractors ─────────────────────────────────────────────────

def _extract_amount(text: str) -> Optional[float]:
    """Pull the first monetary value from query text."""
    text_l = text.lower()
    patterns = [
        r'(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|lakhs|crore|crores)?',
        r'([\d,]+(?:\.\d+)?)\s+(?:lakh|lakhs|crore|crores)',
        r'(?:itc|credit|amount|tax)\s+(?:of\s+)?(?:rs\.?|inr|₹)?\s*([\d,]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text_l)
        if m:
            raw = m.group(1).replace(',', '')
            try:
                val = float(raw)
            except ValueError:
                continue
            if 'crore' in text_l:
                val *= 10_000_000
            elif 'lakh' in text_l:
                val *= 100_000
            return val
    return None


def _extract_percentage(text: str) -> Optional[float]:
    """Pull the first percentage value from query text."""
    m = re.search(r'([\d.]+)\s*%', text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _extract_days(text: str) -> Optional[int]:
    m = re.search(r'(\d+)\s+days?', text.lower())
    if m:
        return int(m.group(1))
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def detect_and_calculate(query: str) -> Optional[CalculationResult]:
    """
    Inspect the query for computable GST patterns and return a pre-computed
    result block. Returns None when no computation applies.
    """
    q = query.lower()

    if re.search(r'rule\s*42|itc.*revers|revers.*itc|common.*input.*service|exempt.*turnover.*itc', q):
        return _rule42(query)

    if re.search(r'rule\s*43|capital\s+goods.*itc|itc.*capital\s+goods|cg.*itc', q):
        return _rule43(query)

    if re.search(r'(?:sec(?:tion)?\.?\s*50|interest.*gst|gst.*interest|delayed\s+payment|interest.*delay)', q):
        return _section50(query)

    if re.search(r'(?:calculate|compute|how\s+much)\s+(?:gst|igst|cgst|sgst|tax)', q):
        return _gst_amount(query)

    return None


def format_for_context(result: CalculationResult) -> str:
    """Render a CalculationResult as a pre-computed facts block for the LLM context."""
    return (
        "\n╔══════════════════════════════════════════╗\n"
        "║   PRE-COMPUTED STATUTORY CALCULATION     ║\n"
        "╚══════════════════════════════════════════╝\n"
        f"Statutory Reference: {result.statutory_ref}\n"
        f"Formula: {result.formula}\n"
        f"Computation:\n{result.computation}\n"
        f"Engine Result: {result.result_text}\n"
        "INSTRUCTION: Use these values verbatim. Do NOT recalculate independently.\n"
    )


# ─── Individual calculators ───────────────────────────────────────────────────

def _rule42(query: str) -> CalculationResult:
    itc = _extract_amount(query)
    exempt_pct = _extract_percentage(query)

    formula = (
        "Rule 42 Monthly Reversal = ITC on common inputs/services "
        "× (Exempt + Non-business Turnover) ÷ Total Turnover\n"
        "Annual reconciliation required under Rule 42(2)."
    )

    if itc and exempt_pct:
        reversal = round(itc * exempt_pct / 100.0, 2)
        computation = (
            f"  Total ITC on common inputs: ₹{itc:,.2f}\n"
            f"  Exempt turnover ratio used: {exempt_pct}%\n"
            f"  Monthly provisional reversal: ₹{reversal:,.2f}\n"
            f"  Annual provisional reversal (×12): ₹{reversal * 12:,.2f}"
        )
        result_text = (
            f"Monthly reversal ≈ ₹{reversal:,.2f}. "
            "Subject to annual reconciliation — compare cumulative provisional "
            "reversals to final annual calculation at year-end."
        )
    else:
        computation = "  (Insufficient numerical data in query — formula guidance only)"
        result_text = (
            "Rule 42 applies to ITC on inputs/services used for taxable + exempt/non-business "
            "supplies. Monthly provisional reversal; annual reconciliation mandatory."
        )

    return CalculationResult(
        applicable=True,
        formula=formula,
        computation=computation,
        result_text=result_text,
        statutory_ref="Rule 42, CGST Rules 2017 | Section 17(3), CGST Act 2017",
    )


def _rule43(query: str) -> CalculationResult:
    itc = _extract_amount(query)
    exempt_pct = _extract_percentage(query)

    formula = (
        "Rule 43 Monthly Reversal = (ITC on Capital Goods ÷ 60) "
        "× (Exempt Turnover ÷ Total Turnover)\n"
        "Useful life of capital goods = 60 months (5 years)."
    )

    if itc and exempt_pct:
        monthly_spread = round(itc / 60.0, 2)
        monthly_reversal = round(monthly_spread * exempt_pct / 100.0, 2)
        computation = (
            f"  Total ITC on capital goods: ₹{itc:,.2f}\n"
            f"  Monthly spread (÷60 months): ₹{monthly_spread:,.2f}\n"
            f"  Exempt turnover ratio: {exempt_pct}%\n"
            f"  Monthly reversal: ₹{monthly_reversal:,.2f}\n"
            f"  Annual reversal (×12): ₹{monthly_reversal * 12:,.2f}"
        )
        result_text = (
            f"Monthly reversal ≈ ₹{monthly_reversal:,.2f}, "
            f"annual ≈ ₹{monthly_reversal * 12:,.2f}. "
            "Annual reconciliation under Rule 43(2) required."
        )
    else:
        computation = "  (Insufficient numerical data in query — formula guidance only)"
        result_text = (
            "Rule 43: ITC on capital goods used for taxable + exempt supplies "
            "must be reversed monthly over 60-month useful life."
        )

    return CalculationResult(
        applicable=True,
        formula=formula,
        computation=computation,
        result_text=result_text,
        statutory_ref="Rule 43, CGST Rules 2017 | Section 17(3), CGST Act 2017",
    )


def _section50(query: str) -> CalculationResult:
    amount = _extract_amount(query)
    days = _extract_days(query)

    formula = (
        "Section 50 Interest = Tax Amount × (Rate ÷ 100) ÷ 365 × Days\n"
        "Rate: 18% p.a. for delayed payment | 24% p.a. for wrongful ITC utilisation\n"
        "Ref: Notification 13/2017-CT (as amended)"
    )

    if amount and days:
        i18 = round(amount * 0.18 / 365 * days, 2)
        i24 = round(amount * 0.24 / 365 * days, 2)
        computation = (
            f"  Principal tax: ₹{amount:,.2f}\n"
            f"  Delay: {days} days\n"
            f"  Interest @ 18% p.a.: ₹{i18:,.2f}\n"
            f"  Interest @ 24% p.a. (wrongful ITC): ₹{i24:,.2f}"
        )
        result_text = (
            f"Interest = ₹{i18:,.2f} (@ 18%) or ₹{i24:,.2f} (@ 24% if wrongful ITC). "
            "Confirm applicable rate from demand notice."
        )
    elif amount:
        i18_daily = round(amount * 0.18 / 365, 2)
        computation = (
            f"  Principal tax: ₹{amount:,.2f}\n"
            f"  Daily interest @ 18%: ₹{i18_daily:,.2f}\n"
            f"  Daily interest @ 24%: ₹{round(amount * 0.24 / 365, 2):,.2f}\n"
            "  (Provide delay in days for total interest)"
        )
        result_text = (
            f"Daily interest: ₹{i18_daily:,.2f} (@ 18%) on ₹{amount:,.2f}. "
            "Multiply by number of delayed days for total."
        )
    else:
        computation = "  (Provide tax amount and delay period for exact computation)"
        result_text = "Sec 50: 18% p.a. for delayed payment; 24% p.a. for wrongful ITC utilisation."

    return CalculationResult(
        applicable=True,
        formula=formula,
        computation=computation,
        result_text=result_text,
        statutory_ref="Section 50, CGST Act 2017 | Notification 13/2017-CT (as amended)",
    )


def _gst_amount(query: str) -> CalculationResult:
    amount = _extract_amount(query)

    # Detect rate from query text
    rate: Optional[float] = _extract_percentage(query)
    if rate is None:
        for r in [28.0, 18.0, 12.0, 5.0, 3.0, 0.25]:
            if str(int(r)) in query or str(r) in query:
                rate = r
                break

    formula = (
        "GST Liability = Taxable Value × GST Rate%\n"
        "For intra-state: CGST = Rate/2 | SGST = Rate/2\n"
        "For inter-state: IGST = Full Rate"
    )

    if amount and rate:
        gst = round(amount * rate / 100.0, 2)
        half = round(gst / 2.0, 2)
        total = round(amount + gst, 2)
        computation = (
            f"  Taxable value: ₹{amount:,.2f}\n"
            f"  GST @ {rate}%: ₹{gst:,.2f}\n"
            f"    Intra-state — CGST ({rate/2}%): ₹{half:,.2f} | SGST ({rate/2}%): ₹{half:,.2f}\n"
            f"    Inter-state — IGST ({rate}%): ₹{gst:,.2f}\n"
            f"  Total invoice value: ₹{total:,.2f}"
        )
        result_text = (
            f"GST = ₹{gst:,.2f} on ₹{amount:,.2f} @ {rate}%. "
            f"Total invoice value = ₹{total:,.2f}."
        )
    else:
        computation = "  (Provide taxable amount and GST rate for exact computation)"
        result_text = "GST = Taxable Value × Applicable Rate under CGST Act / IGST Act."

    return CalculationResult(
        applicable=True,
        formula=formula,
        computation=computation,
        result_text=result_text,
        statutory_ref="Section 9, CGST Act 2017 | Section 5, IGST Act 2017",
    )


# ─── Generic Date & Duration Math Engine (Phase 13) ───────────────────────────

def add_months(base_date: datetime.date, n: int) -> datetime.date:
    month = base_date.month - 1 + n
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def add_years(base_date: datetime.date, n: int) -> datetime.date:
    try:
        return base_date.replace(year=base_date.year + n)
    except ValueError:
        return datetime.date(base_date.year + n, 2, 28)


def add_days(base_date: datetime.date, n: int) -> datetime.date:
    return base_date + datetime.timedelta(days=n)


def parse_date(date_str: str) -> Optional[datetime.date]:
    date_str = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def execute_structured_calculation(calc_req: dict, chunks: list) -> dict:
    """
    Executes a structured calculation request, verifying inputs verbatim in source text.
    """
    base_src_id = calc_req.get("base_src")
    base_val = calc_req.get("base")
    if not base_val or not base_src_id:
        return {"status": "INVALID_REQUEST", "error": "Missing base date or source ID"}

    try:
        idx = int(base_src_id.replace("SRC-", "")) - 1
        base_chunk = chunks[idx] if 0 <= idx < len(chunks) else None
    except (ValueError, TypeError):
        base_chunk = None

    if not base_chunk:
        return {"status": "DERIVATION_UNSUPPORTED", "error": f"Source {base_src_id} not found in context"}

    chunk_text = base_chunk.get("text", "").lower()
    meta = base_chunk.get("metadata", {})

    # Check if base date exists verbatim in chunk text or metadata
    found_base = base_val.lower() in chunk_text
    if not found_base:
        meta_values = [str(v).lower() for v in meta.values()]
        if any(base_val.lower() in mv for mv in meta_values):
            found_base = True

    if not found_base:
        return {"status": "DERIVATION_UNSUPPORTED", "error": f"Base date '{base_val}' not found in source {base_src_id}"}

    rule_src_id = calc_req.get("rule_src")
    offset_val = calc_req.get("offset")
    unit_val = calc_req.get("unit", "months")
    rule_name = calc_req.get("rule", "")

    try:
        rid = int(rule_src_id.replace("SRC-", "")) - 1
        rule_chunk = chunks[rid] if 0 <= rid < len(chunks) else None
    except (ValueError, TypeError):
        rule_chunk = None

    if not rule_chunk:
        return {"status": "DERIVATION_UNSUPPORTED", "error": f"Rule source {rule_src_id} not found in context"}

    rule_text = rule_chunk.get("text", "").lower()
    found_rule = rule_name.lower() in rule_text or rule_name.lower() in str(rule_chunk.get("metadata", {})).lower()

    if not found_rule:
        return {"status": "DERIVATION_UNSUPPORTED", "error": f"Rule '{rule_name}' not found in source {rule_src_id}"}

    op_type = calc_req.get("type")
    if op_type == "date_offset":
        parsed_base = parse_date(base_val)
        if not parsed_base:
            return {"status": "CALCULATION_ERROR", "error": f"Unparseable base date '{base_val}'"}

        try:
            offset_int = int(offset_val)
        except (ValueError, TypeError):
            return {"status": "CALCULATION_ERROR", "error": f"Unparseable offset '{offset_val}'"}

        try:
            if unit_val == "months":
                res_date = add_months(parsed_base, offset_int)
            elif unit_val == "years":
                res_date = add_years(parsed_base, offset_int)
            elif unit_val == "days":
                res_date = add_days(parsed_base, offset_int)
            else:
                return {"status": "CALCULATION_ERROR", "error": f"Unsupported unit '{unit_val}'"}

            res_str = res_date.strftime("%d-%m-%Y")
            return {
                "status": "DERIVED_SUPPORTED",
                "value": res_str,
                "provenance": {
                    "base": base_val,
                    "operation": f"{offset_val} {unit_val}",
                    "base_source": base_src_id,
                    "rule_source": rule_src_id,
                    "rule": rule_name
                }
            }
        except Exception as e:
            return {"status": "CALCULATION_ERROR", "error": f"Calculation error: {e}"}

    return {"status": "INVALID_REQUEST", "error": f"Unsupported operation type '{op_type}'"}


def process_internal_calculations(text: str, chunks: list) -> Tuple[str, List[dict]]:
    """
    Parses and extracts all <calculate> tags from the text, runs them through the verifier,
    registers the outputs, and strips the tags from the final user-facing text.
    """
    calculated_claims = []
    pattern = r'<calculate\s+([^>]+?)\s*/?>'

    def replace_tag(match):
        attr_str = match.group(1)
        attribs = dict(re.findall(r'(\w+)="([^"]*)"', attr_str))
        if attribs:
            res = execute_structured_calculation(attribs, chunks)
            if res.get("status") == "DERIVED_SUPPORTED":
                calculated_claims.append(res)
                return res["value"]
            else:
                return f"[Calculation Error: {res.get('error')}]"
        return ""

    cleaned_text = re.sub(pattern, replace_tag, text)
    return cleaned_text, calculated_claims
