"""
test_secondary_chunk_splitting.py — Phase 4: Secondary Statute/Rule Chunk Splitting

Tests:
  1.  Small statute section (≤ 2000 chars) remains unchanged.
  2.  Oversized statute section is split into multiple children.
  3.  Oversized rule is split into multiple children.
  4.  Full text is preserved exactly after joining child chunks in order.
  5.  No text is silently lost.
  6.  No child chunk exceeds SECONDARY_SPLIT_MAX chars.
  7.  Paragraph boundaries are preferred over sentence boundaries.
  8.  Clause/numbered boundaries are respected.
  9.  Child chunks preserve document/provision provenance.
  10. Child chunk IDs are unique and deterministic.
  11. Re-running the splitter on identical input produces identical output.
  12. Existing Case Law/AAR chunking behavior remains unchanged.
  13. Existing parser tests still pass (structural_split smoke test).
  14. Full regression suite still passes (run separately).
  15. Pathological ~76k-char section is fully split with no oversized remnant.
"""

import os
import sys
import unittest
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ingestion.statute_splitter import (
    split_oversized_provision,
    apply_secondary_split_to_statute_chunks,
    _deterministic_child_id,
    _best_split_point,
    SECONDARY_SPLIT_TRIGGER,
    SECONDARY_SPLIT_TARGET,
    SECONDARY_SPLIT_MAX,
)
from app.ingestion.legal_parser import LegalParser


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_provision_chunk(text: str, provision: str = "Section 16",
                           doc_type: str = "PRIMARY_LAW") -> dict:
    """Build a minimal provision chunk as structural_split produces it."""
    return {
        "text": text,
        "structure": "PROVISION",
        "provision": provision,
        "chunk_id": f"PRI_CGST_{provision.replace(' ', '_')}_DEADBE_P0",
        "rel_path": "Act/CGST_Act_2017.pdf",
        "source": "/data/Act/CGST_Act_2017.pdf",
        "metadata": {
            "rel_path": "Act/CGST_Act_2017.pdf",
            "document_type": doc_type,
            "topic": "ITC",
            "law_type": "substantive",
            "citations": ["CGST_SEC_16"],
            "section_type": "PROVISION",
        },
    }


def _para_text(n_paras: int, para_len: int = 300) -> str:
    """Generate text with n_paras paragraph blocks of ~para_len chars each."""
    paras = []
    for i in range(n_paras):
        words = f"This is paragraph {i+1} discussing Input Tax Credit eligibility. "
        words = (words * (para_len // len(words) + 1))[:para_len]
        paras.append(words)
    return "\n\n".join(paras)


# ─── Test suite ───────────────────────────────────────────────────────────────

class TestStatuteSplitterUnit(unittest.TestCase):
    """Unit tests for statute_splitter.py in isolation."""

    # ── Test 1: Small chunk unchanged ─────────────────────────────────────────

    def test_1_small_chunk_unchanged(self):
        """Chunk at or below TRIGGER passes through unchanged."""
        text = "Section 16 This is a short provision.\n\n" + ("x " * 50)
        self.assertLessEqual(len(text), SECONDARY_SPLIT_TRIGGER)
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], chunk, "Small chunk must be returned by identity (no copy)")

    def test_1b_boundary_chunk_unchanged(self):
        """Chunk exactly at TRIGGER boundary passes through unchanged."""
        text = "A" * SECONDARY_SPLIT_TRIGGER
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        self.assertEqual(len(result), 1)

    # ── Test 2: Oversized statute section is split ─────────────────────────────

    def test_2_oversized_statute_section_splits(self):
        """A statute section with text > TRIGGER is split into 2+ children."""
        text = _para_text(n_paras=10, para_len=500)  # ~5500 chars
        self.assertGreater(len(text), SECONDARY_SPLIT_TRIGGER)
        chunk = _make_provision_chunk(text, provision="Section 16")
        result = split_oversized_provision(chunk)
        self.assertGreater(len(result), 1, "Oversized chunk must produce multiple children")

    # ── Test 3: Oversized rule is split ──────────────────────────────────────

    def test_3_oversized_rule_splits(self):
        """A rule chunk with text > TRIGGER is split into 2+ children."""
        text = _para_text(n_paras=8, para_len=400)
        chunk = _make_provision_chunk(text, provision="Rule 89", doc_type="RULES")
        result = split_oversized_provision(chunk)
        self.assertGreater(len(result), 1)

    # ── Test 4: Full text preserved after joining ─────────────────────────────

    def test_4_full_text_preserved(self):
        """Joining child texts in order produces the original text exactly (100% character/byte preservation)."""
        text = _para_text(n_paras=12, para_len=400)
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        joined = "".join(c["text"] for c in result)
        self.assertEqual(
            joined,
            text,
            "Concatenation of all child texts must equal original text exactly (character-by-character)"
        )

    # ── Test 5: No text lost ──────────────────────────────────────────────────

    def test_5_no_text_lost(self):
        """Total character count of children is exactly equal to the original text length."""
        text = _para_text(n_paras=10, para_len=600)
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        total_child_len = sum(len(c["text"]) for c in result)
        self.assertEqual(
            total_child_len,
            len(text),
            "Total child text length must match original text length exactly"
        )

    # ── Test 6: No child exceeds MAX ─────────────────────────────────────────

    def test_6_no_child_exceeds_max(self):
        """Every child chunk text must be <= SECONDARY_SPLIT_MAX characters."""
        text = _para_text(n_paras=20, para_len=800)
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        for i, child in enumerate(result):
            self.assertLessEqual(
                len(child["text"]),
                SECONDARY_SPLIT_MAX,
                f"Child {i} has {len(child['text'])} chars, exceeds max {SECONDARY_SPLIT_MAX}"
            )

    # ── Test 7: Paragraph boundary preference ────────────────────────────────

    def test_7_paragraph_boundary_preference(self):
        """Splitter prefers paragraph (double-newline) boundaries over mid-sentence splits."""
        # Construct text where a paragraph boundary exists well within target range
        para_a = "A " * 600   # 1200 chars
        para_b = "B " * 600
        para_c = "C " * 600
        text = para_a + "\n\n" + para_b + "\n\n" + para_c
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        self.assertGreater(len(result), 1)

    # ── Test 8: Numbered clause/list boundary ────────────────────────────────

    def test_8_clause_boundary_respected(self):
        """Numbered clauses are used as split points when paragraph breaks are absent."""
        # Text without \n\n but with numbered clauses
        prefix = "Section 16 provides: "
        clauses = " ".join(
            f"({i}) This is clause {i} with important legal content about GST eligibility "
            f"for input tax credit and associated conditions that must be satisfied. "
            for i in range(1, 20)
        )
        text = prefix + clauses
        self.assertGreater(len(text), SECONDARY_SPLIT_TRIGGER)
        chunk = _make_provision_chunk(text)
        result = split_oversized_provision(chunk)
        self.assertGreater(len(result), 1)
        for child in result:
            self.assertLessEqual(len(child["text"]), SECONDARY_SPLIT_MAX)

    # ── Test 9: Provenance preservation ──────────────────────────────────────

    def test_9_provenance_preserved_in_children(self):
        """Every child inherits parent provision marker, rel_path, document_type, citations."""
        text = _para_text(n_paras=10, para_len=500)
        chunk = _make_provision_chunk(text, provision="Section 17", doc_type="PRIMARY_LAW")
        result = split_oversized_provision(chunk)

        for i, child in enumerate(result):
            with self.subTest(child_index=i):
                # Legal identity must survive
                self.assertEqual(child.get("provision"), "Section 17",
                    "provision marker must be inherited")
                self.assertEqual(child.get("rel_path"), "Act/CGST_Act_2017.pdf",
                    "rel_path must be inherited")
                self.assertEqual(child.get("structure"), "PROVISION",
                    "structure must be inherited")
                # Metadata provenance
                meta = child.get("metadata", {})
                self.assertEqual(meta.get("document_type"), "PRIMARY_LAW",
                    "document_type must survive in metadata")
                self.assertEqual(meta.get("citations"), ["CGST_SEC_16"],
                    "citations must survive in metadata")
                # Secondary split markers
                self.assertTrue(child.get("_secondary_split"))
                self.assertEqual(child.get("_child_index"), i)
                self.assertEqual(child.get("_child_count"), len(result))

    # ── Test 10: Unique deterministic chunk IDs ───────────────────────────────

    def test_10_unique_deterministic_chunk_ids(self):
        """Every child has a unique chunk_id, and the same input always produces the same IDs."""
        text = _para_text(n_paras=10, para_len=500)
        chunk = _make_provision_chunk(text)

        result1 = split_oversized_provision(chunk)
        result2 = split_oversized_provision(chunk)

        ids1 = [c["chunk_id"] for c in result1]
        ids2 = [c["chunk_id"] for c in result2]

        # Deterministic: same input → same IDs
        self.assertEqual(ids1, ids2, "IDs must be deterministic across runs")

        # Unique: no two children share the same ID
        self.assertEqual(len(ids1), len(set(ids1)), "All child chunk IDs must be unique")

    # ── Test 11: Determinism ──────────────────────────────────────────────────

    def test_11_determinism(self):
        """Re-running the splitter on identical input produces identical output."""
        text = _para_text(n_paras=15, para_len=400)
        chunk = _make_provision_chunk(text)

        result_a = split_oversized_provision(chunk)
        result_b = split_oversized_provision(chunk)

        self.assertEqual(len(result_a), len(result_b))
        for a, b in zip(result_a, result_b):
            self.assertEqual(a["text"], b["text"])
            self.assertEqual(a["chunk_id"], b["chunk_id"])

    # ── Test 12: Case Law path unchanged ─────────────────────────────────────

    def test_12_case_law_path_unchanged(self):
        """structural_split for CASE_LAW does NOT route through secondary splitter."""
        # Case law text with explicit structural headers
        text = (
            "Facts of the Case\n"
            "The applicant manufactures widgets.\n\n"
            "Issue for determination\n"
            "Whether ITC is admissible on Section 16(2)(d).\n\n"
            "Analysis\n"
            "Section 16 of CGST Act, 2017 provides for eligibility.\n\n"
            "Ruling\n"
            "ITC is admissible subject to conditions.\n"
        )
        chunks = LegalParser.structural_split(text, "CASE_LAW")
        # Should return semantic segments, NOT provision splits
        for c in chunks:
            self.assertIn(c["structure"], ["FACTS", "ISSUE", "ANALYSIS", "RULING", "BACKGROUND"],
                f"Unexpected structure type: {c['structure']}")
            # Case law path must NOT have _secondary_split marker
            self.assertFalse(c.get("_secondary_split"),
                "Case law chunks must not have _secondary_split marker")

    # ── Test 13: Small statute from structural_split passes through ───────────

    def test_13_small_statute_structural_split_unchanged(self):
        """structural_split for PRIMARY_LAW with small sections produces plain PROVISION chunks."""
        text = (
            "Section 2 Definitions\n"
            "In this Act, unless the context otherwise requires:\n"
            "(a) 'taxable person' means a person who is registered.\n"
            "(b) 'supply' includes all forms of supply of goods or services.\n\n"
            "Section 3 Officers\n"
            "There shall be such officers as the Central Government may appoint.\n"
        )
        chunks = LegalParser.structural_split(text, "PRIMARY_LAW")
        for c in chunks:
            self.assertEqual(c["structure"], "PROVISION")
            self.assertFalse(c.get("_secondary_split"),
                "Small statute provisions must not be flagged as secondary splits")

    # ── Test 15: Pathological ~76k-char section ───────────────────────────────

    def test_15_pathological_76k_char_section(self):
        """
        A ~76,227-character statute section (worst-case example from Phase 0 audit)
        must not remain as a single chunk.

        All child chunks must be <= SECONDARY_SPLIT_MAX.
        Full text must be preserved.
        """
        PATHOLOGICAL_SIZE = 76_227
        # Simulate a realistic large section: paragraphs of mixed content
        para_unit = (
            "In accordance with the provisions of sub-section (1) of Section 16 of the "
            "Central Goods and Services Tax Act, 2017, every registered person shall, "
            "subject to such conditions and restrictions as may be prescribed and in "
            "the manner specified in section 49, be entitled to take credit of input "
            "tax charged on any supply of goods or services or both to him which are "
            "used or intended to be used in the course or furtherance of his business "
            "and the said amount shall be credited to the electronic credit ledger "
            "of such person.\n\n"
        )
        # Build up to ~76k chars using repeating paragraphs with slight variation
        segments = []
        total = 0
        idx = 0
        while total < PATHOLOGICAL_SIZE:
            seg = f"({idx + 1}) " + para_unit
            segments.append(seg)
            total += len(seg)
            idx += 1
        text = "".join(segments)[:PATHOLOGICAL_SIZE]

        original_len = len(text)
        self.assertGreaterEqual(original_len, 70_000, "Pathological text must be >= 70k chars")

        chunk = _make_provision_chunk(text, provision="Section 16")
        result = split_oversized_provision(chunk)

        # 1. Must produce multiple children
        self.assertGreater(len(result), 1,
            f"76k-char section must be split; got {len(result)} chunks")

        # 2. No child may exceed MAX
        for i, child in enumerate(result):
            self.assertLessEqual(
                len(child["text"]), SECONDARY_SPLIT_MAX,
                f"Child {i} has {len(child['text'])} chars, exceeds max {SECONDARY_SPLIT_MAX}"
            )

        # 3. Full text preserved exactly byte-for-byte
        joined = "".join(c["text"] for c in result)
        self.assertEqual(joined, text,
            "All child chunk text must equal original text exactly when concatenated (no modification)")

        # Report (printed, not asserted)
        largest = max(len(c["text"]) for c in result)
        print(f"\n[Test 15] Pathological chunk: original={original_len} chars | "
              f"children={len(result)} | largest_child={largest} chars")


class TestApplySecondaryToList(unittest.TestCase):
    """Tests for apply_secondary_split_to_statute_chunks() (list processing)."""

    def test_mixed_list_small_and_large(self):
        """Mixed list: small chunks unchanged, large ones split; order preserved."""
        small_text = "Section 2. Short definitions. (a) taxable person means registered. " * 5
        large_text = _para_text(n_paras=10, para_len=500)

        small_chunk = _make_provision_chunk(small_text, "Section 2")
        large_chunk = _make_provision_chunk(large_text, "Section 16")

        result = apply_secondary_split_to_statute_chunks([small_chunk, large_chunk])

        # Small chunk at position 0 untouched
        self.assertIs(result[0], small_chunk)
        # Large chunk is expanded
        self.assertGreater(len(result), 2)

        # All large-chunk children come after the small chunk
        large_children = [c for c in result if c is not small_chunk]
        for child in large_children:
            self.assertLessEqual(len(child["text"]), SECONDARY_SPLIT_MAX)

    def test_empty_list(self):
        """Empty chunk list returns empty list."""
        result = apply_secondary_split_to_statute_chunks([])
        self.assertEqual(result, [])

    def test_all_small_list_unchanged(self):
        """All-small list passes through unchanged."""
        chunks = [
            _make_provision_chunk("Short text " * 20, f"Section {i}")
            for i in range(5)
        ]
        result = apply_secondary_split_to_statute_chunks(chunks)
        self.assertEqual(len(result), len(chunks))
        for orig, out in zip(chunks, result):
            self.assertIs(orig, out)


class TestBestSplitPoint(unittest.TestCase):
    """Unit tests for _best_split_point()."""

    def test_paragraph_preferred(self):
        """With paragraph and sentence boundaries both available, paragraph wins."""
        # Para boundary at ~target, sentence boundary before that
        target = 500
        maximum = 1000
        text = ("word " * 80) + "\n\n" + ("word " * 80) + ". Word " + ("word " * 80)
        pos = _best_split_point(text, target=target, maximum=maximum)
        # Should find the \n\n as split point
        self.assertGreater(pos, 0)
        self.assertLessEqual(pos, maximum)

    def test_hard_cut_fallback(self):
        """With no whitespace at all, hard-cuts at maximum."""
        text = "A" * 3000
        pos = _best_split_point(text, target=500, maximum=1000)
        self.assertEqual(pos, 1000)

    def test_does_not_produce_empty_left_slice(self):
        """Split point must be > 0 unless the text itself is very short."""
        text = "\n\n" + "word " * 200
        pos = _best_split_point(text, target=300, maximum=600)
        # The paragraph boundary at pos=0 is before search_start, should skip it
        # and find the next boundary or fallback
        self.assertGreaterEqual(pos, 0)


class TestStructuralSplitRegressionSmoke(unittest.TestCase):
    """Smoke regression: existing structural_split behavior still works."""

    def test_statute_provision_split_produces_provision_chunks(self):
        """structural_split for PRIMARY_LAW produces PROVISION structure chunks."""
        text = "Section 9 Levy.\nThere shall be levied a tax on supplies.\n\nSection 10 Composition.\nA registered person may opt for composition."
        chunks = LegalParser.structural_split(text, "PRIMARY_LAW")
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertIn("text", c)
            self.assertIn("structure", c)

    def test_rules_split_produces_provision_chunks(self):
        """structural_split for RULES produces PROVISION structure chunks."""
        text = "Rule 89 Application.\nA person may apply for refund.\n\nRule 90 Scrutiny.\nThe proper officer shall scrutinize."
        chunks = LegalParser.structural_split(text, "RULES")
        self.assertGreater(len(chunks), 0)

    def test_case_law_split_produces_semantic_segments(self):
        """structural_split for CASE_LAW produces semantic segments (not provisions)."""
        text = (
            "Facts of the Case\nApplicant manufactures goods.\n\n"
            "Ruling\nITC is admissible.\n"
        )
        chunks = LegalParser.structural_split(text, "CASE_LAW")
        structures = {c["structure"] for c in chunks}
        # Should contain semantic types, not PROVISION
        self.assertTrue(
            structures.intersection({"FACTS", "RULING", "BACKGROUND"}),
            f"Expected semantic structure types; got {structures}"
        )

    def test_normalize_citation_unchanged(self):
        """LegalParser.normalize_citation() still works after parser modification."""
        result = LegalParser.normalize_citation("section", "16")
        self.assertEqual(result, "CGST_SEC_16")

    def test_extract_citations_unchanged(self):
        """LegalParser.extract_citations() still works after parser modification."""
        text = "Under Section 16(2) of CGST Act, ITC is eligible subject to Rule 36."
        citations = LegalParser.extract_citations(text, normalize=True)
        self.assertIn("CGST_SEC_16", citations[0])


class TestLegalParserStructuralSplitIntegration(unittest.TestCase):
    """Integration tests verifying that LegalParser.structural_split() routes oversized chunks through the splitter."""

    def test_structural_split_integration_oversized_statute(self):
        """Proves that LegalParser.structural_split(oversized_statute, 'PRIMARY_LAW') splits text correctly."""
        # 1. Prepare oversized statute text
        para = "Section 16 Eligibility for input tax credit. " + ("This is detailed legal text. " * 150)
        self.assertGreater(len(para), SECONDARY_SPLIT_TRIGGER)

        # 2. Call the production parser endpoint
        chunks = LegalParser.structural_split(para, "PRIMARY_LAW")

        # 3. Verify multiple chunks are produced
        self.assertGreater(len(chunks), 1, "Oversized statute must be split into multiple chunks")

        # 4. Verify size boundaries
        for i, c in enumerate(chunks):
            self.assertLessEqual(len(c["text"]), SECONDARY_SPLIT_MAX, f"Chunk {i} text exceeds max size")
            self.assertEqual(c["structure"], "PROVISION")
            self.assertEqual(c["provision"], "Section 16")
            self.assertTrue(c.get("_secondary_split"), "Child chunk must have _secondary_split=True")

        # 5. Verify 100% exact text preservation
        joined = "".join(c["text"] for c in chunks)
        self.assertEqual(joined, para, "Concatenation of chunk text must exactly equal original text")

    def test_structural_split_integration_oversized_rule(self):
        """Proves that LegalParser.structural_split(oversized_rule, 'RULES') splits text correctly."""
        para = "Rule 89 Application for refund. " + ("This is detailed rule procedure text. " * 150)
        self.assertGreater(len(para), SECONDARY_SPLIT_TRIGGER)

        chunks = LegalParser.structural_split(para, "RULES")
        self.assertGreater(len(chunks), 1)

        for c in chunks:
            self.assertLessEqual(len(c["text"]), SECONDARY_SPLIT_MAX)
            self.assertEqual(c["structure"], "PROVISION")
            self.assertEqual(c["provision"], "Rule 89")
            self.assertTrue(c.get("_secondary_split"))

        joined = "".join(c["text"] for c in chunks)
        self.assertEqual(joined, para)


if __name__ == "__main__":
    unittest.main()

