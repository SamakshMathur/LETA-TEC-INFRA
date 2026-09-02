import os
import sys
import unittest
from starlette.requests import Request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.document_discovery import DocumentDiscoveryService
from app.api.documents import (
    get_categories,
    get_registry_summary,
    list_documents,
    list_circulars_by_year,
    list_notifications_by_year,
    list_category_by_year,
)
from app.api.admin import admin_status
from app.services.knowledge_service import KnowledgeService


class TestDynamicDocumentDiscovery(unittest.IsolatedAsyncioTestCase):
    def test_base_dir_resolves_and_exists(self):
        """DocumentDiscoveryService must resolve the active Database_V2.0 path."""
        base_dir = DocumentDiscoveryService.get_base_dir()
        self.assertTrue(base_dir.exists(), f"BASE_DIR does not exist: {base_dir}")

    def test_dynamic_category_discovery(self):
        """Categories must be discovered directly from disk with live file and size metrics."""
        cats = DocumentDiscoveryService.discover_categories()
        self.assertIn("circulars", cats)
        self.assertIn("rules", cats)
        self.assertIn("highcourt", cats)
        self.assertIn("acts", cats)
        self.assertIn("supremecourt", cats)

        # Verify live calculated file counts
        self.assertGreaterEqual(cats["circulars"]["files"], 250)
        self.assertGreaterEqual(cats["rules"]["files"], 200)
        self.assertGreaterEqual(cats["highcourt"]["files"], 150)
        self.assertGreater(cats["circulars"]["size_mb"], 10.0)

    def test_synonym_normalization_no_splintering(self):
        """Category normalizer must map folder variations to canonical categories without splintering."""
        self.assertEqual(DocumentDiscoveryService.normalize_category("circulars(2017-2025)")[0], "circulars")
        self.assertEqual(DocumentDiscoveryService.normalize_category("Rate_notifications_2.0")[0], "notifications")
        self.assertEqual(DocumentDiscoveryService.normalize_category("CGST Rules 10-08-2026")[0], "rules")
        self.assertEqual(DocumentDiscoveryService.normalize_category("High Court Case Laws")[0], "highcourt")
        self.assertEqual(DocumentDiscoveryService.normalize_category("Supreme Court Case Laws")[0], "supremecourt")
        self.assertEqual(DocumentDiscoveryService.normalize_category("CGST Acts")[0], "acts")
        self.assertEqual(DocumentDiscoveryService.normalize_category("IGST Rules 04 Aug 2026")[0], "rules")

    def test_dynamic_unknown_folder_discovery(self):
        """Unknown future folders must be cleanly normalized as dynamic categories."""
        cat_id, label, is_dyn = DocumentDiscoveryService.normalize_category("GSTN_Advisories_2027")
        self.assertEqual(cat_id, "gstn_advisories_2027")
        self.assertEqual(label, "Gstn Advisories 2027")
        self.assertTrue(is_dyn)

    def test_circulars_year_breakdown(self):
        """Year breakdown must accurately group all circulars descending across all 9 years."""
        grouped = list_circulars_by_year()
        self.assertIsInstance(grouped, dict)
        years = list(grouped.keys())
        self.assertIn("2025", years)
        self.assertIn("2024", years)
        self.assertIn("2017", years)
        total_in_breakdown = sum(len(docs) for docs in grouped.values())
        self.assertGreaterEqual(total_in_breakdown, 250)

    def test_dynamic_category_year_breakdown_endpoint(self):
        """The /list/{category}/by-year endpoint must work for any valid category."""
        highcourt_by_year = list_category_by_year("highcourt")
        self.assertIsInstance(highcourt_by_year, dict)
        self.assertGreater(len(highcourt_by_year), 0)

    def test_get_categories_api_contract(self):
        """GET /api/documents/categories must return { category_id: count } for DocumentLibrary."""
        cats = get_categories()
        self.assertIsInstance(cats, dict)
        self.assertGreater(cats.get("circulars", 0), 200)
        self.assertGreater(cats.get("rules", 0), 100)

    def test_get_registry_summary_endpoint(self):
        """GET /api/documents/registry/summary returns structured summary with storage metrics."""
        summary = get_registry_summary()
        self.assertIn("total_documents", summary)
        self.assertIn("total_storage_mb", summary)
        self.assertIn("categories", summary)
        self.assertGreaterEqual(summary["total_documents"], 600)
        self.assertGreater(summary["total_storage_mb"], 100.0)

    async def test_admin_status_endpoint(self):
        """GET /api/admin/status must return live category counts and total storage."""
        scope = {"type": "http", "path": "/api/admin/status", "client": ("127.0.0.1", 12345), "headers": []}
        req = Request(scope)
        current_admin = {"username": "admin_test", "role": "admin"}
        res = await admin_status(req, current_admin=current_admin)
        self.assertIn("categories", res)
        self.assertIn("total_documents", res)
        self.assertIn("total_storage_mb", res)
        self.assertGreaterEqual(res["total_documents"], 600)

    def test_knowledge_service_list_documents(self):
        """KnowledgeService.list_documents must return merged physical and mongo documents."""
        docs = KnowledgeService.list_documents(limit=20)
        self.assertIsInstance(docs, list)
        self.assertGreater(len(docs), 0)
        self.assertIn("filename", docs[0])
        self.assertIn("category", docs[0])
        self.assertIn("status", docs[0])


if __name__ == "__main__":
    unittest.main()
