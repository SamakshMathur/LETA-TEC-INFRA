"""
test_launch_readiness_intent.py
-------------------------------
Comprehensive regression tests for Launch Readiness:
1. Intent-aware authority coverage verification (Discovery vs Explicit vs Comprehensive)
2. Directional Parent / Child Specificity Matrix (Sections and Rules)
3. Evidence-aware token budgeting and context deduplication
4. Runtime retrieval trace taxonomy recording
"""

import pytest
from app.retrieval.reference_resolver import ReferenceResolver, LegalReference
from app.retrieval.query_refiner import verify_answer_authority_coverage
from app.generation.citation_validator import CitationValidator
from app.generation.context_builder import (
    select_generation_chunks,
    build_context,
    build_marker_map,
    MAX_EVIDENCE_TOKENS,
)
from app.retrieval.retrieval_trace import RetrievalTrace


# ─────────────────────────────────────────────────────────────────────────────
# 1. Intent-Aware Authority Coverage
# ─────────────────────────────────────────────────────────────────────────────

def test_case_law_discovery_intent_does_not_mandate_unrelated_statutory_rules():
    """Discovery query 'provide case law on ITC' must not fail because it omitted Rule 42/43."""
    query = "hey leta provide me some case law on ITC?"
    answer = (
        "In Bharti Airtel Ltd. v. Union of India, the Supreme Court held that ITC is a statutory right. "
        "Further, in Safari Retreats Pvt. Ltd., the High Court considered Section 17(5)(d)."
    )
    taxonomy = {
        "topics": ["itc"],
        "confidence": 0.9,
        "sections": ["CGST_SEC_16", "CGST_SEC_17", "CGST_SEC_18"],
        "rules": ["CGST_RUL_42", "CGST_RUL_43", "CGST_RUL_44", "CGST_RUL_36"],
        "circulars": ["CIRCULAR_123", "CIRCULAR_167"],
    }
    cov = verify_answer_authority_coverage(query, answer, taxonomy, {})
    assert cov["verdict"] == "pass"
    assert len(cov["missing"]) == 0


def test_circular_discovery_intent_does_not_mandate_unrelated_rules():
    """Circular discovery query does not mandate unrequested background sections."""
    query = "show circulars dealing with refunds on inverted duty structure"
    answer = "Circular No. 135/05/2020 clarified refund admissibility under inverted duty structure."
    taxonomy = {
        "topics": ["refund"],
        "confidence": 0.85,
        "sections": ["CGST_SEC_54", "CGST_SEC_50"],
        "rules": ["CGST_RUL_89", "CGST_RUL_96"],
        "circulars": ["CIRCULAR_135", "CIRCULAR_125"],
    }
    cov = verify_answer_authority_coverage(query, answer, taxonomy, {})
    assert cov["verdict"] == "pass"
    assert len(cov["missing"]) == 0


def test_comprehensive_statutory_analysis_intent_preserves_mandatory_coverage():
    """Query explicitly requesting comprehensive statutory analysis evaluates statutory coverage."""
    query = "give a comprehensive analysis of all provisions and rules governing ITC eligibility and apportionment"
    answer = "Under Section 16 of the CGST Act, registered persons can claim ITC."
    taxonomy = {
        "topics": ["itc"],
        "confidence": 0.9,
        "sections": ["CGST_SEC_16", "CGST_SEC_17", "CGST_SEC_18"],
        "rules": ["CGST_RUL_42", "CGST_RUL_43"],
        "circulars": [],
    }
    cov = verify_answer_authority_coverage(query, answer, taxonomy, {})
    # Answer only mentioned Section 16, missed 17, 18, Rule 42, Rule 43 (4 out of 5 missing)
    assert cov["verdict"] == "fail"
    assert "CGST_SEC_17" in cov["missing"]
    assert "CGST_RUL_42" in cov["missing"]


def test_explicit_authority_target_preserves_strict_mention_requirement():
    """Query explicitly citing Section 17(5)(d) mandates Section 17(5)(d)."""
    query = "Explain Section 17(5)(d) of the CGST Act regarding construction expenses."
    answer_with_sec = "Section 17(5)(d) of the CGST Act blocks ITC on goods received for construction of immovable property."
    taxonomy = {
        "topics": ["itc"],
        "confidence": 0.9,
        "sections": ["CGST_SEC_16", "CGST_SEC_17"],
        "rules": ["CGST_RUL_42"],
        "circulars": [],
    }
    cov = verify_answer_authority_coverage(query, answer_with_sec, taxonomy, {})
    assert cov["verdict"] == "pass"
    assert "CGST_SEC_17(5)(d)" in cov["cited"]

    answer_without_sec = "Construction expenses are blocked from ITC eligibility under the law."
    cov_missing = verify_answer_authority_coverage(query, answer_without_sec, taxonomy, {})
    assert cov_missing["verdict"] == "fail"
    assert "CGST_SEC_17(5)(d)" in cov_missing["missing"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Parent / Child Reference Specificity Matrix
# ─────────────────────────────────────────────────────────────────────────────

def test_parent_child_rule_86a():
    """Evidence Rule 86A(1) -> Claim Rule 86A -> PASS."""
    avail = [LegalReference(ref_type="RULE", statute="CGST", provision_num="86A", subsection="1")]
    cited = LegalReference(ref_type="RULE", statute="CGST", provision_num="86A", subsection=None)
    matched, _ = ReferenceResolver.verify_citation_against_evidence(cited, avail)
    assert matched is True


def test_parent_child_section_17_5_a_supports_17_5():
    """Evidence Section 17(5)(a) -> Claim Section 17(5) -> PASS."""
    avail = [LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5", clause="a")]
    cited = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5")
    matched, _ = ReferenceResolver.verify_citation_against_evidence(cited, avail)
    assert matched is True


def test_parent_child_section_17_5_a_fails_17_5_d():
    """Evidence Section 17(5)(a) -> Claim Section 17(5)(d) -> FAIL."""
    avail = [LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5", clause="a")]
    cited = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5", clause="d")
    matched, _ = ReferenceResolver.verify_citation_against_evidence(cited, avail)
    assert matched is False


def test_parent_child_section_17_2_fails_17_5():
    """Evidence Section 17(2) -> Claim Section 17(5) -> FAIL."""
    avail = [LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="2")]
    cited = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5")
    matched, _ = ReferenceResolver.verify_citation_against_evidence(cited, avail)
    assert matched is False


def test_parent_child_section_17_5_supports_section_17():
    """Evidence Section 17(5) -> Claim Section 17 -> PASS."""
    avail = [LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5")]
    cited = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection=None)
    matched, _ = ReferenceResolver.verify_citation_against_evidence(cited, avail)
    assert matched is True


def test_parent_child_section_17_5_fails_section_16():
    """Evidence Section 17(5) -> Claim Section 16 -> FAIL."""
    avail = [LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5")]
    cited = LegalReference(ref_type="SECTION", statute="CGST", provision_num="16", subsection=None)
    matched, _ = ReferenceResolver.verify_citation_against_evidence(cited, avail)
    assert matched is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Context Selection & Token Budgeting
# ─────────────────────────────────────────────────────────────────────────────

def test_context_budget_driven_selection():
    """Chunk selection accumulates up to budget without arbitrary chunk limits."""
    # Create 20 chunks of 500 tokens (2,000 chars) each
    synthetic_chunks = [
        {
            "chunk_id": f"chunk_{i}",
            "rel_path": f"acts/act_part_{i}.pdf",
            "text": f"Section {i} substantive text. " + ("Legal provisions content. " * 80),
            "metadata": {"category": "statute", "rel_path": f"acts/act_part_{i}.pdf"},
            "_evidence_role": "primary_legislation",
        }
        for i in range(20)
    ]
    selected = select_generation_chunks(synthetic_chunks, query="statutory compliance rules", is_draft=False)
    # Total tokens should not exceed MAX_EVIDENCE_TOKENS (7500)
    total_tokens = sum(len(c["text"]) // 4 for c in selected)
    assert total_tokens <= MAX_EVIDENCE_TOKENS
    assert len(selected) > 0

    # Build context block and check markers
    context_str = build_context(selected)
    assert "[S1]" in context_str
    assert f"[S{len(selected)}]" in context_str


# ─────────────────────────────────────────────────────────────────────────────
# 4. Retrieval Trace Taxonomy Integrity
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieval_trace_taxonomy_recording():
    """Verify trace accurately reflects runtime taxonomy topics and confidence."""
    trace = RetrievalTrace(query_id="test_query_001", query="case law on ITC")
    runtime_tax = {
        "topics": ["itc"],
        "confidence": 0.95,
        "sections": ["CGST_SEC_16"],
        "rules": ["CGST_RUL_36"],
        "circulars": [],
    }

    # Simulate retriever recording runtime taxonomy
    trace.preprocessing["taxonomy"] = runtime_tax
    trace.preprocessing["topic"] = runtime_tax["topics"][0]

    trace_dict = trace.to_log_dict()
    assert trace_dict["taxonomy_topics"] == ["itc"]
    assert trace_dict["taxonomy_conf"] == 0.95
    assert trace_dict["topic"] == "itc"
