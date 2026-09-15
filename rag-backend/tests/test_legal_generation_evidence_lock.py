"""
test_legal_generation_evidence_lock.py
---------------------------------------
Comprehensive regression test suite for Legal Generation Evidence Lock (V3):
1. test_zero_unsupported_citations_clean_pass
2. test_hallucinated_circular_blocked_or_repaired
3. test_statute_mismatch_flagged
4. test_rule_statute_identity
5. test_contradiction_detection
6. test_explicit_unretrieved_authority_insufficient_notice
7. test_case_law_discovery_not_blocked_by_missing_circulars
8. test_allowed_authorities_registry_format
9. test_context_builder_case_law_preservation
10. test_intent_guidance_classification
11. test_bullet_deterministic_repair
12. test_evidence_ledger_generation
13. test_no_hardcoded_authority_blacklists
14. test_token_budget_adaptive_caps
"""

import pytest
import asyncio
from app.retrieval.reference_resolver import ReferenceResolver, LegalReference
from app.generation.citation_validator import CitationValidator
from app.generation.context_builder import (
    build_canonical_authority_registry,
    format_allowed_authorities_block,
    build_context,
    select_generation_chunks,
)
from app.generation.synthesizer import (
    _determine_intent_guidance,
    _select_response_mode,
)
from app.generation.verification_pipeline import (
    run_verification_pipeline,
    verify_substantive_claim_support,
    VerificationResult,
)
import app.generation.prompt as prompt_mod


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_statute_chunk():
    return {
        "chunk_id": "c_sec16_1",
        "rel_path": "act/cgst_act_2017.pdf",
        "text": (
            "Section 16. Eligibility and conditions for taking input tax credit.-\n"
            "(1) Every registered person shall, subject to such conditions and restrictions as may be prescribed "
            "and in the manner specified in section 49, be entitled to take credit of input tax charged on any inward supply "
            "of goods or services or both to him which are used or intended to be used in the course or furtherance of his business."
        ),
        "metadata": {
            "provision_keys": ["CGST_SEC_16", "CGST_SEC_16(1)"],
            "rel_path": "act/cgst_act_2017.pdf",
        },
        "_evidence_authority": "CGST Act, 2017",
    }


@pytest.fixture
def sample_igst_chunk():
    return {
        "chunk_id": "c_igst_sec13_9",
        "rel_path": "act/igst_act_2017.pdf",
        "text": (
            "Section 13. Place of supply of services where location of supplier or location of recipient is outside India.-\n"
            "(9) The place of supply of the following services shall be the location of the supplier of services, namely:--\n"
            "(a) services supplied by a banking company, or a financial institution, or a non-banking financial company..."
        ),
        "metadata": {
            "provision_keys": ["IGST_SEC_13", "IGST_SEC_13(9)"],
            "rel_path": "act/igst_act_2017.pdf",
        },
        "_evidence_authority": "IGST Act, 2017",
    }


@pytest.fixture
def sample_cgst_rule_chunk():
    return {
        "chunk_id": "c_rule96",
        "rel_path": "rules/cgst_rules_2017.pdf",
        "text": (
            "Rule 96. Refund of integrated tax paid on goods or services exported out of India.-\n"
            "(1) The shipping bill filed by an exporter of goods shall be deemed to be an application for refund..."
        ),
        "metadata": {
            "provision_keys": ["CGST_RUL_96"],
            "rel_path": "rules/cgst_rules_2017.pdf",
        },
        "_evidence_authority": "CGST Rules, 2017",
    }


@pytest.fixture
def sample_blocked_credit_chunk():
    return {
        "chunk_id": "c_sec17_5",
        "rel_path": "act/cgst_act_2017.pdf",
        "text": (
            "Section 17. Apportionment of credit and blocked credits.-\n"
            "(5) Notwithstanding anything contained in sub-section (1) of section 16 and subsection (1) of section 18, "
            "input tax credit shall not be available in respect of the following, namely:-\n"
            "(d) goods or services or both received by a taxable person for construction of an immovable property "
            "(other than plant or machinery) on his own account including when such goods or services or both are used in the "
            "course or furtherance of business."
        ),
        "metadata": {
            "provision_keys": ["CGST_SEC_17", "CGST_SEC_17(5)", "CGST_SEC_17(5)(d)"],
            "rel_path": "act/cgst_act_2017.pdf",
        },
        "_evidence_authority": "CGST Act, 2017",
    }


@pytest.fixture
def sample_case_law_chunk():
    return {
        "chunk_id": "c_mohit_minerals",
        "rel_path": "cases/Mohit_Minerals_SC_2022.pdf",
        "text": (
            "Union of India v. Mohit Minerals Pvt. Ltd. (2022) 10 SCC 700 (Supreme Court).\n"
            "Held: Ocean freight on CIF import contracts cannot be subjected to IGST under reverse charge mechanism, "
            "as the Indian importer is not the recipient of maritime transportation service."
        ),
        "metadata": {
            "rel_path": "cases/Mohit_Minerals_SC_2022.pdf",
        },
        "_evidence_authority": "Supreme Court Precedent",
    }


# ── Tests ────────────────────────────────────────────────────────────────────

def test_zero_unsupported_citations_clean_pass(sample_statute_chunk):
    """Invariant 1: Clean answers referencing only retrieved evidence pass validation completely."""
    answer = (
        "Under Section 16(1) of the CGST Act, 2017, a registered person is entitled to take input tax credit "
        "on inward supplies used in the course or furtherance of business (S1)."
    )
    report = CitationValidator.audit_citations(answer, [sample_statute_chunk])
    assert report.is_valid is True
    assert report.verdict == "PASS"
    assert "Section 16(1) of CGST Act" in report.verified_citations
    assert len(report.unsupported_citations) == 0


def test_hallucinated_circular_blocked_or_repaired(sample_statute_chunk):
    """Invariant 2: When LLM introduces an unretrieved circular, it is repaired or blocked."""
    answer_with_hallu = (
        "Under Section 16(1) of the CGST Act, credit is available (S1).\n\n"
        "Further, Circular No. 241/2024 clarifies specific procedures."
    )
    result = asyncio.run(run_verification_pipeline(
        answer=answer_with_hallu,
        query="What are the conditions for ITC under Section 16(1)?",
        chunks=[sample_statute_chunk],
        context="",
        truth_rules_text="",
        marker_map=[{"marker": "[S1]", "chunk_id": "c_sec16_1"}],
        is_draft=False,
    ))
    # The peripheral hallucinated sentence has been dropped or gate blocked
    assert result.gate_verdict in ("REPAIR", "BLOCK")
    if result.gate_verdict == "REPAIR":
        assert "Circular" not in result.verified_answer
        assert "Section 16(1)" in result.verified_answer
    else:
        assert "Legal Integrity Notice" in result.verified_answer


def test_statute_mismatch_flagged(sample_igst_chunk):
    """Invariant 3: Claiming CGST Act when source chunk is IGST Act is flagged as STATUTE_MISMATCH."""
    sn_map = {"S1": sample_igst_chunk}
    claim = "Section 13(9) of the CGST Act provides that place of supply is location of supplier (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([sample_igst_chunk])
    
    chk = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert chk["statute_match"] is False
    assert any("STATUTE_MISMATCH" in iss for iss in chk["issues"])


def test_rule_statute_identity(sample_cgst_rule_chunk):
    """Invariant 4: Rule 96 attributed to IGST Rules is flagged as STATUTE_MISMATCH."""
    sn_map = {"S1": sample_cgst_rule_chunk}
    claim = "Under Rule 96 of the IGST Rules, refund of integrated tax is processed on shipping bill (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([sample_cgst_rule_chunk])

    chk = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert chk["statute_match"] is False
    assert any("Rule 96 belongs to CGST Rules" in iss for iss in chk["issues"])


def test_rule_statute_context_disambiguation():
    """Invariant 4b: Context mentioning IGST tax does not misclassify Rule 96/89 as IGST Rules."""
    # Context mentioning IGST tax should still resolve to CGST_RUL_96
    text_tax = "Refund of integrated tax (IGST) paid on zero-rated supply of goods under Rule 96."
    refs_tax = ReferenceResolver.resolve_references(text_tax)
    assert any(r.canonical_key == "CGST_RUL_96" for r in refs_tax)
    assert not any(r.canonical_key == "IGST_RUL_96" for r in refs_tax)

    # Explicit text attributing rule to IGST Rules correctly resolves to IGST_RUL_96
    text_hallu = "Under Rule 96 of the IGST Rules, exporter files form."
    refs_hallu = ReferenceResolver.resolve_references(text_hallu)
    assert any(r.canonical_key == "IGST_RUL_96" for r in refs_hallu)


def test_contradiction_detection(sample_blocked_credit_chunk):
    """Invariant 5: Asserting ITC is allowed when source chunk explicitly blocks it flags CONTRADICTION."""
    sn_map = {"S1": sample_blocked_credit_chunk}
    claim = "Under Section 17(5)(d), ITC is allowed for construction of immovable property on own account (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([sample_blocked_credit_chunk])

    chk = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert chk["supported"] is False
    assert any("CONTRADICTION" in iss for iss in chk["issues"])


def test_explicit_unretrieved_authority_insufficient_notice():
    """Invariant 6: Explicit request guidance mandates transparent insufficiency notice."""
    contract = prompt_mod._ASSOCIATE_STRUCTURE
    assert "EXPLICIT REQUESTS WITH MISSING EVIDENCE" in contract
    assert "The retrieved legal corpus does not contain documentation to substantiate" in contract


def test_case_law_discovery_not_blocked_by_missing_circulars(sample_case_law_chunk):
    """Invariant 7: Case law discovery answers citing only retrieved cases pass cleanly."""
    answer = (
        "In Union of India v. Mohit Minerals Pvt. Ltd., the Supreme Court held that "
        "ocean freight on CIF imports cannot be subjected to IGST under RCM (S1)."
    )
    report = CitationValidator.audit_citations(answer, [sample_case_law_chunk])
    assert report.is_valid is True
    assert report.verdict == "PASS"


def test_allowed_authorities_registry_format(sample_statute_chunk, sample_case_law_chunk):
    """Invariant 8: Canonical authority registry builds properly structured XML block."""
    registry = build_canonical_authority_registry([sample_statute_chunk, sample_case_law_chunk])
    assert len(registry) == 2
    assert registry[0]["marker"] == "[S1]"
    assert registry[0]["authority_tier"] == "STATUTE"
    assert "CGST_SEC_16" in registry[0]["canonical_keys"]

    assert registry[1]["marker"] == "[S2]"
    assert registry[1]["authority_tier"] == "CASE_LAW"

    xml_block = format_allowed_authorities_block(registry)
    assert "<allowed_authorities>" in xml_block
    assert "</allowed_authorities>" in xml_block
    assert "[S1] [STATUTE]" in xml_block
    assert "[S2] [CASE_LAW]" in xml_block


def test_context_builder_case_law_preservation(sample_case_law_chunk, sample_statute_chunk):
    """Invariant 9: When query asks for case law, select_generation_chunks prioritizes case law."""
    chunks = [sample_statute_chunk, sample_case_law_chunk]
    selected = select_generation_chunks(chunks, query="hey leta provide me some case law on ITC?")
    assert len(selected) > 0
    # Case law chunk must be preserved in selection
    assert any(c["chunk_id"] == "c_mohit_minerals" for c in selected)


def test_intent_guidance_classification():
    """Invariant 10: Intent guidance accurately maps queries to specialized instructions."""
    g_case = _determine_intent_guidance("hey leta provide me some case law on ITC?")
    assert g_case["intent_type"] == "CASE_LAW_DISCOVERY"

    g_prov = _determine_intent_guidance("What does Section 17(5)(d) state regarding construction?")
    assert g_prov["intent_type"] == "SPECIFIC_PROVISION"

    g_exp = _determine_intent_guidance("Explain Rule 96 refund on zero rated supply")
    assert g_exp["intent_type"] == "EXPORT_REFUND"

    g_top = _determine_intent_guidance("What are the comprehensive ITC conditions?")
    assert g_top["intent_type"] == "BROAD_TOPICAL"

    g_gen = _determine_intent_guidance("Hello what is GST?")
    assert g_gen["intent_type"] == "GENERAL_INQUIRY"


def test_bullet_deterministic_repair(sample_statute_chunk):
    """Invariant 11: Deterministic repair drops an unsupported bullet without breaking list structure."""
    answer = (
        "**LEGAL POSITION**\n\n"
        "• Section 16(1) of the CGST Act allows registered persons to claim ITC on business inputs (S1).\n"
        "• Circular No. 999/2024 restricts certain claims.\n"
        "• All tax payments must be remitted as specified under section 49 (S1)."
    )
    result = asyncio.run(run_verification_pipeline(
        answer=answer,
        query="What are the conditions for ITC under Section 16(1)?",
        chunks=[sample_statute_chunk],
        context="",
        truth_rules_text="",
        marker_map=[{"marker": "[S1]", "chunk_id": "c_sec16_1"}],
        is_draft=False,
    ))
    assert result.gate_verdict == "REPAIR"
    assert "Circular No. 999" not in result.verified_answer
    assert "Section 16(1)" in result.verified_answer
    assert "•" in result.verified_answer  # Bullet formatting preserved


def test_evidence_ledger_generation(sample_statute_chunk):
    """Invariant 12: run_verification_pipeline generates an evidence ledger with claim evaluations."""
    answer = "Under Section 16(1) of the CGST Act, ITC is available for business inputs (S1)."
    result = asyncio.run(run_verification_pipeline(
        answer=answer,
        query="Section 16(1) conditions",
        chunks=[sample_statute_chunk],
        context="",
        truth_rules_text="",
        marker_map=[{"marker": "[S1]", "chunk_id": "c_sec16_1"}],
        is_draft=False,
    ))
    assert len(result.evidence_ledger) > 0
    item = result.evidence_ledger[0]
    assert "(S1)" in item["markers"]
    assert item["statute_match"] is True
    assert item["supported"] is True


def test_no_hardcoded_authority_blacklists():
    """Invariant 13: System prompt and code do NOT contain hardcoded lists of prohibited sections."""
    import inspect
    prompt_code = inspect.getsource(prompt_mod)
    # Ensure there are no hardcoded blacklists of sections
    assert "Never append Sections 73, 74, 50" not in prompt_code
    assert "Sections 73/74/50 as prohibited" not in prompt_code


def test_token_budget_adaptive_caps():
    """Invariant 14: Response mode selection returns tuned adaptive token caps."""
    mode_brief, _, cap_brief = _select_response_mode(0.1)
    mode_std, _, cap_std = _select_response_mode(0.5)
    mode_det, _, cap_det = _select_response_mode(0.9)

    assert cap_brief == 2000
    assert cap_std == 3500
    assert cap_det == 5000
