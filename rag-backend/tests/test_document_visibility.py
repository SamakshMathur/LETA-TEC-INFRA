import os
import sys
import unittest
from unittest.mock import MagicMock
from starlette.requests import Request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.documents import (
    BASE_DIR,
    CATEGORY_MAP,
    get_categories,
    list_documents,
    list_circulars_by_year,
    list_notifications_by_year,
)
from app.api.admin import admin_status


class TestDocumentVisibility(unittest.IsolatedAsyncioTestCase):
    def test_base_dir_resolves_and_exists(self):
        """BASE_DIR must resolve to the active Database_V2.0 location."""
        self.assertTrue(BASE_DIR.exists(), f"BASE_DIR does not exist: {BASE_DIR}")
        self.assertTrue(
            (BASE_DIR / "circulars(2017-2025)").exists(),
            "circulars(2017-2025) folder not found under BASE_DIR",
        )
        self.assertTrue(
            (BASE_DIR / "CGST Rules 10-08-2026").exists(),
            "CGST Rules 10-08-2026 folder not found under BASE_DIR",
        )

    def test_get_categories_returns_non_zero_counts(self):
        """get_categories must return non-zero counts for populated V2.0 categories."""
        cats = get_categories()
        self.assertGreaterEqual(cats.get("circulars", 0), 200, "Expected >=200 circulars")
        self.assertGreaterEqual(cats.get("rules", 0), 100, "Expected >=100 rules")
        self.assertGreaterEqual(cats.get("highcourt", 0), 100, "Expected >=100 high court case laws")
        self.assertGreaterEqual(cats.get("acts", 0), 10, "Expected >=10 acts")
        self.assertGreaterEqual(cats.get("supremecourt", 0), 5, "Expected >=5 supreme court case laws")

    def test_circulars_by_year_structure(self):
        """list_circulars_by_year must return year-bucketed dictionaries with all 9 years."""
        grouped = list_circulars_by_year()
        self.assertIsInstance(grouped, dict)
        self.assertIn("2024", grouped)
        self.assertIn("2023", grouped)
        self.assertIn("2017", grouped)
        self.assertGreater(len(grouped["2024"]), 0)
        self.assertIn("filename", grouped["2024"][0])
        self.assertIn("title", grouped["2024"][0])

    def test_list_all_documents(self):
        """list_documents('all') must return documents across categories."""
        all_docs = list_documents("all")
        self.assertIsInstance(all_docs, list)
        self.assertGreater(len(all_docs), 50)

    async def test_admin_status_categories(self):
        """admin_status endpoint must return non-zero category counts for overview dashboard."""
        scope = {"type": "http", "path": "/api/admin/status", "client": ("127.0.0.1", 12345), "headers": []}
        req = Request(scope)
        current_admin = {"username": "admin_test", "role": "admin"}
        res = await admin_status(req, current_admin=current_admin)
        self.assertIn("categories", res)
        cats = res["categories"]
        self.assertGreater(cats["circulars"]["files"], 200)
        self.assertGreater(cats["rules"]["files"], 100)
        self.assertGreater(cats["highcourt"]["files"], 100)


if __name__ == "__main__":
    unittest.main()
