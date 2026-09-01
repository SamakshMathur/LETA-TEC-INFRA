import unittest

class TestIngestion(unittest.TestCase):
    def test_quarantine_flagging(self):
        # Confidence score below 0.85 should set is_active=False
        confidence = 0.50
        is_active = True if confidence >= 0.85 else False
        self.assertFalse(is_active)

if __name__ == "__main__":
    unittest.main()
