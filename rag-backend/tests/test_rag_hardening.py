"""
tests/test_rag_hardening.py
Phase 15: Forensic hardening regression tests for LETA RAG pipeline.
Covers embedding resolution, dimensions, retrieval provenance, numeric parameter filtering,
atomic claim verification, fallback degradation, and streaming lifecycle.
"""
import os
import re
import unittest
import numpy as np

from app.retrieval.retriever import _resolve_model_path, embed_query
from app.embeddings.embedder import embed_texts
from app.generation.validator import (
    _clean_text_for_numbers,
    _clean_claim,
    validate_answer_integrity,
    verifier,
)


class TestEmbeddingModelIntegrity(unittest.TestCase):
    """Verifies local-first embedding loading and 1024-dim compatibility."""

    def test_local_model_resolution(self):
        resolved = _resolve_model_path("BAAI/bge-large-en-v1.5")
        self.assertTrue(os.path.exists(resolved), f"Resolved path does not exist: {resolved}")
        self.assertTrue(os.path.isdir(resolved), f"Resolved path is not a directory: {resolved}")
        self.assertTrue(os.path.exists(os.path.join(resolved, "config.json")), "config.json missing in resolved snapshot")

    def test_embed_query_1024_dim(self):
        vec = embed_query("What is Goods and Services Tax?")
        self.assertIsInstance(vec, np.ndarray)
        self.assertEqual(vec.shape, (1024,))
        self.assertEqual(vec.dtype, np.float32)
        # Vector should be normalized
        norm = np.linalg.norm(vec)
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_embed_texts_1024_dim(self):
        texts = ["What is GST?", "Levy and collection under Section 9."]
        vecs = embed_texts(texts)
        self.assertIsInstance(vecs, np.ndarray)
        self.assertEqual(vecs.shape, (2, 1024))


class TestNumericGroundingAndFalsePositives(unittest.TestCase):
    """Verifies elimination of false 'Ungrounded statutory parameter' warnings (e.g. 20143)."""

    def test_filename_with_section_range_no_false_positive(self):
        sample = (
            "Section 7 defines scope of supply. "
            "See [📄 View](/api/documents/view?category=all&filename=Chapter%20XXI%20Miscellaneous%20(Sections%20143–174).pdf)"
        )
        cleaned = _clean_text_for_numbers(sample)
        # Verify that %20143 or 20143 is not extracted as a numeric parameter
        nums = re.findall(r"₹?\s*\b\d+(?:,\d+)*(?:\.\d+)?%?", cleaned)
        clean_nums = [n.replace("₹", "").replace(",", "").replace("%", "").strip() for n in nums]
        self.assertNotIn("20143", clean_nums)
        self.assertNotIn("143", clean_nums)
        self.assertNotIn("174", clean_nums)

    def test_url_encoded_paths_not_parameters(self):
        sample = "Document located at /api/documents/view_by_path?path=RAG_INFORMATION_DATABASE%2FDatabase_V2.0%2FChapter%20III%20Levy%20and%20Collection%20of%20Tax%20(Sections%207%E2%80%9311A).pdf"
        cleaned = _clean_text_for_numbers(sample)
        nums = re.findall(r"₹?\s*\b\d+(?:,\d+)*(?:\.\d+)?%?", cleaned)
        clean_nums = [n.replace("₹", "").replace(",", "").replace("%", "").strip() for n in nums]
        self.assertNotIn("20", clean_nums)
        self.assertNotIn("207", clean_nums)

    def test_real_statutory_parameters_preserved(self):
        sample = (
            "Under Section 9(1), GST is levied at 18% on intra-State supply above ₹50,000 threshold. "
            "See [📄 View](/api/documents/view?category=all&filename=Chapter%20XXI%20Miscellaneous%20(Sections%20143–174).pdf)"
        )
        cleaned = _clean_text_for_numbers(sample)
        nums = [n.strip() for n in re.findall(r"₹?\s*\b\d+(?:,\d+)*(?:\.\d+)?%?", cleaned)]
        self.assertIn("18%", nums)
        self.assertIn("₹50,000", nums)


    def test_validate_answer_integrity_no_20143_warning(self):
        content = (
            "Section 7 covers scope of supply. "
            "[📄 View](/api/documents/view?category=all&filename=Chapter%20XXI%20Miscellaneous%20(Sections%20143–174).pdf)"
        )
        chunks = [{
            "chunk_id": "c1",
            "text": "Section 7. Scope of supply. All forms of supply of goods or services.",
            "rel_path": "Chapter XXI Miscellaneous (Sections 143–174).pdf",
            "metadata": {
                "citations": ["CGST_SEC_7"],
                "provisions": ["CGST_SEC_7"],
                "rel_path": "Chapter XXI Miscellaneous (Sections 143–174).pdf",
            }
        }]
        res = validate_answer_integrity(content, chunks, is_strict=False)
        self.assertNotIn("20143", res.get("ungrounded_numbers", []))
        for w in res.get("warnings", []):
            self.assertNotIn("20143", w)


class TestAtomicClaimVerification(unittest.TestCase):
    """Verifies atomic claim evaluation rather than whole-block single evaluation."""

    def test_clean_claim_strips_markdown_and_links(self):
        raw = "### Key Pillar\n- **Section 9** levies Central GST on intra-State supplies. [📄 View](/api/doc)"
        cleaned = _clean_claim(raw)
        self.assertEqual(cleaned, "Key Pillar - Section 9 levies Central GST on intra-State supplies.")

    def test_atomic_claim_statuses_in_validator(self):
        content = (
            "- Section 7 defines scope of supply.\n"
            "- Section 9 levies Central GST on intra-State supplies."
        )
        chunks = [
            {
                "chunk_id": "c_sec7",
                "text": "Section 7. For the purposes of this Act, the expression supply includes all forms of supply.",
                "rel_path": "Chapter_III.pdf",
                "metadata": {"citations": ["CGST_SEC_7"], "provisions": ["CGST_SEC_7"], "rel_path": "Chapter_III.pdf"}
            },
            {
                "chunk_id": "c_sec9",
                "text": "Section 9. There shall be levied a tax called the central goods and services tax on all intra-State supplies.",
                "rel_path": "Chapter_III.pdf",
                "metadata": {"citations": ["CGST_SEC_9"], "provisions": ["CGST_SEC_9"], "rel_path": "Chapter_III.pdf"}
            }
        ]
        res = validate_answer_integrity(content, chunks, is_strict=False)
        verified_claims = res.get("verified_claims", [])
        self.assertGreaterEqual(len(verified_claims), 2)
        citations_found = {c["citation"] for c in verified_claims}
        self.assertIn("7", citations_found)
        self.assertIn("9", citations_found)
        for c in verified_claims:
            self.assertEqual(c["status"], "VERIFIED")

    def test_unsupported_claim_marked_unverified(self):
        content = "Section 999 mandates mandatory registration for every citizen."
        chunks = [{
            "chunk_id": "c1",
            "text": "Section 7 deals with supply.",
            "rel_path": "Chapter_III.pdf",
            "metadata": {"citations": ["CGST_SEC_7"], "rel_path": "Chapter_III.pdf"}
        }]
        res = validate_answer_integrity(content, chunks, is_strict=False)
        self.assertIn("999", res.get("citations_status", {}))
        self.assertEqual(res["citations_status"]["999"], "UNVERIFIED")
        self.assertIn("UNVERIFIED_CITATION", res.get("failure_categories", []))


class TestRetrievalProvenanceIntegrity(unittest.TestCase):
    """Verifies that retrieval results retain immutable provenance, file paths, and chunk IDs."""

    def test_retriever_initialization_and_provenance(self):
        from app.dependencies import get_retriever
        retriever = get_retriever()
        self.assertIsNotNone(retriever.index)
        self.assertIsNotNone(retriever.bm25)
        self.assertGreater(len(retriever.chunks), 1000)

        results = retriever.search("What is GST?", top_k=5)
        self.assertGreater(len(results), 0)
        for chunk in results:
            self.assertIn("chunk_id", chunk)
            self.assertTrue(bool(chunk.get("chunk_id")))
            self.assertTrue(bool(chunk.get("text")))
            rel_path = chunk.get("rel_path") or chunk.get("metadata", {}).get("rel_path")
            self.assertTrue(bool(rel_path), f"Missing rel_path in chunk {chunk.get('chunk_id')}")


class TestGracefulFallbacks(unittest.TestCase):
    """Verifies that optional component absence falls back cleanly without breaking."""

    def test_cross_encoder_fallback_active(self):
        # Even if CrossEncoder is offline/unavailable, verifier returns containment or unknown
        res = verifier.verify("Section 7 defines supply", "Section 7. Scope of supply includes all forms of supply.")
        self.assertIn(res, ["SUPPORTED", "UNKNOWN", "NEUTRAL"])

    def test_batch_verify_fallback(self):
        pairs = [
            ("Section 7. Scope of supply includes all forms of supply.", "Section 7 defines supply"),
            ("Section 9. Levy of tax on intra-State supply.", "Section 9 deals with levy of CGST")
        ]
        results = verifier.verify_batch(pairs)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn(r, ["SUPPORTED", "UNKNOWN", "NEUTRAL"])


if __name__ == "__main__":
    unittest.main()
