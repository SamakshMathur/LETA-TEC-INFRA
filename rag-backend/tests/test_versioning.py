import unittest

class TestVersioning(unittest.TestCase):
    def test_version_mapping(self):
        version = {
            "version_id": "ver_cgst_act_2024_amend",
            "effective_from": "2024-11-01T00:00:00Z",
            "effective_to": None
        }
        self.assertEqual(version["version_id"], "ver_cgst_act_2024_amend")

if __name__ == "__main__":
    unittest.main()
