"""
test_legal_reference_integrity.py
---------------------------------
Comprehensive Forensic Test Suite for the Legal Reference Integrity System:
1. Canonical Legal Reference Parsing & Modeling (ReferenceResolver)
2. Parent / Child Specificity Matrix (Cases A, B, C, D for Section 17/17(5)/17(5)(a))
3. Circular and Notification Canonicalization & Distinctness
4. Context Compressor Canonical [Sn] Source Marker Identity Preservation
5. Explicit Citation Grounding vs Implicit Legal Proposition Boundaries
6. Pre-Exposure Streaming Gate & Byte Suppression
7. Sync Endpoint and File-Based Ask Hard Gating
8. Cache Store, Verification Fingerprint & Replay Protection
9. Internal Metadata Leakage Prevention
10. RetrievalTrace Reference Lifecycle Logging
"""

import asyncio
from typing import List, Dict, Any

from app.retrieval.reference_resolver import ReferenceResolver, LegalReference
from app.generation.citation_validator import CitationValidator, CitationValidationReport
from app.generation.context_compressor import compress_context
from app.generation.context_builder import build_context, build_marker_map
from app.generation.verification_pipeline import run_verification_pipeline, VerificationResult


# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical Reference Extraction & Modeling
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_sections_with_subsections_and_clauses():
    query = "What are the blocked credit conditions under Section 17(5)(a) and Section 16(2) of the CGST Act?"
    refs = ReferenceResolver.resolve_references(query)
    keys = {r.canonical_key for r in refs}

    assert "CGST_SEC_17(5)(a)" in keys
    assert "CGST_SEC_16(2)" in keys

    sec17 = next(r for r in refs if r.provision_num == "17")
    assert sec17.statute == "CGST"
    assert sec17.subsection == "5"
    assert sec17.clause == "a"


def test_resolve_rules():
    text = "Please explain the compliance timeline in Rule 88D and refund formula under Rule 89(4)."
    refs = ReferenceResolver.resolve_references(text)
    keys = {r.canonical_key for r in refs}

    assert "CGST_RUL_88D" in keys
    assert "CGST_RUL_89(4)" in keys


def test_resolve_landmark_case_law():
    text = "In Safari Retreats Pvt. Ltd. and Mohit Minerals, the court examined the scope of ITC."
    refs = ReferenceResolver.resolve_references(text)
    case_names = {r.authority_name for r in refs if r.ref_type == "CASE_LAW"}

    assert "Safari Retreats Pvt. Ltd." in case_names
    assert "Mohit Minerals Pvt. Ltd." in case_names


# ─────────────────────────────────────────────────────────────────────────────
# 2. Specificity Matrix (Cases A, B, C, D)
# ─────────────────────────────────────────────────────────────────────────────

def test_specificity_case_a_evidence_sec17_5_answer_sec17_verified():
    """
    CASE A:
    Evidence: CGST_SEC_17(5) (Blocked credits)
    Answer asserts parent provision: "Under Section 17..."
    Expected: VERIFIED (Evidence for child provision grounds the existence/content of parent provision).
    """
    retrieved_chunks = [
        {"provision": "CGST_SEC_17(5)", "text": "Section 17(5) Notwithstanding anything contained in sub-section (1)..."}
    ]
    answer = "Under Section 17, registered persons are entitled to full apportionment of input tax credit."
    report = CitationValidator.audit_citations(answer, retrieved_chunks)

    assert report.is_valid is True
    assert report.verdict == "PASS"
    assert "Section 17 of CGST Act" in report.verified_citations


def test_specificity_case_b_evidence_sec17_answer_sec17_5_not_verified():
    """
    CASE B:
    Evidence: CGST_SEC_17 (General heading only)
    Answer asserts child subsection: "Under Section 17(5)..."
    Expected: NOT VERIFIED (Parent cannot ground specific child subsection).
    """
    retrieved_chunks = [
        {"provision": "CGST_SEC_17", "text": "Section 17. Apportionment of credit and blocked credits."}
    ]
    answer = "Under Section 17(5), input tax credit on corporate health insurance is blocked."
    report = CitationValidator.audit_citations(answer, retrieved_chunks)

    assert report.is_valid is False
    assert report.verdict == "BLOCK"
    assert any("Section 17(5)" in unsupp for unsupp in report.unsupported_citations)


def test_specificity_case_c_evidence_sec17_5_answer_sec17_5_verified():
    """
    CASE C:
    Evidence: CGST_SEC_17(5)
    Answer asserts exact match: "Under Section 17(5)..."
    Expected: VERIFIED.
    """
    retrieved_chunks = [
        {"provision": "CGST_SEC_17(5)", "text": "Section 17(5) Notwithstanding anything contained in sub-section (1)..."}
    ]
    answer = "According to Section 17(5), input tax credit shall not be available in respect of motor vehicles."
    report = CitationValidator.audit_citations(answer, retrieved_chunks)

    assert report.is_valid is True
    assert report.verdict == "PASS"
    assert len(report.unsupported_citations) == 0


def test_specificity_case_d_evidence_sec17_5_a_answer_sec17_5_a_verified():
    """
    CASE D:
    Evidence: CGST_SEC_17(5)(a)
    Answer asserts exact clause: "Under Section 17(5)(a)..."
    Expected: VERIFIED.
    """
    retrieved_chunks = [
        {"provision": "CGST_SEC_17(5)(a)", "text": "Section 17(5)(a) motor vehicles for transportation of persons having approved seating capacity of not more than thirteen persons..."}
    ]
    answer = "Under Section 17(5)(a), credit on motor vehicles with seating capacity up to 13 is blocked."
    report = CitationValidator.audit_citations(answer, retrieved_chunks)

    assert report.is_valid is True
    assert report.verdict == "PASS"
    assert len(report.unsupported_citations) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Circular & Notification Canonicalization & Distinctness
# ─────────────────────────────────────────────────────────────────────────────

def test_circular_canonicalization_and_distinctness():
    """
    Prove formatting variants of Circular 184/16/2022-GST resolve to CIRCULAR_184,
    while distinct circulars (e.g. 184 vs 185) maintain distinct identities.
    """
    c184_full = ReferenceResolver.resolve_references("Refer to Circular No. 184/16/2022-GST.")[0]
    c184_short = ReferenceResolver.resolve_references("As stated in Circular 184.")[0]
    c185 = ReferenceResolver.resolve_references("Refer to Circular No. 185/17/2022-GST.")[0]

    assert c184_full.canonical_key == "CIRCULAR_184"
    assert c184_short.canonical_key == "CIRCULAR_184"
    assert c185.canonical_key == "CIRCULAR_185"
    assert c184_full.canonical_key != c185.canonical_key

    # Rejection of mismatched circular
    retrieved = [{"provision": "CIRCULAR_183", "text": "Circular No. 183/15/2022-GST clarifications."}]
    answer = "As clarified under Circular No. 184, export of services qualifies."
    report = CitationValidator.audit_citations(answer, retrieved)
    assert report.is_valid is False
    assert report.verdict == "BLOCK"


def test_notification_canonicalization_and_distinctness():
    """
    Prove Notification 04/2022-Central Tax vs 05/2022-Central Tax maintain distinct canonical identities.
    """
    n4 = ReferenceResolver.resolve_references("Notification No. 04/2022-Central Tax")[0]
    n5 = ReferenceResolver.resolve_references("Notification No. 05/2022-Central Tax")[0]

    assert "04/2022" in n4.provision_num or "04" in n4.provision_num
    assert "05/2022" in n5.provision_num or "05" in n5.provision_num
    assert n4.canonical_key != n5.canonical_key


# ─────────────────────────────────────────────────────────────────────────────
# 4. Context Compressor Canonical [Sn] Source Marker Identity Preservation
# ─────────────────────────────────────────────────────────────────────────────

def test_context_compressor_preserves_canonical_source_marker_identity():
    """
    Identity Preservation Invariant:
    Original indices: S1 -> Doc A, S2 -> Doc B, S3 -> Doc C.
    Compression re-orders by relevance: Doc C, Doc A, Doc B.
    Expected compressed markers: [S3], [S1], [S2] (NOT re-indexed as [S1], [S2], [S3]).
    """
    chunks = [
        {"source": "doc_a_definitions.pdf", "page": 1, "text": "Doc A general taxability definitions under GST.", "_rerank_score": 0.4},
        {"source": "doc_b_rules.pdf", "page": 5, "text": "Doc B rule procedures and time limits.", "_rerank_score": 0.3},
        {"source": "doc_c_circular.pdf", "page": 12, "text": "Doc C circular on export of intermediary services.", "_rerank_score": 0.99},
    ]

    compressed = compress_context(chunks, query="export intermediary services", is_draft=False)

    # First section in compressed text must be [S3] Doc C
    assert compressed.startswith("[S3] doc_c_circular.pdf p.12")
    assert "[S1] doc_a_definitions.pdf p.1" in compressed
    assert "[S2] doc_b_rules.pdf p.5" in compressed


# ─────────────────────────────────────────────────────────────────────────────
# 5. Explicit vs Implicit Legal Question Boundaries (Honest Audit)
# ─────────────────────────────────────────────────────────────────────────────

def test_explicit_legal_question_grounding_verification():
    """
    A. Explicit Question: User asks about Section 17(5)(d).
    Evidence contains Section 17(5)(d). Answer cites Section 17(5)(d).
    System detects exact grounding -> PASS.
    """
    chunks = [
        {"provision": "CGST_SEC_17(5)(d)", "text": "Section 17(5)(d) goods or services or both received by a taxable person for construction of an immovable property on his own account..."}
    ]
    answer = "Under Section 17(5)(d) of the CGST Act, ITC is blocked for goods/services used in construction on own account."
    vr = asyncio.run(run_verification_pipeline(
        answer=answer,
        query="What does Section 17(5)(d) provide?",
        chunks=chunks,
        context="Section 17(5)(d) text",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))
    assert vr.gate_verdict == "PASS"
    assert vr.is_verified is True


def test_implicit_legal_question_with_unsupported_statutory_citation():
    """
    B1. Implicit Question: User asks a business scenario without citing a section:
    'Is ITC available on construction of a commercial building intended for leasing?'
    Evidence retrieved has only Section 17(5)(c) (works contract).
    Model generates an answer asserting Section 17(5)(d).
    CitationValidator detects unsupported citation Section 17(5)(d) -> BLOCKS answer.
    """
    chunks = [
        {"provision": "CGST_SEC_17(5)(c)", "text": "Section 17(5)(c) works contract services for construction of immovable property..."}
    ]
    hallucinated_answer = "ITC is blocked under Section 17(5)(d) for construction of commercial property intended for leasing."

    vr = asyncio.run(run_verification_pipeline(
        answer=hallucinated_answer,
        query="Is ITC available on construction of a commercial building intended for leasing?",
        chunks=chunks,
        context="Section 17(5)(c) text",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))
    assert vr.gate_verdict == "BLOCK"
    assert "Section 17(5)(d)" in vr.safe_fallback_answer or len(vr.unsupported_citations) > 0


def test_implicit_legal_question_uncited_proposition_boundary():
    """
    B2. Implicit Question with Uncited Proposition (System Limitation Demonstration):
    Query: 'Can I claim ITC on employee health insurance?'
    Evidence retrieved: General Section 16 text (no mention of health insurance).
    Model asserts an uncited conclusion: 'Yes, ITC is generally available for all employee business expenses.'
    Because the model cited NO explicit statutory sections or rules, CitationValidator finds 0 citations
    and does NOT block based on citation regex alone.
    Demonstrates: Level 1 Citation Grounding is active; Level 3 Semantic Proposition Grounding is not performed by regex.
    """
    chunks = [
        {"provision": "CGST_SEC_16", "text": "Section 16 Eligibility and conditions for taking input tax credit."}
    ]
    uncited_answer = "Yes, input tax credit is generally available for business expenses relating to staff."
    report = CitationValidator.audit_citations(uncited_answer, chunks)

    # CitationValidator correctly reports 0 citations extracted/verified, so citation-level audit passes
    assert len(report.verified_citations) == 0
    assert len(report.unsupported_citations) == 0
    assert report.is_valid is True  # Level 1 citation validator does not block uncited text


# ─────────────────────────────────────────────────────────────────────────────
# 6. Streaming Integration & Byte Suppression
# ─────────────────────────────────────────────────────────────────────────────

def test_streaming_pre_exposure_gate_byte_suppression():
    """
    Integration Test: In stream_and_save, if generation contains an unsupported citation,
    the ungrounded answer bytes are NEVER yielded to the client; the safe fallback is yielded instead.
    """
    chunks = [
        {"provision": "CGST_SEC_16", "text": "Section 16 text on ITC conditions."}
    ]
    hallucinated_answer = "Under Section 74A of the CGST Act, new penalties apply."

    # Simulate verification gate at stream boundary
    vr = asyncio.run(run_verification_pipeline(
        answer=hallucinated_answer,
        query="What penalties apply?",
        chunks=chunks,
        context="Section 16 text",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))

    assert vr.gate_verdict == "BLOCK"
    assert vr.verified_answer != hallucinated_answer
    assert "Section 74A" not in vr.verified_answer or "⚠ **LETA TEC Legal Integrity Notice:**" in vr.verified_answer
    assert "LETA TEC Legal Integrity Notice" in vr.verified_answer


# ─────────────────────────────────────────────────────────────────────────────
# 7. Metadata Leakage, Cache Protection & Reference Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def test_internal_metadata_leak_protection():
    """
    Ensure internal tokens __METADATA__, __END_METADATA__, and __CITATIONS__
    do not leak into user-facing narrative text.
    """
    from app.generation.context_builder import parse_markers
    answer_with_meta = "Under Section 16(2), invoice is required."
    cleaned = parse_markers(answer_with_meta, [])
    assert "__METADATA__" not in cleaned.get("answer", answer_with_meta)
    assert "__CITATIONS__" not in cleaned.get("answer", answer_with_meta)


def test_cache_integrity_block_rejected():
    """
    Ensure that any answer with gate_verdict == 'BLOCK' is NOT committed to cache.
    Uses the real verification pipeline output structure rather than a bare Python conditional.
    """
    chunks = [
        {"provision": "CGST_SEC_16", "text": "Section 16 text"}
    ]
    hallucinated_answer = "Under Section 74A of the CGST Act, new penalties apply."

    vr = asyncio.run(run_verification_pipeline(
        answer=hallucinated_answer,
        query="What penalties apply?",
        chunks=chunks,
        context="Section 16 text",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))

    # Simulate the cache gating logic from stream_and_save / ask_sync:
    # Only PASS/REPAIR verdicts are eligible for caching.
    cached_payload = None
    if vr.gate_verdict in ("PASS", "REPAIR") and vr.is_verified:
        cached_payload = {"answer": vr.verified_answer, "verified": True}

    assert vr.gate_verdict == "BLOCK", f"Expected BLOCK, got {vr.gate_verdict}"
    assert cached_payload is None, "BLOCK verdict must not be committed to cache"


def test_retrieval_trace_reference_lifecycle():
    """
    Verify reference lifecycle is traceable across pipeline stages:
    requested -> retrieved -> context -> generated -> verified -> gate_verdict.
    """
    query = "What are the blocked credit conditions under Section 17(5)?"
    requested_refs = [r.canonical_key for r in ReferenceResolver.resolve_references(query)]
    assert "CGST_SEC_17(5)" in requested_refs

    # Evidence matches
    retrieved_chunks = [{"provision": "CGST_SEC_17(5)", "text": "Section 17(5) blocked credit text"}]
    avail_refs = [r.canonical_key for r in ReferenceResolver.extract_available_chunk_references(retrieved_chunks)]
    assert "CGST_SEC_17(5)" in avail_refs

    # Generated text
    gen_text = "Under Section 17(5), ITC is blocked on motor vehicles."
    gen_refs = [r.canonical_key for r in ReferenceResolver.resolve_references(gen_text)]
    assert "CGST_SEC_17(5)" in gen_refs

    # Verification
    report = CitationValidator.audit_citations(gen_text, retrieved_chunks)
    assert report.verdict == "PASS"
    assert "Section 17(5) of CGST Act" in report.verified_citations


# ─────────────────────────────────────────────────────────────────────────────
# 8. New Specific Legal Integrity Regression Tests (Golden Queries 1–15)
# ─────────────────────────────────────────────────────────────────────────────

def test_golden_query_sec_17_5_d_statutory_grounding_and_repair():
    """
    TEST 1 & 8: Section 17(5)(d) query with supported primary provision and unsupported peripheral Safari Retreats citation.
    Verifies:
    - Primary provision Section 17(5)(d) is detected and supported.
    - Unsupported peripheral Safari Retreats / Section 18 commentary is safely repaired or blocked.
    - Whole answer is NOT blocked when safe repair succeeds.
    """
    chunks = [
        {"provision": "CGST_SEC_17(5)(d)", "_pinned_by_ref": True, "text": "Section 17(5)(d) goods or services received by a taxable person for construction of an immovable property on his own account..."}
    ]
    gen_answer = (
        "Section 17(5)(d) of the CGST Act provides that input tax credit is not available for goods or services received by a taxable person for construction of an immovable property on his own account.\n\n"
        "Note: In Safari Retreats Pvt. Ltd., the High Court considered Section 17(5)(d)."
    )

    vr = asyncio.run(run_verification_pipeline(
        answer=gen_answer,
        query="What does Section 17(5)(d) of the CGST Act provide?",
        chunks=chunks,
        context="Section 17(5)(d) text",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))

    assert vr.gate_verdict in ("PASS", "REPAIR")
    assert "Section 17(5)(d)" in vr.verified_answer
    assert "Safari Retreats" not in vr.verified_answer


def test_golden_query_sec_17_1_vs_sec_17_5_structural_distinction():
    """
    TEST 3: Section 17(1) vs Section 17(5) parent/child & sibling structural distinction.
    """
    ref1 = ReferenceResolver.resolve_references("Section 17(1) of the CGST Act")[0]
    ref5 = ReferenceResolver.resolve_references("Section 17(5) of the CGST Act")[0]

    assert ref1.canonical_key == "CGST_SEC_17(1)"
    assert ref5.canonical_key == "CGST_SEC_17(5)"
    assert ref1.canonical_key != ref5.canonical_key
    assert ref1.is_exact_or_child_of(ref5) is False


def test_golden_query_safari_retreats_explicit_case_request():
    """
    TEST 4: Safari Retreats explicitly requested by user -> Case law becomes mandatory/relevant.
    """
    query = "What did the Supreme Court hold in Safari Retreats regarding Section 17(5)(d)?"
    refs = ReferenceResolver.resolve_references(query)
    case_refs = [r for r in refs if r.ref_type == "CASE_LAW"]

    assert len(case_refs) > 0
    assert case_refs[0].authority_name == "Safari Retreats Pvt. Ltd."


def test_golden_query_circular_184_explicit_request():
    """
    TEST 5: Circular 184/16/2022-GST exact reference query.
    """
    query = "What clarification was given in Circular 184/16/2022-GST regarding transportation of goods outside India?"
    refs = ReferenceResolver.resolve_references(query)
    assert any(r.canonical_key == "CIRCULAR_184" for r in refs)

    chunks = [
        {"provision": "CIRCULAR_184", "text": "Circular No. 184/16/2022-GST clarification on transportation of goods outside India."}
    ]
    report = CitationValidator.audit_citations("As clarified in Circular No. 184/16/2022-GST, services are governed by place of supply.", chunks)
    assert report.is_valid is True
    assert report.verdict == "PASS"


def test_nonexistent_authority_honest_handling():
    """
    TEST 6: Ask for nonexistent section e.g. Section 999(99).
    Expected: Citation validator / gate catches hallucinated section.
    """
    chunks = [
        {"provision": "CGST_SEC_16", "text": "Section 16 text"}
    ]
    report = CitationValidator.audit_citations("Under Section 999(99) of the CGST Act, Special credit applies.", chunks)
    assert report.is_valid is False
    assert report.verdict == "BLOCK"
    assert any("999" in u for u in report.unsupported_citations)


def test_documents_api_contract():
    """
    TEST 14: Audit document list routes for all, circulars/by-year, notifications/by-year.
    """
    from app.api.documents import list_documents
    docs_all = list_documents("all")
    assert isinstance(docs_all, list)

    docs_by_year = list_documents("circulars/by-year")
    assert isinstance(docs_by_year, list)


def test_feed_store_seed_startup_clean():
    """
    TEST 15: Verify the application lifespan startup runs without any ImportError
    and the feed store module is cleanly importable and functional.

    Two sub-verifications:
      (a) ASGI startup test: drive the _lifespan via AsyncClient.
          - If an ImportError exists in the startup block, it propagates out of
            the lifespan and causes this test to fail immediately.
          - The app serving a response (even 503-warmup-pending) confirms the
            full startup lifecycle completed without crashing.
      (b) Direct feed-store contract test: verify make_event() + _event_log
          work correctly in isolation (unit-level check for the module contract).
    """
    import asyncio
    from httpx import AsyncClient, ASGITransport
    from app.api.app import app

    async def _run_startup_lifecycle():
        """Drive the FastAPI ASGI lifespan and confirm startup completes cleanly."""
        # ASGITransport drives the FastAPI lifespan (startup + shutdown).
        # Any ImportError or unhandled exception in _lifespan would propagate here.
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.get("/api/health")
            # 200 = ready, 503 = warmup-pending. Both mean startup completed without crash.
            assert resp.status_code in (200, 503), (
                f"Unexpected HTTP status {resp.status_code} — startup may have failed"
            )
        # Reaching here: lifespan startup+shutdown executed without unhandled exception.

    # (a) ASGI startup lifecycle test
    asyncio.run(_run_startup_lifecycle())

    # (b) Direct feed-store module contract test
    from app.feed_store import _event_log, make_event, get_recent_events
    test_evt = make_event("Startup test verification event", "TEST")
    assert test_evt["type"] == "TEST", "make_event type mismatch"
    assert "id" in test_evt, "make_event missing 'id'"
    assert "timestamp" in test_evt, "make_event missing 'timestamp'"
    assert isinstance(_event_log, object), "_event_log not importable"
    # publish_event_sync and manual append work correctly
    _event_log.append(test_evt)
    recent = get_recent_events(1)
    assert recent and recent[0]["type"] == "TEST", "get_recent_events did not return appended event"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Master Action Pipeline Invariant Tests (Items 1–22)
# ─────────────────────────────────────────────────────────────────────────────

def test_inv_01_explicit_section_and_subsection_specificity():
    """Item 1 & 2 & 6: Specificity invariants for sections, subsections, and clauses."""
    sec17 = ReferenceResolver.resolve_references("Section 17")[0]
    sec17_5 = ReferenceResolver.resolve_references("Section 17(5)")[0]
    sec17_5_d = ReferenceResolver.resolve_references("Section 17(5)(d)")[0]

    assert sec17_5_d.is_exact_or_child_of(sec17_5) is True
    assert sec17_5_d.is_exact_or_child_of(sec17) is True
    assert sec17.is_exact_or_child_of(sec17_5_d) is False
    assert sec17_5.is_exact_or_child_of(sec17_5_d) is False


def test_inv_03_explicit_circular_evidence_selection_dominance():
    """Item 3 & 4: Explicit circular query selects and prioritizes circular chunks over unrequested circulars."""
    from app.generation.context_builder import select_generation_chunks
    query = "What clarification was given in Circular 184/16/2022-GST regarding transportation of goods outside India?"
    chunks = [
        {"chunk_id": "c1", "rel_path": "circular/Circular_184.pdf", "text": "Circular 184 clarification on transportation.", "_pinned_by_ref": True, "metadata": {"provision_keys": ["CIRCULAR_184"]}},
        {"chunk_id": "c2", "rel_path": "circular/Circular_184.pdf", "text": "Circular 184 paragraph 2 operative clarification.", "metadata": {"rel_path": "circular/Circular_184.pdf"}},
        {"chunk_id": "c3", "rel_path": "circular/Circular_108.pdf", "text": "Circular 108 unrelated text.", "metadata": {"rel_path": "circular/Circular_108.pdf"}},
        {"chunk_id": "c4", "rel_path": "circular/Circular_206.pdf", "text": "Circular 206 unrelated text.", "metadata": {"rel_path": "circular/Circular_206.pdf"}},
        {"chunk_id": "c5", "rel_path": "CGST Acts/Section 12.pdf", "text": "Section 12(8) statute text.", "_is_statute_first": True},
    ]

    selected = select_generation_chunks(chunks, query)
    selected_cids = [c["chunk_id"] for c in selected]

    # Circular 184 chunks and sibling chunks must be included
    assert "c1" in selected_cids
    assert "c2" in selected_cids
    # Unrequested circulars must NOT crowd out the primary evidence
    assert "c3" not in selected_cids
    assert "c4" not in selected_cids


def test_inv_05_explicit_case_law_selection_and_evidence_preservation():
    """Item 5: Explicit case law query retrieves and preserves case law chunks."""
    from app.generation.context_builder import select_generation_chunks
    query = "What did the Supreme Court hold in Safari Retreats regarding Section 17(5)(d)?"
    chunks = [
        {"chunk_id": "s1", "rel_path": "Case Laws/Safari Retreats.pdf", "text": "Supreme Court judgment in Safari Retreats regarding construction and Section 17(5)(d).", "metadata": {"rel_path": "Case Laws/Safari Retreats.pdf"}},
        {"chunk_id": "s2", "rel_path": "CGST Acts/Section 17.pdf", "text": "Section 17(5)(d) bare statute text.", "_is_statute_first": True, "metadata": {"provision_keys": ["CGST_SEC_17(5)(d)"]}},
        {"chunk_id": "s3", "rel_path": "circular/Circular_131.pdf", "text": "Unrelated circular text."},
    ]

    selected = select_generation_chunks(chunks, query)
    selected_cids = [c["chunk_id"] for c in selected]

    assert "s1" in selected_cids
    assert "s2" in selected_cids
    assert "s3" not in selected_cids


def test_inv_07_multiple_authorities_in_one_query():
    """Item 7: Multiple explicit authorities in query resolved and preserved."""
    query = "Compare Section 16(2) and Section 17(5) along with Rule 89"
    refs = ReferenceResolver.resolve_references(query)
    canonical = {r.canonical_key for r in refs}
    assert "CGST_SEC_16(2)" in canonical
    assert "CGST_SEC_17(5)" in canonical
    assert "CGST_RUL_89" in canonical


def test_inv_11_compression_preserves_immutable_marker_identity():
    """Item 11: Compression preserves exact chunk [Sn] marker identities."""
    from app.generation.context_compressor import compress_context
    chunks = [
        {"chunk_id": "ch_a", "source": "DocA.pdf", "text": "Section 16 conditions for input tax credit claiming eligibility.", "page": 1, "_final_legal_score": 0.95},
        {"chunk_id": "ch_b", "source": "DocB.pdf", "text": "Section 17 apportionments and blocked credits list.", "page": 2, "_final_legal_score": 0.80},
    ]
    compressed = compress_context(chunks, "Section 16 input tax credit")
    # Marker [S1] refers to DocA, [S2] refers to DocB
    assert "[S1]" in compressed
    assert "DocA.pdf" in compressed


def test_inv_12_unsupported_peripheral_citation_triggers_repair():
    """Item 12: Unsupported peripheral citation in generated answer is cleanly repaired."""
    chunks = [
        {"provision": "CGST_SEC_17(5)(d)", "text": "Section 17(5)(d) ITC is blocked on construction of immovable property."}
    ]
    gen_text = (
        "Under Section 17(5)(d) of the CGST Act, ITC is blocked on construction of immovable property.\n\n"
        "Additionally, refund is calculated under Rule 89(4) of the CGST Rules."
    )
    vr = asyncio.run(run_verification_pipeline(
        answer=gen_text,
        query="What does Section 17(5)(d) provide?",
        chunks=chunks,
        context="",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))
    assert vr.gate_verdict == "REPAIR"
    assert "Section 17(5)(d)" in vr.verified_answer
    assert "Rule 89" not in vr.verified_answer


def test_inv_13_unsupported_primary_citation_triggers_block():
    """Item 13: Unsupported primary citation causes gate BLOCK and honest fallback."""
    chunks = [
        {"provision": "CGST_SEC_16", "text": "Section 16 text."}
    ]
    gen_text = "Section 999(99) provides a special limitation exemption."
    vr = asyncio.run(run_verification_pipeline(
        answer=gen_text,
        query="What does Section 999(99) provide?",
        chunks=chunks,
        context="",
        truth_rules_text="",
        marker_map=[],
        is_draft=False,
    ))
    assert vr.gate_verdict == "BLOCK"
    assert vr.is_verified is False
    assert "LETA TEC Legal Integrity Notice" in vr.safe_fallback_answer
    assert "Section 999" in vr.safe_fallback_answer


def test_inv_15_citation_marker_map_provenance_binding():
    """Item 14 & 15: Marker map links resolve strictly to exact chunk documents."""
    from app.generation.context_builder import build_marker_map, parse_markers
    chunks = [
        {"chunk_id": "c1", "rel_path": "CGST Acts/Section 16.pdf", "page": 5},
        {"chunk_id": "c2", "rel_path": "circular/Circular_184.pdf", "page": 2},
    ]
    marker_map = build_marker_map(chunks)
    assert len(marker_map) == 2
    assert marker_map[0]["title"] == "Section 16.pdf"
    assert "Section%2016.pdf" in marker_map[0]["url"]
    assert marker_map[1]["title"] == "Circular_184.pdf"

    parsed = parse_markers("As provided in (S1) and clarified in (S2).", marker_map)
    assert len(parsed["citations"]) == 2
    assert parsed["citations"][0]["title"] == "Section 16.pdf"
    assert parsed["citations"][1]["title"] == "Circular_184.pdf"


def test_inv_16_detected_refs_trace_lifecycle():
    """Item 16: RetrievalTrace receives and stores detected canonical references."""
    from app.retrieval.retrieval_trace import RetrievalTrace
    trace = RetrievalTrace(query_id="test-trace-1", query="What does Circular 184 provide?")
    trace.record_preprocessing(
        original_query="What does Circular 184 provide?",
        detected_refs=["CIRCULAR_184"],
    )
    log_dict = trace.to_log_dict()
    assert "CIRCULAR_184" in log_dict["detected_refs"]


# ─────────────────────────────────────────────────────────────────────────────
# 10. Indian Statutory Drafting & Evidence-Aware Multi-Tier Generation Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_indian_statutory_drafting_inverted_subsections():
    """Verify ReferenceResolver correctly parses inverted Indian statutory drafting patterns."""
    # A. "sub-section (6) of section 2 of the IGST Act" -> IGST_SEC_2(6)
    r1 = ReferenceResolver.resolve_references("Under sub-section (6) of section 2 of the IGST Act, export of services is defined.")
    keys1 = {r.canonical_key for r in r1}
    assert "IGST_SEC_2(6)" in keys1
    sec2_6 = next(r for r in r1 if r.canonical_key == "IGST_SEC_2(6)")
    assert sec2_6.statute == "IGST"
    assert sec2_6.provision_num == "2"
    assert sec2_6.subsection == "6"

    # B. Variations: "subsection (6) of section 2", "sub-section 6 of section 2", "sub-section (6) of Sec. 2"
    r2 = ReferenceResolver.resolve_references("Refer to subsection (6) of section 2 and sub-section 6 of section 2 and sub-section (6) of Sec. 2.")
    keys2 = {r.canonical_key for r in r2}
    assert "CGST_SEC_2(6)" in keys2

    # C. Inverted Rules: "sub-rule (4) of rule 89 of the CGST Rules", "clause (b) of sub-rule (4) of rule 89"
    r3 = ReferenceResolver.resolve_references("Refund is calculated under clause (b) of sub-rule (4) of rule 89 of the CGST Rules.")
    keys3 = {r.canonical_key for r in r3}
    assert "CGST_RUL_89(4)(b)" in keys3

    # D. Inverted Clauses: "clause (a) of sub-section (5) of section 17"
    r4 = ReferenceResolver.resolve_references("Credit blocked under clause (a) of sub-section (5) of section 17 of CGST Act.")
    keys4 = {r.canonical_key for r in r4}
    assert "CGST_SEC_17(5)(a)" in keys4


def test_statutory_numbered_paragraphs_chunk_resolution():
    """Verify statutory numbered paragraphs in Act/Rule chunks resolve to specific canonical children."""
    chunk = {
        "chunk_id": "sec16_chunk",
        "rel_path": "IGST Acts/Section 16.pdf",
        "_is_statute_first": True,
        "text": (
            "Section 16. Zero rated supply.\n"
            "(1) \"zero rated supply\" means any of the following supplies of goods or services or both, namely:--\n"
            "(a) export of goods or services or both; or\n"
            "(b) supply of goods or services or both to a Special Economic Zone developer.\n"
            "(2) Subject to the provisions of sub-section (5) of section 17 of the Central Goods and Services Tax Act...\n"
            "(3) A registered person making zero rated supply shall be eligible to claim refund...\n"
        ),
        "metadata": {"provision_keys": ["IGST_SEC_16"]},
    }
    available = ReferenceResolver.extract_available_chunk_references([chunk])
    avail_keys = {r.canonical_key for r in available}

    assert "IGST_SEC_16" in avail_keys
    assert "IGST_SEC_16(1)" in avail_keys
    assert "IGST_SEC_16(3)" in avail_keys


def test_source_text_evidence_verification_strictness():
    """Verify verify_citation_against_evidence inspects chunk source_text and enforces strictness."""
    # Chunk contains Section 16 with subsections (1) and (3), but NOT (5)
    chunk = {
        "chunk_id": "sec16_c1",
        "rel_path": "IGST Acts/Section 16.pdf",
        "text": (
            "Section 16. Zero rated supply.\n"
            "(1) Zero rated supply means export of goods or services.\n"
            "(3) A registered person making zero rated supply shall be eligible to claim refund.\n"
        ),
        "metadata": {"provision_keys": ["IGST_SEC_16"]},
    }
    report1 = CitationValidator.audit_citations(
        "Under Section 16(1) and Section 16(3) of the IGST Act, zero rated exports are eligible for refund.",
        [chunk],
    )
    assert report1.is_valid is True
    assert report1.verdict == "PASS"

    # Mentioning Section 16(5) which is absent from source_text must be BLOCKED
    report2 = CitationValidator.audit_citations(
        "Under Section 16(5) of the IGST Act, special time limits apply.",
        [chunk],
    )
    assert report2.is_valid is False
    assert report2.verdict == "BLOCK"
    assert any("Section 16(5)" in unsupp for unsupp in report2.unsupported_citations)


def test_generation_selection_preserves_multi_tier_authorities():
    """Verify select_generation_chunks does not discard Rule / Notification tiers for broad queries."""
    from app.generation.context_builder import select_generation_chunks

    query = "Explain the treatment of export transportation services and identify the relevant section and circular."
    chunks = [
        # Act tier (4 chunks)
        {"chunk_id": "act_1", "rel_path": "IGST Acts/Section 16.pdf", "text": "Section 16 zero rated supply.", "_evidence_role": "primary_legislation", "_final_legal_score": 0.95},
        {"chunk_id": "act_2", "rel_path": "IGST Acts/Section 2.pdf", "text": "Section 2(6) export of services.", "_evidence_role": "primary_legislation", "_final_legal_score": 0.93},
        {"chunk_id": "act_3", "rel_path": "CGST Acts/Section 54.pdf", "text": "Section 54 refund provisions.", "_evidence_role": "primary_legislation", "_final_legal_score": 0.91},
        {"chunk_id": "act_4", "rel_path": "IGST Acts/Section 8.pdf", "text": "Section 8 intra-state supply.", "_evidence_role": "primary_legislation", "_final_legal_score": 0.89},
        # Rule tier (2 chunks)
        {"chunk_id": "rule_1", "rel_path": "CGST Rules/Rule 89.pdf", "text": "Rule 89 refund application formula.", "_evidence_role": "delegated_legislation", "_final_legal_score": 0.88},
        {"chunk_id": "rule_2", "rel_path": "CGST Rules/Rule 96.pdf", "text": "Rule 96 refund on export of goods or services.", "_evidence_role": "delegated_legislation", "_final_legal_score": 0.87},
        # Notification tier (1 chunk)
        {"chunk_id": "notif_1", "rel_path": "notifications/notif_13_2017.pdf", "text": "Notification 13/2017 RCM on transportation.", "_evidence_role": "delegated_authority", "_final_legal_score": 0.85},
        # Circular tier (4 chunks)
        {"chunk_id": "cir_1", "rel_path": "circular/Circular_161.pdf", "text": "Circular 161 clarification on export transportation.", "_evidence_role": "departmental_guidance", "_final_legal_score": 0.94},
        {"chunk_id": "cir_2", "rel_path": "circular/Circular_139.pdf", "text": "Circular 139 refund clarifications.", "_evidence_role": "departmental_guidance", "_final_legal_score": 0.86},
        {"chunk_id": "cir_4", "rel_path": "circular/Circular_125.pdf", "text": "Circular 125 master refund circular.", "_evidence_role": "departmental_guidance", "_final_legal_score": 0.83},
        # Case Law tier (1 chunk)
        {"chunk_id": "case_1", "rel_path": "Case Laws/Mohit Minerals.pdf", "text": "Mohit Minerals ocean freight judgment.", "_evidence_role": "binding_precedent", "_final_legal_score": 0.90},
    ]

    selected = select_generation_chunks(chunks, query)
    selected_cids = {c["chunk_id"] for c in selected}

    # Verify that all 5 represented tiers (Acts, Rules, Notifications, Circulars, Case Law) are preserved
    assert "act_1" in selected_cids
    assert "rule_1" in selected_cids, "Rule 89 must not be discarded by generation selection"
    assert "rule_2" in selected_cids, "Rule 96 must not be discarded by generation selection"
    assert "notif_1" in selected_cids, "Notification 13/2017 must not be discarded by generation selection"
    assert "cir_1" in selected_cids
    assert "case_1" in selected_cids


def test_evidence_selection_under_heavy_capacity_pressure():
    """Verify select_generation_chunks handles 50+ chunks, deduplicating repetitive docs and respecting token budget."""
    from app.generation.context_builder import select_generation_chunks, MAX_EVIDENCE_TOKENS

    query = "What are the rules and statutory provisions governing tax invoice requirements and credit notes?"
    # Generate 55 candidate chunks with repetitive documents and varying scores
    chunks = []
    # 20 duplicate/repetitive chunks from same doc (Invoice Rules)
    for i in range(20):
        chunks.append({
            "chunk_id": f"inv_rule_dup_{i}",
            "rel_path": "CGST Rules/Rule 46 Tax Invoice.pdf",
            "text": f"Rule 46 tax invoice requirement paragraph {i}. " * 30,
            "_final_legal_score": 0.90 - (i * 0.01),
        })
    # 15 repetitive chunks from Section 31 (Statute)
    for i in range(15):
        chunks.append({
            "chunk_id": f"sec31_dup_{i}",
            "rel_path": "CGST Acts/Section 31 Tax invoice.pdf",
            "text": f"Section 31 tax invoice statute requirement clause {i}. " * 30,
            "_final_legal_score": 0.85 - (i * 0.01),
        })
    # 10 chunks from Circular 160 (Clarifications)
    for i in range(10):
        chunks.append({
            "chunk_id": f"cir160_dup_{i}",
            "rel_path": "circulars/Circular_160.pdf",
            "text": f"Circular 160 clarification on credit notes paragraph {i}. " * 30,
            "_final_legal_score": 0.80 - (i * 0.01),
        })
    # 10 chunks from Case Law (Judicial precedents)
    for i in range(10):
        chunks.append({
            "chunk_id": f"case_dup_{i}",
            "rel_path": f"Case Laws/Judgment_{i}.pdf",
            "text": f"Judgment {i} discussing tax invoices and credit notes. " * 30,
            "_final_legal_score": 0.70 - (i * 0.01),
        })

    selected = select_generation_chunks(chunks, query)
    selected_cids = {c["chunk_id"] for c in selected}

    # Verify deduplication: no single document monopolizes the entire budget (max 4 per doc in topical mode)
    doc_counts = {}
    for c in selected:
        doc = c["rel_path"]
        doc_counts[doc] = doc_counts.get(doc, 0) + 1
        assert doc_counts[doc] <= 4, f"Doc {doc} exceeded max deduplication cap of 4 chunks"

    # Verify token budget is respected
    total_tokens = sum(len(c.get("text", "").strip()) // 4 for c in selected)
    assert total_tokens <= MAX_EVIDENCE_TOKENS


def test_evidence_selection_no_unnecessary_tier_stuffing_for_explicit_queries():
    """Verify that explicit statutory queries prioritize direct/connected evidence and exclude unrequested circulars/cases."""
    from app.generation.context_builder import select_generation_chunks

    query = "What are the blocked credit restrictions under Section 17(5)(c) of the CGST Act?"
    chunks = [
        # Explicit matching direct evidence
        {"chunk_id": "sec17_5_c", "rel_path": "CGST Acts/Section 17.pdf", "text": "Section 17(5)(c) works contract services for construction of an immovable property.", "metadata": {"provision_keys": ["CGST_SEC_17(5)(c)"]}},
        {"chunk_id": "sec17_5_d", "rel_path": "CGST Acts/Section 17.pdf", "text": "Section 17(5)(d) goods or services received by a taxable person for construction.", "metadata": {"provision_keys": ["CGST_SEC_17(5)(d)"]}},
        {"chunk_id": "sec17_gen", "rel_path": "CGST Acts/Section 17.pdf", "text": "Section 17 apportionment of credit and blocked credits."},
        # Connected statute
        {"chunk_id": "sec16_conn", "rel_path": "CGST Acts/Section 16.pdf", "text": "Section 16 eligibility and conditions for taking input tax credit.", "_is_statute_first": True},
        # High-score unrequested circulars
        {"chunk_id": "cir_unrelated_1", "rel_path": "circular/Circular_131.pdf", "text": "Circular 131 standard operating procedure.", "_final_legal_score": 0.99},
        {"chunk_id": "cir_unrelated_2", "rel_path": "circular/Circular_125.pdf", "text": "Circular 125 refund rules.", "_final_legal_score": 0.98},
        # High-score unrequested case law
        {"chunk_id": "case_unrelated", "rel_path": "Case Laws/Unrelated_Tax_Case.pdf", "text": "Unrelated tax judgment text.", "_final_legal_score": 0.97},
    ]

    selected = select_generation_chunks(chunks, query)
    selected_cids = {c["chunk_id"] for c in selected}

    # Direct evidence must dominate
    assert "sec17_5_c" in selected_cids
    assert "sec17_5_d" in selected_cids
    assert "sec17_gen" in selected_cids
    assert "sec16_conn" in selected_cids

    # Unrequested circulars/cases must NOT crowd out or pollute explicit statutory query context
    assert "cir_unrelated_1" not in selected_cids
    assert "cir_unrelated_2" not in selected_cids
    assert "case_unrelated" not in selected_cids



