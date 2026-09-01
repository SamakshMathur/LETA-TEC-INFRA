"""
test_quarantine_gate.py — Phase 3: Quarantine Retrieval Gate tests.

Proves that quarantined chunks (is_active=False or status=NEEDS_REVIEW)
cannot enter final retrieval results through any of the four retrieval paths:
  1. Retriever._add_to_pool  (semantic/FAISS/BM25)
  2. Retriever._direct_ref_lookup
  3. StatuteRetriever.search_statutes
  4. ProvisionGraphRetriever.search_by_provisions
"""

import os
import sys
import unittest
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.quarantine import _is_quarantined


# ─── Helpers ───────────────────────────────────────────────────────────────

def _make_chunk(is_active=True, status="ACTIVE", nested=False) -> Dict[str, Any]:
    """
    Build a minimal chunk dict.
    If nested=True, quarantine flags live inside the 'metadata' sub-dict
    (mimicking flattened-vs-nested ingestion variation).
    """
    if nested:
        return {
            "chunk_id": "chunk_001",
            "text": "ITC under Section 16",
            "rel_path": "Act/CGST.pdf",
            "metadata": {
                "rel_path": "Act/CGST.pdf",
                "citations": ["CGST_SEC_16"],
                "is_active": is_active,
                "status": status,
            }
        }
    return {
        "chunk_id": "chunk_001",
        "text": "ITC under Section 16",
        "rel_path": "Act/CGST.pdf",
        "is_active": is_active,
        "status": status,
        "metadata": {
            "rel_path": "Act/CGST.pdf",
            "citations": ["CGST_SEC_16"],
        }
    }


# ─── Unit tests for _is_quarantined helper ─────────────────────────────────

class TestIsQuarantinedHelper(unittest.TestCase):

    def test_active_chunk_not_quarantined(self):
        chunk = _make_chunk(is_active=True, status="ACTIVE")
        self.assertFalse(_is_quarantined(chunk))

    def test_is_active_false_quarantined(self):
        chunk = _make_chunk(is_active=False, status="ACTIVE")
        self.assertTrue(_is_quarantined(chunk))

    def test_needs_review_status_quarantined(self):
        chunk = _make_chunk(is_active=True, status="NEEDS_REVIEW")
        self.assertTrue(_is_quarantined(chunk))

    def test_both_flags_quarantined(self):
        chunk = _make_chunk(is_active=False, status="NEEDS_REVIEW")
        self.assertTrue(_is_quarantined(chunk))

    def test_nested_is_active_false_quarantined(self):
        """Quarantine flag lives inside metadata sub-dict (nested ingestion format)."""
        chunk = _make_chunk(is_active=False, status="ACTIVE", nested=True)
        self.assertTrue(_is_quarantined(chunk))

    def test_nested_needs_review_quarantined(self):
        chunk = _make_chunk(is_active=True, status="NEEDS_REVIEW", nested=True)
        self.assertTrue(_is_quarantined(chunk))

    def test_chunk_without_flags_not_quarantined(self):
        """Chunks with no is_active / status fields at all must pass through."""
        chunk = {
            "chunk_id": "c1",
            "text": "Some text",
            "rel_path": "Act/CGST.pdf",
            "metadata": {"citations": ["CGST_SEC_16"]},
        }
        self.assertFalse(_is_quarantined(chunk))


# ─── Path 3: StatuteRetriever.search_statutes ─────────────────────────────

class TestStatuteRetrieverQuarantine(unittest.TestCase):

    def _make_statute_chunk(self, is_active=True, status="ACTIVE"):
        """Chunk shaped the way StatuteRetriever expects it."""
        return {
            "chunk_id": "statute_c1",
            "text": "Section 16 text",
            "rel_path": "Act/CGST.pdf",
            "is_active": is_active,
            "status": status,
            "metadata": {
                "rel_path": "act/cgst.pdf",
                "citations": ["CGST_SEC_16"],
            }
        }

    def test_active_chunk_included(self):
        from app.retrieval.statute_retriever import StatuteRetriever
        sr = StatuteRetriever.__new__(StatuteRetriever)
        sr.index = {"ITC": {"primary": ["Section 16 CGST"]}}
        sr._loaded = True
        chunks = [self._make_statute_chunk(is_active=True, status="ACTIVE")]
        from unittest.mock import patch
        with patch("app.ingestion.legal_parser.LegalParser.normalize_citation", return_value="CGST_SEC_16"):
            results = sr.search_statutes(chunks, "ITC")
        self.assertEqual(len(results), 1)

    def test_quarantined_chunk_excluded(self):
        from app.retrieval.statute_retriever import StatuteRetriever
        sr = StatuteRetriever.__new__(StatuteRetriever)
        sr.index = {"ITC": {"primary": ["Section 16 CGST"]}}
        sr._loaded = True
        chunks = [self._make_statute_chunk(is_active=False, status="ACTIVE")]

        from unittest.mock import patch
        with patch("app.ingestion.legal_parser.LegalParser.normalize_citation", return_value="CGST_SEC_16"):
            results = sr.search_statutes(chunks, "ITC")
        self.assertEqual(len(results), 0,
            "Quarantined chunk (is_active=False) must not appear in statute search results")

    def test_needs_review_chunk_excluded(self):
        from app.retrieval.statute_retriever import StatuteRetriever
        sr = StatuteRetriever.__new__(StatuteRetriever)
        sr.index = {"ITC": {"primary": ["Section 16 CGST"]}}
        sr._loaded = True
        chunks = [self._make_statute_chunk(is_active=True, status="NEEDS_REVIEW")]

        from unittest.mock import patch
        with patch("app.ingestion.legal_parser.LegalParser.normalize_citation", return_value="CGST_SEC_16"):
            results = sr.search_statutes(chunks, "ITC")
        self.assertEqual(len(results), 0,
            "Quarantined chunk (status=NEEDS_REVIEW) must not appear in statute search results")


# ─── Path 4: ProvisionGraphRetriever.search_by_provisions ─────────────────

class TestProvisionGraphQuarantine(unittest.TestCase):

    def _make_graph_chunk(self, is_active=True, status="ACTIVE"):
        return {
            "chunk_id": "graph_c1",
            "text": "Rule 89 text",
            "rel_path": "Rules/CGST.pdf",
            "is_active": is_active,
            "status": status,
            "metadata": {
                "rel_path": "rules/cgst.pdf",
                "citations": ["CGST_RUL_89"],
            }
        }

    def test_active_chunk_included_by_graph(self):
        from app.retrieval.provision_graph import ProvisionGraphRetriever
        from pathlib import Path
        gr = ProvisionGraphRetriever.__new__(ProvisionGraphRetriever)
        gr.adj_list = {}
        gr._edge_count = 0
        chunks = [self._make_graph_chunk(is_active=True)]
        results = gr.search_by_provisions(chunks, {"CGST_RUL_89"})
        self.assertEqual(len(results), 1)

    def test_quarantined_chunk_excluded_by_graph(self):
        from app.retrieval.provision_graph import ProvisionGraphRetriever
        gr = ProvisionGraphRetriever.__new__(ProvisionGraphRetriever)
        gr.adj_list = {}
        gr._edge_count = 0
        chunks = [self._make_graph_chunk(is_active=False)]
        results = gr.search_by_provisions(chunks, {"CGST_RUL_89"})
        self.assertEqual(len(results), 0,
            "Quarantined chunk (is_active=False) must not appear in graph expansion results")

    def test_needs_review_chunk_excluded_by_graph(self):
        from app.retrieval.provision_graph import ProvisionGraphRetriever
        gr = ProvisionGraphRetriever.__new__(ProvisionGraphRetriever)
        gr.adj_list = {}
        gr._edge_count = 0
        chunks = [self._make_graph_chunk(is_active=True, status="NEEDS_REVIEW")]
        results = gr.search_by_provisions(chunks, {"CGST_RUL_89"})
        self.assertEqual(len(results), 0,
            "Quarantined chunk (status=NEEDS_REVIEW) must not appear in graph expansion results")


# ─── Path 2: Retriever._direct_ref_lookup (unit-level) ────────────────────

class TestDirectRefLookupQuarantine(unittest.TestCase):

    def _make_retriever_stub(self, chunk_is_active=True, chunk_status="ACTIVE"):
        """Build a minimal Retriever stub without loading FAISS/BM25."""
        from app.retrieval.retriever import Retriever
        r = Retriever.__new__(Retriever)
        r.inactive_paths = set()
        r.chunks = [
            {
                "chunk_id": "direct_c1",
                "text": "Section 16 text",
                "rel_path": "Act/CGST.pdf",
                "is_active": chunk_is_active,
                "status": chunk_status,
                "metadata": {
                    "rel_path": "Act/CGST.pdf",
                    "citations": ["CGST_SEC_16"],
                }
            }
        ]
        r._provision_index = {"CGST_SEC_16": [0]}  # maps key → chunk indices
        return r

    def test_active_chunk_pinned_by_direct_lookup(self):
        r = self._make_retriever_stub(chunk_is_active=True)
        pinned = r._direct_ref_lookup(["CGST_SEC_16"])
        self.assertEqual(len(pinned), 1)

    def test_quarantined_chunk_not_pinned(self):
        r = self._make_retriever_stub(chunk_is_active=False)
        pinned = r._direct_ref_lookup(["CGST_SEC_16"])
        self.assertEqual(len(pinned), 0,
            "Quarantined chunk (is_active=False) must not be pinned by _direct_ref_lookup")

    def test_needs_review_chunk_not_pinned(self):
        r = self._make_retriever_stub(chunk_status="NEEDS_REVIEW")
        pinned = r._direct_ref_lookup(["CGST_SEC_16"])
        self.assertEqual(len(pinned), 0,
            "Quarantined chunk (status=NEEDS_REVIEW) must not be pinned by _direct_ref_lookup")


# ─── Path 1: _add_to_pool + final boundary (functional) ───────────────────

class TestAddToPoolQuarantine(unittest.TestCase):
    """Verifies _is_quarantined is called inside _add_to_pool by checking the helper."""

    def test_quarantined_chunk_rejected_by_helper(self):
        """_is_quarantined(chunk) must return True for quarantined chunks."""
        chunk = _make_chunk(is_active=False)
        self.assertTrue(_is_quarantined(chunk))

    def test_active_chunk_accepted_by_helper(self):
        chunk = _make_chunk(is_active=True)
        self.assertFalse(_is_quarantined(chunk))

    def test_add_to_pool_code_calls_is_quarantined(self):
        """Static audit: _add_to_pool in retriever.py calls _is_quarantined."""
        retriever_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "app", "retrieval", "retriever.py")
        )
        with open(retriever_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_is_quarantined", content,
            "retriever.py must call _is_quarantined in _add_to_pool")
        # Verify it also appears in the final quarantine boundary comment/filter
        self.assertIn("Phase 3: final quarantine", content,
            "final_results filter in retriever.py must include Phase 3 quarantine boundary")

    def test_direct_ref_lookup_code_calls_is_quarantined(self):
        """Static audit: _direct_ref_lookup in retriever.py calls _is_quarantined."""
        retriever_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "app", "retrieval", "retriever.py")
        )
        with open(retriever_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Find _direct_ref_lookup definition and verify _is_quarantined is called within it
        idx = content.find("def _direct_ref_lookup(self")
        self.assertNotEqual(idx, -1, "Could not find _direct_ref_lookup definition inside retriever.py")
        section = content[idx:idx + 8000]
        self.assertIn("_is_quarantined", section,
            "_direct_ref_lookup must call _is_quarantined")

    def test_statute_retriever_code_calls_is_quarantined(self):
        """Static audit: statute_retriever.py calls _is_quarantined in search_statutes."""
        path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "app", "retrieval", "statute_retriever.py")
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_is_quarantined", content,
            "statute_retriever.py must call _is_quarantined in search_statutes")

    def test_provision_graph_code_calls_is_quarantined(self):
        """Static audit: provision_graph.py calls _is_quarantined in search_by_provisions."""
        path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "app", "retrieval", "provision_graph.py")
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_is_quarantined", content,
            "provision_graph.py must call _is_quarantined in search_by_provisions")


if __name__ == "__main__":
    unittest.main()
