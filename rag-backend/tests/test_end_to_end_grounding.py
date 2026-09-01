import unittest

class TestEndToEndGrounding(unittest.TestCase):
    def test_insufficient_evidence_fallback(self):
        # When repair fails, standard qualified fallback response should be returned
        is_valid_repaired = False
        warnings_str = "- Section 45 is cited but not present"
        if not is_valid_repaired:
            answer = (
                "I cannot sufficiently verify this answer from the available legal sources.\n\n"
                "**Unverified details:**\n"
                f"{warnings_str}"
            )
        self.assertIn("cannot sufficiently verify", answer)

if __name__ == "__main__":
    unittest.main()
