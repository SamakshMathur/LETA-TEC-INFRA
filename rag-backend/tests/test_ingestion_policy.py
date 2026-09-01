import unittest
from app.ingestion.legal_parser import LegalParser

class TestIngestionPolicy(unittest.TestCase):

    def test_primary_law_unknown_date_active(self):
        doc_meta = {
            "document_type": "PRIMARY_LAW",
            "confidence": 0.90,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertTrue(is_active)
        self.assertEqual(status, "Completed")

    def test_rules_unknown_date_active(self):
        doc_meta = {
            "document_type": "RULES",
            "confidence": 0.88,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertTrue(is_active)
        self.assertEqual(status, "Completed")

    def test_circular_unknown_date_quarantined(self):
        doc_meta = {
            "document_type": "CIRCULAR",
            "confidence": 0.90,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertFalse(is_active)
        self.assertEqual(status, "NEEDS_REVIEW")

    def test_notification_unknown_date_quarantined(self):
        doc_meta = {
            "document_type": "NOTIFICATION",
            "confidence": 0.95,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertFalse(is_active)
        self.assertEqual(status, "NEEDS_REVIEW")

    def test_primary_law_low_confidence_quarantined(self):
        doc_meta = {
            "document_type": "PRIMARY_LAW",
            "confidence": 0.70,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertFalse(is_active)
        self.assertEqual(status, "NEEDS_REVIEW")

    def test_rules_low_confidence_quarantined(self):
        doc_meta = {
            "document_type": "RULES",
            "confidence": 0.68,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertFalse(is_active)
        self.assertEqual(status, "NEEDS_REVIEW")

    def test_primary_law_boundary_active(self):
        doc_meta = {
            "document_type": "PRIMARY_LAW",
            "confidence": 0.80,
            "date_precision": "UNKNOWN",
            "date_year": None
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertTrue(is_active)
        self.assertEqual(status, "Completed")

    def test_circular_with_valid_date_active(self):
        doc_meta = {
            "document_type": "CIRCULAR",
            "confidence": 0.92,
            "date_precision": "DAY",
            "date_year": 2022
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertTrue(is_active)
        self.assertEqual(status, "Completed")

    def test_notification_with_valid_date_active(self):
        doc_meta = {
            "document_type": "NOTIFICATION",
            "confidence": 0.90,
            "date_precision": "YEAR",
            "date_year": 2021
        }
        is_active, status = LegalParser.determine_quarantine(doc_meta)
        self.assertTrue(is_active)
        self.assertEqual(status, "Completed")

if __name__ == "__main__":
    unittest.main()
