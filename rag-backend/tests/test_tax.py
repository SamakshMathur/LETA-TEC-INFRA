"""
Tests for deterministic GST calculation and place-of-supply resolution (app/services/tax.py).
"""
import pytest
from app.services.tax import (
    calculate_gst,
    resolve_place_of_supply,
    SUPPLIER_STATE_CODE,
    SUPPLIER_STATE_NAME,
    GST_RATE,
    CGST_RATE,
    SGST_RATE,
    IGST_RATE,
)


def test_rajasthan_intra_state_gst_breakdown_with_odd_paise():
    """
    1. Rajasthan customer (intra-State) with odd-paise Total GST:
       Grand Total: ₹10.00 (1000 paise).
       Taxable = round_half_up(1000 / 1.18) = 847 paise (₹8.47).
       Total GST = 1000 - 847 = 153 paise (₹1.53, odd).
       Under Approach B (deterministic 1-paise allocation policy):
         CGST (9%) = (153 + 1) // 2 = 77 paise (₹0.77).
         SGST (9%) = 153 - 77 = 76 paise (₹0.76).
         IGST (0%) = 0 paise (₹0.00).
       Reconciled Invariants:
         847 + 77 + 76 == 1000 (₹8.47 + ₹0.77 + ₹0.76 == ₹10.00)
         77 + 76 == 153 (₹0.77 + ₹0.76 == ₹1.53)
    """
    tax = calculate_gst(1000, customer_state="Rajasthan", customer_state_code="08")
    assert tax.grand_total_paise == 1000
    assert tax.taxable_amount_paise == 847
    assert tax.total_gst_paise == 153
    assert tax.cgst_rate == 0.09
    assert tax.cgst_amount_paise == 77
    assert tax.sgst_rate == 0.09
    assert tax.sgst_amount_paise == 76
    assert tax.igst_rate == 0.0
    assert tax.igst_amount_paise == 0
    assert tax.is_inter_state is False
    assert tax.place_of_supply == "08-Rajasthan"
    assert tax.customer_state_code == "08"
    assert tax.customer_state_name == "Rajasthan"

    # Strict reconciliation
    assert tax.taxable_amount_paise + tax.cgst_amount_paise + tax.sgst_amount_paise == tax.grand_total_paise
    assert tax.cgst_amount_paise + tax.sgst_amount_paise == tax.total_gst_paise


def test_non_rajasthan_inter_state_gst_breakdown():
    """
    2. Non-Rajasthan customer (inter-State, e.g., Maharashtra):
       Charges: Actual charged amount in paise (e.g., 1000 paise = ₹10.00).
       Taxable = 847 paise (₹8.47).
       Total GST = 153 paise (₹1.53).
       CGST (0%) = 0.
       SGST (0%) = 0.
       IGST (18%) = 153 paise (₹1.53).
    """
    tax = calculate_gst(1000, customer_state="Maharashtra", customer_state_code="27")
    assert tax.grand_total_paise == 1000
    assert tax.taxable_amount_paise == 847
    assert tax.total_gst_paise == 153
    assert tax.cgst_rate == 0.0
    assert tax.cgst_amount_paise == 0
    assert tax.sgst_rate == 0.0
    assert tax.sgst_amount_paise == 0
    assert tax.igst_rate == 0.18
    assert tax.igst_amount_paise == 153
    assert tax.is_inter_state is True
    assert tax.place_of_supply == "27-Maharashtra"
    assert tax.customer_state_code == "27"
    assert tax.customer_state_name == "Maharashtra"

    # Reconciliation
    assert tax.taxable_amount_paise + tax.total_gst_paise == tax.grand_total_paise
    assert tax.igst_amount_paise == tax.total_gst_paise


def test_multiple_real_plan_prices_and_dynamic_calculation():
    """
    3. Multiple real module/plan prices with even and odd GST remainders:
       - ₹10 (1000p): Taxable 847p (₹8.47), GST 153p (₹1.53).
         Rajasthan: CGST 77p + SGST 76p = 153p. Total 1000p.
       - ₹55 (5500p): Taxable 4661p (₹46.61), GST 839p (₹8.39).
         Rajasthan: CGST 420p + SGST 419p = 839p. Total 5500p.
       - ₹77 (7700p): Taxable 6525p (₹65.25), GST 1175p (₹11.75).
         Rajasthan: CGST 588p + SGST 587p = 1175p. Total 7700p.
       - ₹115 (11500p): Taxable 9746p (₹97.46), GST 1754p (₹17.54).
         Rajasthan: CGST 877p + SGST 877p = 1754p. Total 11500p.
       - ₹199 (19900p): Taxable 16864p (₹168.64), GST 3036p (₹30.36).
         Rajasthan: CGST 1518p + SGST 1518p. Outside: IGST 3036p.
       - ₹399 (39900p): Taxable 33814p (₹338.14), GST 6086p (₹60.86).
         Rajasthan: CGST 3043p + SGST 3043p. Outside: IGST 6086p.
       - ₹499 (49900p): Taxable 42288p (₹422.88), GST 7612p (₹76.12).
         Rajasthan: CGST 3806p + SGST 3806p. Outside: IGST 7612p.
       - ₹735 (73500p): Taxable 62288p (₹622.88), GST 11212p (₹112.12).
         Rajasthan: CGST 5606p + SGST 5606p. Outside: IGST 11212p.
       - ₹999 (99900p), ₹1499 (149900p).
    """
    cases = [
        (1000, 847, 153, 77, 76),       # ₹10 (odd GST)
        (5500, 4661, 839, 420, 419),    # ₹55 (odd GST)
        (7700, 6525, 1175, 588, 587),   # ₹77 (odd GST)
        (11500, 9746, 1754, 877, 877),  # ₹115 (even GST)
        (19900, 16864, 3036, 1518, 1518), # ₹199 (even GST)
        (39900, 33814, 6086, 3043, 3043), # ₹399 (even GST)
        (49900, 42288, 7612, 3806, 3806), # ₹499 (even GST)
        (73500, 62288, 11212, 5606, 5606), # ₹735 (even GST)
        (99900, 84661, 15239, 7620, 7619), # ₹999 (odd GST)
        (149900, 127034, 22866, 11433, 11433), # ₹1499 (even GST)
    ]

    for grand, exp_tax, exp_gst, exp_cgst, exp_sgst in cases:
        # Intra-state
        rj = calculate_gst(grand, customer_state="Rajasthan")
        assert rj.taxable_amount_paise == exp_tax
        assert rj.total_gst_paise == exp_gst
        assert rj.cgst_amount_paise == exp_cgst
        assert rj.sgst_amount_paise == exp_sgst
        assert rj.igst_amount_paise == 0
        assert rj.taxable_amount_paise + rj.cgst_amount_paise + rj.sgst_amount_paise == grand
        assert rj.cgst_amount_paise + rj.sgst_amount_paise == exp_gst

        # Inter-state
        out = calculate_gst(grand, customer_state="Delhi")
        assert out.taxable_amount_paise == exp_tax
        assert out.total_gst_paise == exp_gst
        assert out.cgst_amount_paise == 0
        assert out.sgst_amount_paise == 0
        assert out.igst_amount_paise == exp_gst
        assert out.taxable_amount_paise + out.igst_amount_paise == grand


def test_exhaustive_rounding_and_paise_reconciliation():
    """
    4. Genuinely exhaustive rounding and paise reconciliation:
       Sweeps every integer amount from 1 to 100,000 paise (₹0.01 to ₹1,000.00)
       for both Intra-State (Rajasthan) and Inter-State supplies.

       Verifies across all 200,000 cases:
       - taxable_amount + total_gst == grand_total (zero paise drift)
       - intra-state: cgst + sgst == total_gst and igst == 0
       - inter-state: igst == total_gst and cgst == 0 and sgst == 0
       - non-zero CGST, SGST, and IGST never exist simultaneously
    """
    for amt in range(1, 100001):
        # Intra-state (Rajasthan)
        intra = calculate_gst(amt, customer_state_code="08")
        assert intra.taxable_amount_paise + intra.total_gst_paise == amt
        assert intra.cgst_amount_paise + intra.sgst_amount_paise == intra.total_gst_paise
        assert intra.igst_amount_paise == 0
        assert not (intra.cgst_amount_paise > 0 and intra.sgst_amount_paise > 0 and intra.igst_amount_paise > 0)

        # Inter-state (e.g. Maharashtra)
        inter = calculate_gst(amt, customer_state_code="27")
        assert inter.taxable_amount_paise + inter.total_gst_paise == amt
        assert inter.igst_amount_paise == inter.total_gst_paise
        assert inter.cgst_amount_paise == 0
        assert inter.sgst_amount_paise == 0
        assert not (inter.cgst_amount_paise > 0 and inter.sgst_amount_paise > 0 and inter.igst_amount_paise > 0)


def test_missing_customer_state_handling():
    """
    5. Missing customer state / place-of-supply:
       Must fail safely into unclassified mode without guessing from IP, phone, or location.
    """
    tax = calculate_gst(1000, customer_state=None, customer_state_code=None)
    assert tax.grand_total_paise == 1000
    assert tax.taxable_amount_paise == 847
    assert tax.total_gst_paise == 153
    assert tax.is_inter_state is None
    assert tax.place_of_supply is None
    assert tax.customer_state_code is None
    assert tax.customer_state_name is None
    assert tax.cgst_amount_paise == 0
    assert tax.sgst_amount_paise == 0
    assert tax.igst_amount_paise == 0


def test_invalid_state_value_handling():
    """
    6. Invalid state value:
       Resolves to None safely without crashing or inventing a state.
    """
    assert resolve_place_of_supply(state="Atlantis") is None
    assert resolve_place_of_supply(state_code="999") is None
    assert resolve_place_of_supply(state="", state_code="") is None

    tax = calculate_gst(1000, customer_state="NonExistentState123", customer_state_code="99")
    assert tax.is_inter_state is None
    assert tax.place_of_supply is None


def test_never_charge_cgst_sgst_and_igst_simultaneously():
    """
    12. Ensure no code path can produce non-zero CGST + non-zero SGST + non-zero IGST simultaneously.
    """
    for state in ["Rajasthan", "Maharashtra", "08", "27", "07", None, "Invalid"]:
        tax = calculate_gst(1000, customer_state=state)
        non_zero_count = sum([
            tax.cgst_amount_paise > 0,
            tax.sgst_amount_paise > 0,
            tax.igst_amount_paise > 0,
        ])
        assert not (tax.cgst_amount_paise > 0 and tax.sgst_amount_paise > 0 and tax.igst_amount_paise > 0)
        assert non_zero_count in (0, 1, 2)
        if tax.igst_amount_paise > 0:
            assert tax.cgst_amount_paise == 0 and tax.sgst_amount_paise == 0


def test_validate_gstin_structure_valid_cases():
    """Verify structural validation passes for standard 15-character Indian GSTINs."""
    from app.services.tax import validate_gstin_structure

    valid_gstins = [
        ("08AAGCL9166P1ZL", "08"),  # Rajasthan (Company GSTIN)
        ("27ABCDE1234F1Z5", "27"),  # Maharashtra
        ("29ABCDE1234F1Z5", "29"),  # Karnataka
        ("07AAAAA0000A1Z5", "07"),  # Delhi
        (" 08AAGCL9166P1ZL ", "08"),  # Leading/trailing whitespace trimmed
    ]
    for gstin, expected_state in valid_gstins:
        is_valid, state_code, err = validate_gstin_structure(gstin)
        assert is_valid is True, f"Failed for valid GSTIN {gstin}: {err}"
        assert state_code == expected_state
        assert err is None


def test_validate_gstin_structure_invalid_cases():
    """Verify structural validation rejects malformed GSTINs without claiming checksum verification."""
    from app.services.tax import validate_gstin_structure

    # 1. Length violations
    assert validate_gstin_structure("08AAGCL9166P1Z")[0] is False  # 14 chars
    assert validate_gstin_structure("08AAGCL9166P1ZL9")[0] is False  # 16 chars

    # 2. None / Empty
    assert validate_gstin_structure(None)[0] is False
    assert validate_gstin_structure("")[0] is False
    assert validate_gstin_structure("   ")[0] is False

    # 3. Invalid character structure
    assert validate_gstin_structure("XXAAGCL9166P1ZL")[0] is False  # Alphabetic state code
    assert validate_gstin_structure("081234L9166P1ZL")[0] is False  # Digits instead of PAN alpha
    assert validate_gstin_structure("08AAGCL9166P1!L")[0] is False  # Special characters

    # 4. Unrecognized Indian state code
    is_valid, state_code, err = validate_gstin_structure("99AAGCL9166P1ZL")
    assert is_valid is False
    assert state_code == "99"
    assert "not a recognized Indian GST state" in err


def test_get_financial_year_boundaries():
    """Verify Indian financial year (Apr 1 to Mar 31) boundary calculations."""
    from datetime import datetime, timezone
    from app.services.tax import get_financial_year

    # April 1st (Start of FY)
    assert get_financial_year(datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)) == "2026-27"
    # Mid FY (September)
    assert get_financial_year(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)) == "2026-27"
    # End of calendar year (December)
    assert get_financial_year(datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)) == "2026-27"
    # Start of calendar year (January, still prior FY)
    assert get_financial_year(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)) == "2025-26"
    # March 31st (End of FY)
    assert get_financial_year(datetime(2026, 3, 31, 23, 59, tzinfo=timezone.utc)) == "2025-26"
    # Century turnover check
    assert get_financial_year(datetime(2099, 5, 1, tzinfo=timezone.utc)) == "2099-00"
