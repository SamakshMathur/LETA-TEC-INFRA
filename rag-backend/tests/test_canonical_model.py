import unittest
from app.ingestion.legal_parser import LegalParser

class TestCanonicalModel(unittest.TestCase):
    def test_metadata_extraction_circular(self):
        text = "Government of India\nMinistry of Finance\nCircular No. 237/2024-GST\nCBIC-190354/172/2024-TRU Section\nDated the 15th October, 2024"
        meta = LegalParser.extract_document_metadata(text, text, "cir237.pdf")
        self.assertEqual(meta["document_type"], "CIRCULAR")
        self.assertEqual(meta["jurisdiction"], "Central")
        self.assertEqual(meta["authority"], "Central Board of Indirect Taxes and Customs")
        self.assertIn("237/2024", meta["title"])
        self.assertGreaterEqual(meta["confidence"], 0.85)

    def test_metadata_extraction_act(self):
        text = "THE CENTRAL GOODS AND SERVICES TAX ACT, 2017\nNo. 12 of 2017\nAn Act to make a provision for levy and collection of tax on intra-State supply of goods"
        meta = LegalParser.extract_document_metadata(text, text, "cgst_act.pdf")
        self.assertEqual(meta["document_type"], "PRIMARY_LAW")
        self.assertEqual(meta["jurisdiction"], "Central")
        self.assertEqual(meta["authority"], "Parliament of India")
        self.assertIn("Act, 2017", meta["title"])
        self.assertGreaterEqual(meta["confidence"], 0.85)

    def test_metadata_extraction_court(self):
        text = "IN THE SUPREME COURT OF INDIA\nCIVIL APPELLATE JURISDICTION\nCivil Appeal No. 2351 of 2024\nM/s Union of India Versus M/s Adani Power Ltd"
        meta = LegalParser.extract_document_metadata(text, text, "court_case.pdf")
        self.assertEqual(meta["document_type"], "CASE_LAW")
        self.assertEqual(meta["jurisdiction"], "Supreme")
        self.assertEqual(meta["authority"], "Supreme Court of India")
        self.assertIn("Vs", meta["title"])
        self.assertGreaterEqual(meta["confidence"], 0.85)

if __name__ == "__main__":
    unittest.main()
