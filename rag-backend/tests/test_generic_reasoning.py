import unittest
import datetime
from app.generation.calculation_engine import add_months, add_years, add_days, parse_date, execute_structured_calculation, process_internal_calculations
from app.generation.validator import validate_answer_integrity, CrossEncoderEntailment

class TestGenericReasoning(unittest.TestCase):
    def test_date_primitives(self):
        # Test basic addition and subtraction
        base = datetime.date(2022, 2, 28)
        self.assertEqual(add_months(base, 3), datetime.date(2022, 5, 28))
        self.assertEqual(add_months(base, -3), datetime.date(2021, 11, 28))
        
        # Test leap year day fallback
        leap_base = datetime.date(2024, 2, 29)
        self.assertEqual(add_years(leap_base, 1), datetime.date(2025, 2, 28))
        self.assertEqual(add_years(leap_base, 4), datetime.date(2028, 2, 29))
        
        # Test basic day arithmetic
        self.assertEqual(add_days(base, 10), datetime.date(2022, 3, 10))

    def test_parse_date(self):
        self.assertEqual(parse_date("28-02-2022"), datetime.date(2022, 2, 28))
        self.assertEqual(parse_date("2022-02-28"), datetime.date(2022, 2, 28))
        self.assertEqual(parse_date("invalid-date"), None)

    def test_execute_structured_calculation(self):
        chunks = [
            {
                "text": "The due date for filing annual return for financial year 2020-21 was extended to 28-02-2022.",
                "metadata": {"rel_path": "notification_56_2023.pdf"}
            },
            {
                "text": "Under Section 73(2), the proper officer shall issue the show cause notice at least three months prior to the time limit specified in Section 73(10) for issuance of order.",
                "metadata": {"rel_path": "cgst_act.pdf"}
            }
        ]
        
        calc_req = {
            "type": "date_offset",
            "base": "28-02-2022",
            "base_src": "SRC-1",
            "offset": "-3",
            "unit": "months",
            "rule": "Section 73(2)",
            "rule_src": "SRC-2"
        }
        
        res = execute_structured_calculation(calc_req, chunks)
        self.assertEqual(res["value"], "28-11-2021") # Nov 28 (3 months prior to Feb 28)

    def test_process_internal_calculations(self):
        chunks = [
            {
                "text": "The due date for filing annual return for financial year 2020-21 was extended to 28-02-2022.",
                "metadata": {"rel_path": "notification_56_2023.pdf"}
            },
            {
                "text": "Under Section 73(2), the proper officer shall issue the show cause notice at least three months prior to the time limit specified in Section 73(10) for issuance of order.",
                "metadata": {"rel_path": "cgst_act.pdf"}
            }
        ]
        
        text = 'The SCN due date for FY 2020-21 under Section 73 is <calculate type="date_offset" base="28-02-2022" base_src="SRC-1" offset="-3" unit="months" rule="Section 73(2)" rule_src="SRC-2" />.'
        cleaned, claims = process_internal_calculations(text, chunks)
        self.assertEqual(cleaned, "The SCN due date for FY 2020-21 under Section 73 is 28-11-2021.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["value"], "28-11-2021")

    def test_validate_answer_integrity_derived_grounding(self):
        # Mock CrossEncoderEntailment to bypass lazy load failure in offline sandbox
        from app.generation.validator import verifier
        verifier.load_failed = False
        
        from unittest.mock import patch
        with patch.object(verifier, '_lazy_load', return_value=None), \
             patch.object(verifier, 'verify_batch', return_value=["SUPPORTED", "SUPPORTED"]):
            chunks = [
                {
                    "text": "The due date for filing annual return for financial year 2020-21 was extended to 28-02-2022.",
                    "metadata": {"rel_path": "notification_56_2023.pdf"}
                },
                {
                    "text": "Under Section 73(2), the proper officer shall issue the show cause notice at least three months prior to the time limit specified in Section 73(10) for issuance of order.",
                    "metadata": {"rel_path": "cgst_act.pdf", "provisions": ["Section 73", "Section 84"]}
                }
            ]
            
            calculated_claims = [
                {
                    "status": "DERIVED_SUPPORTED",
                    "value": "28-11-2021",
                    "provenance": {
                        "base": "28-02-2022",
                        "operation": "-3 months",
                        "base_source": "SRC-1",
                        "rule_source": "SRC-2",
                        "rule": "Section 73(2)"
                    }
                }
            ]
            
            # Verify that the derived date "28-11-2021" is whitelisted and does not raise ungrounded warnings
            # Also verify that chapter heading ranges like "Sections 73–84" in content are matched from metadata/paths
            res = validate_answer_integrity(
                content="The SCN due date for FY 2020-21 under Section 73 is 28-11-2021. Review Sections 73–84.",
                chunks=chunks,
                is_strict=True,
                user_query="due date SCN 2020-21 Section 73",
                calculated_claims=calculated_claims
            )
            print("VALIDATION RESULT WARNINGS:", res["warnings"])
            print("VALIDATION RESULT UNGROUNDED NUMBERS:", res["ungrounded_numbers"])
            self.assertTrue(res["is_valid"])
            self.assertEqual(len(res["ungrounded_numbers"]), 0)

if __name__ == "__main__":
    unittest.main()
