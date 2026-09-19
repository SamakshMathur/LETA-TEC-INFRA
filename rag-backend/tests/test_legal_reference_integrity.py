"""
Regression and Integrity Test Suite for Legal Reference Integrity V4.

Tests:
1. Act & provision detection: IGST vs CGST distinction, eliminates silent CGST fallback.
2. Circular & Notification identity resolution.
3. Direct Authority vs Cross-Reference extraction.
4. Chunk continuity & sequential heading resolution across chunks.
5. Evidence Selection (4-pass statutory priority policy).
6. Canonical Authority Registry & <allowed_authorities> block generation.
7. CitationValidator & Marker Laundering detection.
8. Substantive Claim Support verification & 3-state Final Answer Gate (PASS / REPAIR / BLOCK).
"""

import pytest
from app.retrieval.reference_resolver import (
    ReferenceResolver,
    resolve_act,
    resolve_rule_act,
    extract_available_chunk_references,
    verify_citation_against_evidence,
    LegalReference,
)
from app.generation.context_builder import (
    select_generation_chunks,
    build_canonical_authority_registry,
    format_allowed_authorities_block,
    build_marker_map,
)
from app.generation.citation_validator import CitationValidator
from app.generation.verification_pipeline import (
    verify_substantive_claim_support,
    run_verification_pipeline,
)


class TestReferenceResolver:
    """Phase 1: Statute Resolution & Provison Extraction."""

    def test_igst_section_13_does_not_resolve_to_cgst(self):
        query = "Under the Integrated Goods and Services Tax Act, 2017, what does Section 13 say?"
        resolver = ReferenceResolver()
        refs = resolver.resolve_references(query)
        assert len(refs) >= 1
        assert refs[0].act == "IGST"
        assert refs[0].canonical_key == "IGST_SEC_13"
        assert refs[0].canonical_key != "CGST_SEC_13"

    def test_ambiguous_section_does_not_silently_default_to_cgst(self):
        query = "What does Section 13 provide?"
        resolver = ReferenceResolver()
        refs = resolver.resolve_references(query)
        assert len(refs) >= 1
        # When statute cannot be established deterministically, statute is UNKNOWN
        assert refs[0].act == "UNKNOWN"
        assert refs[0].canonical_key == "UNKNOWN_SEC_13"

    def test_explicit_cgst_section_resolves_to_cgst(self):
        query = "What are the conditions under Central Goods and Services Tax Act Section 16(2)?"
        resolver = ReferenceResolver()
        refs = resolver.resolve_references(query)
        assert len(refs) >= 1
        assert refs[0].act == "CGST"
        assert "CGST_SEC_16" in refs[0].canonical_key

    def test_rule_act_resolution(self):
        assert resolve_rule_act("CGST Rules, 2017 - Rule 96") == "CGST"
        assert resolve_rule_act("IGST Rules - Rule 3") == "IGST"
        assert resolve_rule_act("Random text mentioning Rule 89") == "CGST"  # GST rules default to CGST

    def test_circular_and_notification_identity(self):
        q1 = "Circular No. 184/16/2022-GST clarifying taxability of services"
        resolver = ReferenceResolver()
        refs1 = resolver.resolve_references(q1)
        assert any(r.provision_type == "circular" for r in refs1)

        q2 = "Notification No. 50/2018-Central Tax dated 13th September 2018"
        refs2 = resolver.resolve_references(q2)
        assert any(r.provision_type == "notification" for r in refs2)


class TestChunkExtractionAndDirectVsCrossRef:
    """Phase 2 & Phase 7: Chunk Continuity, Direct vs Cross-Reference."""

    def test_direct_vs_cross_reference_distinction(self):
        chunk = {
            "chunk_id": "cgst_sec_16_chunk_1",
            "metadata": {
                "rel_path": "acts/cgst_act.txt",
                "section": "16",
                "section_heading": "Eligibility and conditions for taking input tax credit",
            },
            "text": (
                "Section 16. (1) Every registered person shall be entitled to take credit of input tax.\n"
                "(2) Notwithstanding anything contained in this section, no registered person shall be entitled to the credit of any input tax...\n"
                "(d) he has furnished the return under section 39."
            ),
        }
        refs = extract_available_chunk_references([chunk])
        direct_refs = [r for r in refs if not r.is_cross_ref]
        cross_refs = [r for r in refs if r.is_cross_ref]

        assert any("CGST_SEC_16" in r.canonical_key for r in direct_refs)
        assert any("CGST_SEC_39" in r.canonical_key for r in cross_refs)

    def test_continuation_chunk_preserves_section_identity(self):
        chunk = {
            "chunk_id": "cgst_sec_17_cont",
            "metadata": {
                "rel_path": "acts/cgst_act.txt",
                "section": "17",
                "section_heading": "Apportionment of credit and blocked credits",
            },
            "text": (
                "(5) Notwithstanding anything contained in sub-section (1) of section 16 and sub-section (1) of section 18, "
                "input tax credit shall not be available in respect of the following, namely:—\n"
                "(d) goods or services or both received by a taxable person for construction of an immovable property..."
            ),
        }
        refs = extract_available_chunk_references([chunk])
        direct_keys = [r.canonical_key for r in refs if not r.is_cross_ref]
        assert "CGST_SEC_17(5)(d)" in direct_keys or "CGST_SEC_17(5)" in direct_keys


class TestEvidenceSelectionAndRegistry:
    """Phase 4 & 5: Evidence Selection & Canonical Authority Registry."""

    def test_select_generation_chunks_prioritizes_direct_statutory_provisions(self):
        target_chunk = {
            "chunk_id": "sec_16_4",
            "metadata": {"rel_path": "acts/cgst_act.txt", "section": "16"},
            "text": "A registered person shall not be entitled to take input tax credit in respect of any invoice after the thirtieth day of November... (4)",
            "rerank_score": 0.85,
        }
        unrelated_circular = {
            "chunk_id": "circ_unrelated",
            "metadata": {"rel_path": "circulars/cir_999.txt"},
            "text": "Clarification on miscellaneous procedural issues under GST.",
            "rerank_score": 0.95,
        }
        unrelated_rule = {
            "chunk_id": "rule_unrelated",
            "metadata": {"rel_path": "rules/cgst_rules.txt", "rule": "42"},
            "text": "Manner of determination of input tax credit in respect of inputs and input services...",
            "rerank_score": 0.90,
        }

        chunks = [unrelated_circular, unrelated_rule, target_chunk]
        selected = select_generation_chunks(chunks, "What is the time limit under Section 16(4)?", max_tokens=1000)

        # Target chunk must be prioritized to front
        assert len(selected) >= 1
        assert selected[0]["chunk_id"] == "sec_16_4"

    def test_build_canonical_authority_registry_and_block(self):
        chunks = [
            {
                "chunk_id": "c1",
                "metadata": {"rel_path": "acts/cgst_act.txt", "section": "16"},
                "text": "Section 16. Eligibility and conditions for taking input tax credit.",
            },
            {
                "chunk_id": "c2",
                "metadata": {"rel_path": "rules/cgst_rules.txt", "rule": "36"},
                "text": "Rule 36. Documentary requirements and conditions for claiming input tax credit.",
            },
        ]
        registry = build_canonical_authority_registry(chunks)
        all_keys = [k for item in registry for k in item["canonical_keys"]]
        assert any("CGST_SEC_16" in k for k in all_keys)
        assert any("CGST_RUL_36" in k for k in all_keys)

        block = format_allowed_authorities_block(registry)
        assert "<allowed_authorities>" in block
        assert "CGST_SEC_16" in block
        assert "CGST_RUL_36" in block


class TestCitationValidatorAndMarkerLaundering:
    """Phase 6: Citation Validation & Marker Laundering."""

    def test_marker_laundering_fails(self):
        chunks = [
            {
                "chunk_id": "c_sec_17_5",
                "metadata": {"rel_path": "acts/cgst_act.txt", "section": "17"},
                "text": "Section 17(5)(d) blocks input tax credit for construction of immovable property.",
            },
            {
                "chunk_id": "c_sec_73",
                "metadata": {"rel_path": "acts/cgst_act.txt", "section": "73"},
                "text": "Section 73 provides for determination of tax not paid or short paid.",
            },
        ]
        sn_map = {"S1": chunks[0], "S2": chunks[1]}
        claim_sentence = "Under Section 73, the tax officer may issue a notice for unpaid tax (S1)."
        s_refs = ReferenceResolver.resolve_references(claim_sentence)
        avail_refs = ReferenceResolver.extract_available_chunk_references(chunks)
        res = verify_substantive_claim_support(claim_sentence, s_refs, avail_refs, sn_map)
        assert not res["supported"]
        assert any("MARKER_LAUNDERING" in str(iss) for iss in res["issues"])

    def test_valid_marker_attribution_passes(self):
        chunks = [
            {
                "chunk_id": "c_sec_16_2",
                "metadata": {"rel_path": "acts/cgst_act.txt", "section": "16"},
                "text": "Section 16(2) provides four mandatory conditions for entitlement to input tax credit.",
            }
        ]
        sn_map = {"S1": chunks[0]}
        claim_sentence = "Section 16(2) provides four mandatory conditions for entitlement to input tax credit (S1)."
        s_refs = ReferenceResolver.resolve_references(claim_sentence)
        avail_refs = ReferenceResolver.extract_available_chunk_references(chunks)
        res = verify_substantive_claim_support(claim_sentence, s_refs, avail_refs, sn_map)
        assert res["supported"]
        assert len(res["issues"]) == 0


class TestFinalAnswerGate:
    """Phase 8 & 9: Substantive Claim Support & 3-State Final Answer Gate."""

    @pytest.mark.anyio
    async def test_pipeline_pass_on_well_grounded_answer(self):
        chunks = [
            {
                "chunk_id": "c1",
                "metadata": {"rel_path": "acts/cgst_act.txt", "section": "16"},
                "text": "Section 16(4) specifies that no registered person shall take ITC after 30th November following the end of financial year.",
            }
        ]
        marker_map = build_marker_map(chunks)
        answer = "Under Section 16(4) of the CGST Act, 2017, no registered person can claim ITC after 30th November following the financial year [S1]."
        vr = await run_verification_pipeline(
            answer=answer,
            query="What is the time limit under Section 16(4)?",
            chunks=chunks,
            context="Section 16(4) specifies time limit.",
            truth_rules_text="",
            marker_map=marker_map,
            is_draft=False,
        )
        assert vr.gate_verdict == "PASS"
        assert vr.is_verified
        assert answer in vr.verified_answer

    @pytest.mark.anyio
    async def test_pipeline_block_on_completely_unsupported_claims(self):
        chunks = [
            {
                "chunk_id": "c1",
                "metadata": {"rel_path": "acts/cgst_act.txt", "section": "16"},
                "text": "Section 16 details ITC rules.",
            }
        ]
        marker_map = build_marker_map(chunks)
        answer = "Under Section 13 of the IGST Act, cross-border place of supply is always domestic [S1]."
        vr = await run_verification_pipeline(
            answer=answer,
            query="Explain IGST place of supply",
            chunks=chunks,
            context="Section 16 details ITC rules.",
            truth_rules_text="",
            marker_map=marker_map,
            is_draft=False,
        )
        assert vr.gate_verdict == "BLOCK"
        assert not vr.is_verified
        assert "LETA TEC Legal Integrity Notice" in vr.verified_answer

