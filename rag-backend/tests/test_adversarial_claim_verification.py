import pytest
from app.generation.verification_pipeline import verify_substantive_claim_support
from app.retrieval.reference_resolver import ReferenceResolver, LegalReference

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures for Adversarial Grounding Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def chunk_section_13_igst():
    return {
        "rel_path": "Database_V2.0/IGST Acts/IGST Act.pdf",
        "source": "Database_V2.0/IGST Acts/IGST Act.pdf",
        "metadata": {
            "provision_keys": ["IGST_SEC_13"],
            "section_label": "section 13",
        },
        "text": (
            "Section - 13, Integrated Goods And Services Tax Act, 2017. "
            "(8) The place of supply of the following services shall be the location "
            "of the supplier of services, namely:— (a) services supplied by a banking company, "
            "or a financial institution, or a non-banking financial company, to account holders; "
            "(9) 26b[***]"
        )
    }

@pytest.fixture
def chunk_rule_96_cgst():
    return {
        "rel_path": "Database_V2.0/CGST Rules 10-08-2026/Rule 96.pdf",
        "source": "Database_V2.0/CGST Rules 10-08-2026/Rule 96.pdf",
        "metadata": {
            "provision_keys": ["CGST_RUL_96"],
            "section_label": "rule 96",
        },
        "text": (
            "Rule - 96 , Central Goods and Services Tax Rules, 2017. "
            "Refund of integrated tax paid on goods or services exported out of India. "
            "(1) The shipping bill filed by an exporter of goods shall be deemed to be an application for refund."
        )
    }

@pytest.fixture
def chunk_section_17_5_blocked():
    return {
        "rel_path": "Database_V2.0/CGST Acts/Chapter V Input Tax Credit (ITC) (Sections 16–21).pdf",
        "source": "Database_V2.0/CGST Acts/Chapter V Input Tax Credit (ITC) (Sections 16–21).pdf",
        "metadata": {
            "provision_keys": ["CGST_SEC_17"],
            "section_label": "section 17",
        },
        "text": (
            "17. (5) Notwithstanding anything contained in sub-section (1) of section 16 and subsection (1) of section 18, "
            "input tax credit shall not be available in respect of the following, namely:— "
            "(d) goods or services or both received by a taxable person for construction of an immovable property "
            "(other than plant or machinery) on his own account including when such goods or services or both are used "
            "in the course or furtherance of business."
        )
    }

@pytest.fixture
def chunk_section_16_2_d():
    return {
        "rel_path": "Database_V2.0/CGST Acts/Chapter V Input Tax Credit (ITC) (Sections 16–21).pdf",
        "source": "Database_V2.0/CGST Acts/Chapter V Input Tax Credit (ITC) (Sections 16–21).pdf",
        "metadata": {
            "provision_keys": ["CGST_SEC_16"],
            "section_label": "section 16",
        },
        "text": (
            "Section 16. Eligibility and conditions for taking input tax credit. "
            "(2) Notwithstanding anything contained in this section, no registered person shall be entitled "
            "to the credit of any input tax in respect of any supply of goods or services or both to him unless,— "
            "(d) he has furnished the return under section 39."
        )
    }

# ─────────────────────────────────────────────────────────────────────────────
# 11 Adversarial Tests Required by User
# ─────────────────────────────────────────────────────────────────────────────

def test_adversarial_1_statute_swap(chunk_section_13_igst):
    """
    Test 1 — Statute Swap
    Evidence: Section 13(9) IGST Act (S1)
    Generated: Section 13(9) CGST Act (S1) -> FAIL (STATUTE_MISMATCH)
    """
    sn_map = {"S1": chunk_section_13_igst}
    claim = "Under Section 13(9) of the CGST Act, banking services place of supply is determined (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([chunk_section_13_igst])

    res = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert res["statute_match"] is False
    assert res["supported"] is False
    assert any("STATUTE_MISMATCH" in iss for iss in res["issues"])


def test_adversarial_2_rule_swap(chunk_rule_96_cgst):
    """
    Test 2 — Rule Swap
    Evidence: Rule 96 CGST Rules (S1)
    Generated: Rule 96 IGST Rules (S1) -> FAIL (STATUTE_MISMATCH)
    """
    sn_map = {"S1": chunk_rule_96_cgst}
    claim = "Under Rule 96 of the IGST Rules, the exporter files a shipping bill (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([chunk_rule_96_cgst])

    res = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert res["statute_match"] is False
    assert res["supported"] is False
    assert any("STATUTE_MISMATCH" in iss for iss in res["issues"])


def test_adversarial_3_contradictory_proposition(chunk_section_17_5_blocked):
    """
    Test 3 — Contradictory Proposition
    Evidence: ITC is blocked under Section 17(5)(d).
    Generated: ITC is available under Section 17(5)(d) for construction on own account (S1) -> FAIL (CONTRADICTION)
    """
    sn_map = {"S1": chunk_section_17_5_blocked}
    claim = "Under Section 17(5)(d), ITC is available for construction of immovable property on own account (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([chunk_section_17_5_blocked])

    res = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert res["supported"] is False
    assert any("CONTRADICTION" in iss for iss in res["issues"])


def test_adversarial_4_same_authority_unsupported_proposition(chunk_section_17_5_blocked):
    """
    Test 4 — Same Authority, Unsupported Proposition
    Evidence: Section 17(5)(d) blocks credit on construction on own account.
    Generated: Section 17(5)(d) creates an unrestricted entitlement to credit on immovable property (S1) -> FAIL
    """
    sn_map = {"S1": chunk_section_17_5_blocked}
    claim = "Section 17(5)(d) creates an unrestricted entitlement to ITC for all construction expenses (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([chunk_section_17_5_blocked])

    res = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert res["supported"] is False
    assert any("UNSUPPORTED_PROPOSITION" in iss or "CONTRADICTION" in iss for iss in res["issues"])


def test_adversarial_5_marker_laundering(chunk_section_17_5_blocked):
    """
    Test 5 — Marker Laundering
    Evidence: [S1] Section 17(5)(d)
    Generated: Section 73 applies and imposes penalty for non-compliance (S1) -> FAIL
    Attaching valid marker (S1) to completely ungrounded legal section (Section 73) must FAIL.
    """
    sn_map = {"S1": chunk_section_17_5_blocked}
    claim = "Section 73 applies and imposes a mandatory penalty for non-compliance (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([chunk_section_17_5_blocked])

    res = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert res["supported"] is False
    assert any("MARKER_LAUNDERING" in iss for iss in res["issues"])


def test_adversarial_6_parent_child_specificity():
    """
    Test 6 — Parent / Child Specificity Invariant Matrix
    """
    ref_sec17_5_a = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5", clause="a")
    ref_sec17_5 = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5")
    ref_sec17_5_d = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17", subsection="5", clause="d")
    ref_sec17 = LegalReference(ref_type="SECTION", statute="CGST", provision_num="17")
    ref_sec16 = LegalReference(ref_type="SECTION", statute="CGST", provision_num="16")

    # Available: 17(5)(a). Claim: 17(5) -> PASS (child satisfies parent claim)
    assert ref_sec17_5_a.is_exact_or_child_of(ref_sec17_5) is True

    # Available: 17(5)(a). Claim: 17(5)(d) -> FAIL (sibling clause mismatch)
    assert ref_sec17_5_a.is_exact_or_child_of(ref_sec17_5_d) is False

    # Available: 17(5)(a). Claim: 17 -> PASS (child satisfies broad section)
    assert ref_sec17_5_a.is_exact_or_child_of(ref_sec17) is True

    # Available: 17(5). Claim: 16 -> FAIL (different section)
    assert ref_sec17_5.is_exact_or_child_of(ref_sec16) is False


def test_adversarial_7_cross_reference_vs_direct_authority(chunk_section_16_2_d):
    """
    Test 7 — Statutory Cross-Reference vs Direct Authority
    Evidence: Section 16(2)(d) mentions return under section 39.
    Claim 1: States statutory condition -> PASS
    Claim 2: Asserts detailed operational rules of section 39 without direct chunk -> FAIL
    """
    sn_map = {"S1": chunk_section_16_2_d}
    avail = ReferenceResolver.extract_available_chunk_references([chunk_section_16_2_d])

    # Claim 1: Statutory condition
    claim_cond = "Under Section 16(2)(d), the registered person must furnish the return under section 39 (S1)."
    refs_cond = ReferenceResolver.resolve_references(claim_cond)
    res_cond = verify_substantive_claim_support(claim_cond, refs_cond, avail, sn_map)
    assert res_cond["supported"] is True

    # Claim 2: Substantive operational rules for Section 39
    claim_op = "Section 39 mandates filing within the due date with mandatory penalty (S1)."
    refs_op = ReferenceResolver.resolve_references(claim_op)
    res_op = verify_substantive_claim_support(claim_op, refs_op, avail, sn_map)
    assert res_op["supported"] is False
    assert any("CROSS_REFERENCE_NOT_DIRECT" in iss or "MARKER_LAUNDERING" in iss for iss in res_op["issues"])


def test_adversarial_8_chunk_continuation_heading_resolution():
    """
    Test 8 — Chunk Continuation Heading Resolution
    Continuation chunk with inherited IGST_SEC_13 resolves Section 13(8)(a) and 13(9).
    """
    continuation_chunk = {
        "rel_path": "Database_V2.0/IGST Acts/IGST Act.pdf",
        "metadata": {
            "provision_keys": ["IGST_SEC_13"],
            "section_label": "section 13",
        },
        "text": (
            "as may be prescribed. (8) The place of supply of the following services shall be the location "
            "of the supplier of services, namely:— (a) services supplied by a banking company, "
            "or a financial institution, or a non-banking financial company, to account holders; "
            "(9) 26b[***]"
        )
    }
    avail = ReferenceResolver.extract_available_chunk_references([continuation_chunk])
    canonical_keys = [r.canonical_key for r in avail]

    assert "IGST_SEC_13" in canonical_keys
    assert "IGST_SEC_13(8)" in canonical_keys
    assert "IGST_SEC_13(8)(a)" in canonical_keys
    assert "IGST_SEC_13(9)" in canonical_keys


def test_adversarial_9_circular_document_identity():
    """
    Test 9 — Circular Document-Level Identity
    Chunks with normalized circular filenames resolve their circular number canonical key.
    """
    sample_circular_chunks = [
        {"rel_path": "Database_V2.0/circulars(2017-2025)/2018/circularno-37-cgst.pdf", "text": "LUT procedures for export."},
        {"rel_path": "Database_V2.0/circulars(2017-2025)/2024/Circular-No-241-2024.pdf", "text": "Clarification on ITC."},
        {"rel_path": "Database_V2.0/circulars(2017-2025)/2022/cir-170-02-2022-cgst.pdf", "text": "Mandatory reporting in GSTR-3B."},
    ]
    avail = ReferenceResolver.extract_available_chunk_references(sample_circular_chunks)
    canonical_keys = [r.canonical_key for r in avail]

    assert "CIRCULAR_37" in canonical_keys
    assert "CIRCULAR_241" in canonical_keys
    assert "CIRCULAR_170" in canonical_keys


def test_adversarial_10_statute_context_propagation():
    """
    Test 10 — Statute Context Propagation
    In an IGST context, unanchored provision mentions resolve to IGST, avoiding phantom CGST citations.
    """
    text = (
        "Under Section 13(8)(a) of the IGST Act, the place of supply for banking services is the "
        "location of the supplier. Banking services are therefore expressly placed under Section 13(8)(a), "
        "not Section 13(9)."
    )
    refs = ReferenceResolver.resolve_references(text)
    canonical_keys = [r.canonical_key for r in refs]

    assert "IGST_SEC_13(8)(a)" in canonical_keys
    assert "IGST_SEC_13(9)" in canonical_keys
    # Zero phantom CGST citations
    assert not any(k.startswith("CGST_SEC_13") for k in canonical_keys)


def test_adversarial_11_valid_direct_claim(chunk_section_13_igst):
    """
    Test 11 — Valid Direct Claim
    Accurate claim supported by evidence passes cleanly without issues.
    """
    sn_map = {"S1": chunk_section_13_igst}
    claim = "Under Section 13(8)(a) of the IGST Act, the place of supply for banking services is the location of the supplier (S1)."
    refs = ReferenceResolver.resolve_references(claim)
    avail = ReferenceResolver.extract_available_chunk_references([chunk_section_13_igst])

    res = verify_substantive_claim_support(claim, refs, avail, sn_map)
    assert res["supported"] is True
    assert res["statute_match"] is True
    assert len(res["issues"]) == 0
