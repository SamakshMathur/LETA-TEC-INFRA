"""
Authoritative deterministic GST calculation engine for LETATEC.

Business Logic & Pricing Contract:
----------------------------------
1. The customer-facing plan amount charged by Razorpay is GST-INCLUSIVE.
   Grand Total (Paise) = actual charged amount.

2. Taxable Base Amount:
   Taxable Amount (Paise) = round_half_up(Grand Total / (1 + GST_RATE))
   Total GST (Paise) = Grand Total - Taxable Base Amount

3. Rounding & Reconciliation Policy (Approach B):
   - In GST-inclusive reverse calculations, Total GST is first derived from the
     inclusive Grand Total to guarantee: Taxable + Total GST == Grand Total.
   - For Inter-State supply (IGST 18%):
       IGST = Total GST
       CGST = 0
       SGST = 0
   - For Intra-State supply (CGST 9% + SGST 9%):
       Total GST is allocated 50/50 between Central and State governments.
       When Total GST in paise is an odd integer (e.g. 153 paise on ₹10.00),
       it cannot be split into identical integer halves without a 1-paise remainder.
       The deterministic 1-paise reconciliation policy allocates:
         CGST (Paise) = (Total GST + 1) // 2
         SGST (Paise) = Total GST - CGST
       This prevents independent rounding mismatch (which would produce ₹9.99
       instead of ₹10.00) and guarantees that:
         Taxable + CGST + SGST == Grand Total
         CGST + SGST == Total GST

4. Invariants Guaranteed across all price points:
   - taxable_amount + total_gst == grand_total
   - intra-state: cgst_amount + sgst_amount == total_gst and igst_amount == 0
   - inter-state: igst_amount == total_gst and cgst_amount == 0 and sgst_amount == 0
   - never non-zero CGST + SGST + IGST simultaneously
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict


# ── Authoritative Business & Tax Constants ─────────────────────────────────────
# Note: Tax rates and place-of-supply classifications represent software
# configurations for LETATEC digital services subject to business/accounting validation.
COMPANY_NAME = "LETATEC AI TECHNOLOGIES PRIVATE LIMITED"
COMPANY_GSTIN = "08AAGCL9166P1ZL"
COMPANY_CIN = "U62010RJ2026PTC114803"

SUPPLIER_STATE_CODE = "08"
SUPPLIER_STATE_NAME = "Rajasthan"

GST_RATE = 0.18        # Configured standard 18% GST for digital services
CGST_RATE = 0.09       # 9% Central GST
SGST_RATE = 0.09       # 9% State GST
IGST_RATE = 0.18       # 18% Integrated GST


# ── Official Indian State / UT 2-Digit GST Codes ──────────────────────────────
INDIAN_GST_STATES: Dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}

# Inverted mapping: normalized lowercase state name -> 2-digit code
_STATE_NAME_TO_CODE: Dict[str, str] = {
    name.lower().replace(" and ", " & "): code
    for code, name in INDIAN_GST_STATES.items()
}
# Standard aliases
_STATE_NAME_TO_CODE.update({
    "jammu & kashmir": "01",
    "j&k": "01",
    "daman & diu": "26",
    "dadra & nagar haveli": "26",
    "andaman & nicobar": "35",
    "delhi ncr": "07",
    "nct of delhi": "07",
    "orissa": "21",
    "pondicherry": "34",
    "rajasthan": "08",
})


@dataclass(frozen=True)
class TaxBreakdown:
    grand_total_paise: int
    taxable_amount_paise: int
    total_gst_paise: int
    cgst_rate: float
    cgst_amount_paise: int
    sgst_rate: float
    sgst_amount_paise: int
    igst_rate: float
    igst_amount_paise: int
    is_inter_state: Optional[bool]
    supplier_state_code: str
    supplier_state_name: str
    customer_state_code: Optional[str]
    customer_state_name: Optional[str]
    place_of_supply: Optional[str]


def resolve_place_of_supply(
    state: Optional[str] = None,
    state_code: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    Deterministically resolves Indian state name and 2-digit GST code.
    Returns dict with state_code, state_name, and place_of_supply (e.g. '08-Rajasthan').
    Never guesses based on IP, phone number, or heuristics.
    Returns None if state cannot be identified.
    """
    if state_code:
        cleaned_code = str(state_code).strip().zfill(2)
        if cleaned_code in INDIAN_GST_STATES:
            name = INDIAN_GST_STATES[cleaned_code]
            return {
                "state_code": cleaned_code,
                "state_name": name,
                "place_of_supply": f"{cleaned_code}-{name}",
            }

    if state:
        cleaned_state = str(state).strip()
        if cleaned_state.isdigit() and len(cleaned_state) <= 2:
            code = cleaned_state.zfill(2)
            if code in INDIAN_GST_STATES:
                name = INDIAN_GST_STATES[code]
                return {
                    "state_code": code,
                    "state_name": name,
                    "place_of_supply": f"{code}-{name}",
                }

        norm = cleaned_state.lower().replace(" and ", " & ")
        if norm in _STATE_NAME_TO_CODE:
            code = _STATE_NAME_TO_CODE[norm]
            name = INDIAN_GST_STATES[code]
            return {
                "state_code": code,
                "state_name": name,
                "place_of_supply": f"{code}-{name}",
            }

        for code, name in INDIAN_GST_STATES.items():
            if norm == name.lower():
                return {
                    "state_code": code,
                    "state_name": name,
                    "place_of_supply": f"{code}-{name}",
                }

    return None


def calculate_gst(
    amount_paise: int,
    customer_state: Optional[str] = None,
    customer_state_code: Optional[str] = None,
) -> TaxBreakdown:
    """
    Deterministic GST calculation for a given charged amount in paise.

    Parameters:
      amount_paise: Total amount charged to the customer (inclusive of GST).
      customer_state: Optional state name (e.g. 'Rajasthan', 'Maharashtra').
      customer_state_code: Optional 2-digit GST state code (e.g. '08', '27').

    Returns:
      TaxBreakdown dataclass with exact integer-paise tax components.
    """
    if amount_paise < 0:
        raise ValueError(f"amount_paise must be non-negative, got {amount_paise}")

    pos_info = resolve_place_of_supply(state=customer_state, state_code=customer_state_code)

    grand_total_paise = int(amount_paise)
    # Taxable amount reverse-calculated: round_half_up(Grand Total / 1.18)
    taxable_dec = (Decimal(grand_total_paise) / Decimal("1.18")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    taxable_amount_paise = int(taxable_dec)
    total_gst_paise = grand_total_paise - taxable_amount_paise

    if pos_info is not None:
        cust_code = pos_info["state_code"]
        cust_name = pos_info["state_name"]
        pos_str = pos_info["place_of_supply"]

        if cust_code == SUPPLIER_STATE_CODE:
            # Intra-State Supply (Rajasthan -> Rajasthan)
            is_inter_state = False
            cgst_rate = CGST_RATE
            sgst_rate = SGST_RATE
            igst_rate = 0.0

            # Deterministic 1-paise reconciliation: allocate remainder to CGST
            cgst_amount_paise = (total_gst_paise + 1) // 2
            sgst_amount_paise = total_gst_paise - cgst_amount_paise
            igst_amount_paise = 0
        else:
            # Inter-State Supply (Rajasthan -> Outside Rajasthan)
            is_inter_state = True
            cgst_rate = 0.0
            sgst_rate = 0.0
            igst_rate = IGST_RATE

            cgst_amount_paise = 0
            sgst_amount_paise = 0
            igst_amount_paise = total_gst_paise
    else:
        is_inter_state = None
        cust_code = None
        cust_name = None
        pos_str = None
        cgst_rate = 0.0
        sgst_rate = 0.0
        igst_rate = 0.0
        cgst_amount_paise = 0
        sgst_amount_paise = 0
        igst_amount_paise = 0

    # Strict Invariant Verification
    assert taxable_amount_paise + total_gst_paise == grand_total_paise, (
        f"Reconciliation error: {taxable_amount_paise} + {total_gst_paise} != {grand_total_paise}"
    )

    if is_inter_state is False:
        assert cgst_amount_paise + sgst_amount_paise == total_gst_paise, "Intra-state GST mismatch"
        assert igst_amount_paise == 0, "Intra-state IGST must be 0"
    elif is_inter_state is True:
        assert igst_amount_paise == total_gst_paise, "Inter-state IGST mismatch"
        assert cgst_amount_paise == 0 and sgst_amount_paise == 0, "Inter-state CGST/SGST must be 0"

    assert not (cgst_amount_paise > 0 and sgst_amount_paise > 0 and igst_amount_paise > 0), (
        "Fatal tax error: CGST, SGST, and IGST cannot all be non-zero simultaneously"
    )

    return TaxBreakdown(
        grand_total_paise=grand_total_paise,
        taxable_amount_paise=taxable_amount_paise,
        total_gst_paise=total_gst_paise,
        cgst_rate=cgst_rate,
        cgst_amount_paise=cgst_amount_paise,
        sgst_rate=sgst_rate,
        sgst_amount_paise=sgst_amount_paise,
        igst_rate=igst_rate,
        igst_amount_paise=igst_amount_paise,
        is_inter_state=is_inter_state,
        supplier_state_code=SUPPLIER_STATE_CODE,
        supplier_state_name=SUPPLIER_STATE_NAME,
        customer_state_code=cust_code,
        customer_state_name=cust_name,
        place_of_supply=pos_str,
    )
