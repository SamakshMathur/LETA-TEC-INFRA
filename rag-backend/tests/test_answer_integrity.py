import unittest
from app.generation.validator import validate_answer_integrity

class TestAnswerIntegrity(unittest.TestCase):
    def setUp(self):
        self.mock_chunks = [
            {
                "text": "Section 16(2) provides that no registered person shall be entitled to input tax credit unless he possesses tax invoice. Rule 42 specifies the reversal of input tax credit for common inputs. The applicable CGST rate is 18%. The time limit under Section 16(4) is 30th November of the next financial year.",
                "metadata": {
                    "citations": ["CGST_SEC_16_2", "CGST_RUL_42", "CGST_SEC_16_4"],
                    "provisions": ["CGST_SEC_16_2", "CGST_RUL_42", "CGST_SEC_16_4"]
                }
            }
        ]

    def test_exact_citation_matching(self):
        content = "Under Section 16(2), a tax invoice is mandatory for claiming ITC."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(res["citations_status"].get("16(2)"), "EXACT")
        self.assertTrue(res["is_valid"])

    def test_partial_citation_matching(self):
        content = "The taxpayer complied with Section 16 requirements."
        res = validate_answer_integrity(content, self.mock_chunks)
        # 16 is a base section number present in chunks text
        self.assertEqual(res["citations_status"].get("16"), "PARTIAL")

    def test_unverified_citation(self):
        content = "According to Section 45, the return must be filed."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(res["citations_status"].get("45"), "UNVERIFIED")
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["severity"], "HIGH")

    def test_grounded_numbers(self):
        content = "The applicable CGST rate is 18%."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(len(res["ungrounded_numbers"]), 0)
        self.assertTrue(res["is_valid"])

    def test_ungrounded_numbers(self):
        content = "The applicable CGST rate is 28%."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertIn("28%", res["ungrounded_numbers"])
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["severity"], "HIGH")

if __name__ == "__main__":
    unittest.main()
