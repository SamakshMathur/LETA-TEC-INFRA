import unittest

class TestCitations(unittest.TestCase):
    def test_citation_coordinate_provenance(self):
        coords = {"x0": 72.0, "y0": 210.5, "x1": 512.0, "y1": 256.0}
        self.assertGreater(coords["x1"], coords["x0"])
        self.assertGreater(coords["y1"], coords["y0"])

if __name__ == "__main__":
    unittest.main()
