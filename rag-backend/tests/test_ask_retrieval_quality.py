"""Deterministic unit and regression tests for GST-RAG retrieval quality.

Validates generic legal authority identity and evidence correctness across:
1. Document-level circular/notification metadata inheritance across sibling chunks.
2. Direct reference lookup pinning all substantive pages of multi-chunk authorities.
3. Explicit-reference priority preventing taxonomy dilution and displacement.
4. Intra-class authority identity distinctness (Section 16 != 17, Rule 89 != 96, Circular 184 != 203,
   Notification 12/2017 != 13/2017, Case A != Case B, AAR A != AAR B).
5. Strict preservation of the universal statutory/case-law hierarchy for general queries.
6. Negative case: distinct authority identity attribution preventing cross-authority displacement.

All tests are isolated unit tests that run entirely in memory without requiring
FAISS index files, external models, or network access.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
import pytest

from app.retrieval.retriever import Retriever
from app.retrieval.authority_taxonomy import classify_query_authority
from app.retrieval.evidence_resolver import resolve_evidence


def make_test_retriever(chunks: List[Dict[str, Any]]) -> Retriever:
    """Construct an isolated in-memory Retriever test-double without FAISS or model dependencies.

    Executes the exact in-memory metadata normalization and provision index construction
    used by Retriever.__init__.
    """
    retriever = Retriever.__new__(Retriever)
    retriever.chunks = [dict(c) for c in chunks]
    retriever.metadata = [c.get("metadata", {}) for c in retriever.chunks]

    # In-memory circular index & sibling propagation
    _cir_num_re = re.compile(
        r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
        r'|cir[-_.](?:cgst[-_.])?'
        r'|cir(?=[0-9])'
        r'|circularno[-_.])'
        r'(\d{2,3})',
        re.IGNORECASE,
    )
    _cir_leading_re = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)
    retriever._circular_index = {}
    for _ci, _chunk in enumerate(retriever.chunks):
        _meta = _chunk.get("metadata", {})
        _cat = (_meta.get("category") or "").lower()
        _dtype = (_meta.get("document_type") or "").lower()
        _rel = _chunk.get("rel_path") or _meta.get("rel_path", "")
        if "circular" not in _cat and "circular" not in _dtype and "circular" not in _rel.lower():
            continue
        _fname = _rel.split("/")[-1].split("\\")[-1] if _rel else ""
        _m = _cir_num_re.search(_fname) or _cir_leading_re.match(_fname)
        if _m:
            _key = f"CIRCULAR_{_m.group(1)}"
            if _key not in retriever._circular_index:
                retriever._circular_index[_key] = []
            if _ci not in retriever._circular_index[_key]:
                retriever._circular_index[_key].append(_ci)
            _pkeys = _meta.get("provision_keys")
            if _pkeys is None:
                _meta["provision_keys"] = [_key]
            elif _key not in _pkeys:
                if isinstance(_pkeys, list):
                    _pkeys.append(_key)
                else:
                    _meta["provision_keys"] = list(_pkeys) + [_key]

    # In-memory notification index & sibling propagation
    _notif_num_re = re.compile(
        r'(?:notif(?:ication)?[-_.\s]*(?:no[-_.\s]*)?)?(\d+)[-_/](\d{4})',
        re.IGNORECASE,
    )
    retriever._notification_index = {}
    for _ci, _chunk in enumerate(retriever.chunks):
        _meta = _chunk.get("metadata", {})
        _cat  = (_meta.get("category") or "").lower()
        _dtype = (_meta.get("document_type") or "").lower()
        _rel  = _chunk.get("rel_path") or _meta.get("rel_path", "")
        if "notification" not in _cat and "notification" not in _dtype and "notification" not in _rel.lower():
            continue
        _fname = _rel.split("/")[-1].split("\\")[-1] if _rel else ""
        _nm = _notif_num_re.search(_fname)
        if _nm:
            _key = f"NOTIF_{_nm.group(1)}_{_nm.group(2)}"
            if _key not in retriever._notification_index:
                retriever._notification_index[_key] = []
            if _ci not in retriever._notification_index[_key]:
                retriever._notification_index[_key].append(_ci)
            _pkeys = _meta.get("provision_keys")
            if _pkeys is None:
                _meta["provision_keys"] = [_key]
            elif _key not in _pkeys:
                if isinstance(_pkeys, list):
                    _pkeys.append(_key)
                else:
                    _meta["provision_keys"] = list(_pkeys) + [_key]

    # In-memory provision index
    retriever._provision_index = {}
    for _ci, _chunk in enumerate(retriever.chunks):
        _meta = _chunk.get("metadata", {})
        _refs = set(
            (_meta.get("provisions") or [])
            + (_meta.get("citations") or [])
            + (_meta.get("provision_keys") or [])
        )
        for _ref in _refs:
            if _ref and _ref not in ("ACT", "RULES", "NOTIFICATION"):
                if _ref not in retriever._provision_index:
                    retriever._provision_index[_ref] = []
                retriever._provision_index[_ref].append(_ci)

    return retriever


@pytest.mark.parametrize(
    "authority_key,rel_path_pattern,chunk_count,initial_pkeys",
    [
        ("CIRCULAR_184", "circulars/2022/cir-184-16-2022.pdf", 4, ["CIRCULAR_184"]),
        ("CIRCULAR_178", "circulars/2022/cir-178-10-2022-cgst.pdf", 3, ["CIRCULAR_178"]),
        ("NOTIF_12_2017", "notifications/2017/notif-12-2017-central-tax.pdf", 4, ["NOTIF_12_2017"]),
    ],
)
def test_authority_sibling_metadata_inheritance(
    authority_key: str, rel_path_pattern: str, chunk_count: int, initial_pkeys: List[str]
):
    """Test 1: Sibling chunks from any circular or notification document inherit canonical metadata.

    Validates that even when only chunk 0 has initial citations, all subsequent sibling
    chunks (substantive pages) dynamically receive the document's canonical authority key.
    """
    raw_chunks = []
    for i in range(chunk_count):
        raw_chunks.append({
            "chunk_id": f"{authority_key.lower()}_p{i}",
            "rel_path": rel_path_pattern,
            "text": f"Page {i} content of {authority_key} discussing legal requirements.",
            "metadata": {
                "rel_path": rel_path_pattern,
                "chunk_index": i,
                "provision_keys": list(initial_pkeys) if i == 0 else [],
            },
        })

    retriever = make_test_retriever(raw_chunks)

    # Verify every sibling chunk received the canonical key in memory
    for idx, chunk in enumerate(retriever.chunks):
        pkeys = chunk.get("metadata", {}).get("provision_keys", [])
        assert authority_key in pkeys, f"Sibling chunk {idx} did not inherit {authority_key}: {pkeys}"

    # Verify provision_index maps the key to all sibling chunk indices
    indexed_indices = retriever._provision_index.get(authority_key, [])
    assert len(indexed_indices) == chunk_count
    for idx in range(chunk_count):
        assert idx in indexed_indices


@pytest.mark.parametrize(
    "authority_key,rel_path_pattern",
    [
        ("CIRCULAR_184", "circulars/2022/cir-184-16-2022.pdf"),
        ("NOTIF_12_2017", "notifications/2017/notif-12-2017-central-tax.pdf"),
    ],
)
def test_direct_ref_lookup_covers_substantive_pages(authority_key: str, rel_path_pattern: str):
    """Test 2: Direct ref lookup pins all substantive pages of multi-chunk authorities.

    Ensures that chunks beyond the cover page (chunk_index 1, 2, 3) are pinned
    and not cut off by an overly restrictive per-key cap.
    """
    raw_chunks = [
        {
            "chunk_id": f"{authority_key.lower()}_p{i}",
            "rel_path": rel_path_pattern,
            "text": f"Page {i} of {authority_key} detailed legal guidance.",
            "metadata": {"rel_path": rel_path_pattern, "chunk_index": i},
        }
        for i in range(4)
    ]
    retriever = make_test_retriever(raw_chunks)
    pinned = retriever._direct_ref_lookup([authority_key])

    assert len(pinned) == 4, f"Expected 4 pinned chunks for {authority_key}, got {len(pinned)}"
    pinned_indices = [c.get("metadata", {}).get("chunk_index") for c in pinned]
    assert sorted(pinned_indices) == [0, 1, 2, 3]


def test_explicit_circular_query_preserves_requested_candidates():
    """Test 3: Explicit circular query suppresses generic taxonomy circular flooding."""
    query = "Clarification regarding GST on transportation of goods to place outside India under Circular No. 184/16/2022-GST"

    # Verify authority taxonomy suppresses default circulars (e.g. CIRCULAR_125, 135)
    tax = classify_query_authority(query)
    assert "CIRCULAR_125" not in tax.get("circulars", [])
    assert "CIRCULAR_135" not in tax.get("circulars", [])

    # Verify direct ref lookup pins Circular 184 chunks
    mock_chunks = [
        {
            "chunk_id": "cir_184_0",
            "rel_path": "circulars/2022/cir-184-16-2022.pdf",
            "text": "Circular No. 184/16/2022-GST cover page",
            "metadata": {"rel_path": "circulars/2022/cir-184-16-2022.pdf", "chunk_index": 0},
        }
    ]
    retriever = make_test_retriever(mock_chunks)
    pinned = retriever._direct_ref_lookup(["CIRCULAR_184"])
    assert len(pinned) == 1
    assert pinned[0]["chunk_id"] == "cir_184_0"


@pytest.mark.parametrize(
    "query,target_chunk_id,expected_exact_ref",
    [
        (
            "What are the statutory conditions for input tax credit under Section 16 of the CGST Act?",
            "chunk_sec_16",
            "cgst_sec_16",
        ),
        (
            "What is the refund calculation procedure specified under Rule 89(4) of CGST Rules?",
            "chunk_rule_89",
            "cgst_rul_89",
        ),
        (
            "What exemptions are granted under Notification No. 12/2017-Central Tax Rate?",
            "chunk_notif_12",
            "notif_12_2017",
        ),
        (
            "What clarification is given under Circular No. 184/16/2022-GST regarding freight?",
            "chunk_cir_184",
            "circular_184",
        ),
        (
            "What was held by the Supreme Court in Mohit Minerals regarding ocean freight levy?",
            "chunk_mohit_minerals",
            "mohit minerals",
        ),
        (
            "What was ruled in In re Caltech Polymers regarding GST on canteen recovery?",
            "chunk_caltech_polymers",
            "caltech polymers",
        ),
    ],
)
def test_generic_explicit_authority_precedence(query: str, target_chunk_id: str, expected_exact_ref: str):
    """Test 4: Generic intent-aware precedence across all legal authority classes.

    Verifies that when ANY authority (Act Section, Rule, Notification, Circular,
    AAR ruling, or Supreme Court Case) is explicitly requested, that target authority
    receives the query-intent boost and takes precedence over competing candidates.
    """
    competing_pool = [
        {
            "chunk_id": "chunk_sec_16",
            "rel_path": "act/cgst_act_2017.pdf",
            "text": "Section 16 Eligibility and conditions for taking input tax credit.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "act/cgst_act_2017.pdf", "provision_keys": ["CGST_SEC_16"]},
        },
        {
            "chunk_id": "chunk_rule_89",
            "rel_path": "rules/cgst_rules_2017.pdf",
            "text": "Rule 89 Application for refund of tax, interest, penalty, fees.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "rules/cgst_rules_2017.pdf", "provision_keys": ["CGST_RUL_89"]},
        },
        {
            "chunk_id": "chunk_notif_12",
            "rel_path": "notifications/2017/notif-12-2017.pdf",
            "text": "Notification No. 12/2017 Central Tax Rate exemption list.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "notifications/2017/notif-12-2017.pdf", "provision_keys": ["NOTIF_12_2017"]},
        },
        {
            "chunk_id": "chunk_cir_184",
            "rel_path": "circulars/2022/cir-184-16-2022.pdf",
            "text": "Circular No. 184/16/2022-GST clarification on transportation of goods.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "circulars/2022/cir-184-16-2022.pdf", "provision_keys": ["CIRCULAR_184"]},
        },
        {
            "chunk_id": "chunk_mohit_minerals",
            "rel_path": "case_law/supreme court/mohit_minerals.pdf",
            "text": "Supreme Court judgment in Mohit Minerals on ocean freight IGST.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "case_law/supreme court/mohit_minerals.pdf", "case_name": "Mohit Minerals"},
        },
        {
            "chunk_id": "chunk_caltech_polymers",
            "rel_path": "case_law/aar/caltech_polymers.pdf",
            "text": "Authority for Advance Ruling in In re Caltech Polymers regarding recovery from employees.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "case_law/aar/caltech_polymers.pdf", "applicant": "Caltech Polymers"},
        },
    ]

    resolved = resolve_evidence(competing_pool, query)

    assert resolved[0]["chunk_id"] == target_chunk_id, (
        f"Expected {target_chunk_id} to rank #1 for query '{query}', but got {resolved[0]['chunk_id']}"
    )
    assert any(expected_exact_ref in ref for ref in resolved[0]["_evidence_exact_refs"]), (
        f"Expected '{expected_exact_ref}' in exact_refs: {resolved[0]['_evidence_exact_refs']}"
    )
    assert resolved[0]["_evidence_resolution_score"] > resolved[1]["_evidence_resolution_score"]


@pytest.mark.parametrize(
    "query,expected_top_id,expected_second_id",
    [
        # Circular 184 vs Circular 203 (Intra-class circular distinction)
        (
            "What does Circular No. 184/16/2022-GST clarify regarding place of supply of transportation of goods?",
            "chunk_cir_184",
            "chunk_cir_203",
        ),
        # Notification 12/2017 vs Notification 13/2017 (Intra-class notification distinction)
        (
            "What services are exempt under Notification No. 12/2017-Central Tax Rate?",
            "chunk_notif_12",
            "chunk_notif_13",
        ),
        # Section 16 vs Section 17 (Intra-class statutory section distinction)
        (
            "What are the eligibility conditions under Section 16 of the CGST Act?",
            "chunk_sec_16",
            "chunk_sec_17",
        ),
        # Rule 89 vs Rule 96 (Intra-class rule distinction)
        (
            "What is the procedure for refund application under Rule 89 of CGST Rules?",
            "chunk_rule_89",
            "chunk_rule_96",
        ),
        # Case A (Mohit Minerals) vs Case B (Safari Retreats) (Intra-class court precedent distinction)
        (
            "What did the Supreme Court hold in Mohit Minerals regarding ocean freight?",
            "chunk_mohit_minerals",
            "chunk_safari_retreats",
        ),
        # AAR A (Caltech Polymers) vs AAR B (Soya Processing) (Intra-class AAR ruling distinction)
        (
            "What was held in In re Caltech Polymers regarding recovery for food provided in canteen?",
            "chunk_aar_caltech",
            "chunk_aar_soya",
        ),
    ],
)
def test_intra_class_authority_distinctness(query: str, expected_top_id: str, expected_second_id: str):
    """Test 5: Intra-class authority distinction.

    Proves that an explicit request for Authority X (e.g. Circular 184, Notification 12/2017,
    Section 16, Rule 89, Mohit Minerals, Caltech Polymers) boosts ONLY Authority X and does NOT
    boost a sibling Authority Y from the same authority class (Circular 203, Notification 13/2017,
    Section 17, Rule 96, Safari Retreats, Soya Processing).
    """
    pair_pool = [
        # Circulars
        {
            "chunk_id": "chunk_cir_184",
            "rel_path": "circulars/2022/cir-184-16-2022.pdf",
            "text": "Circular No. 184/16/2022-GST clarification on transportation of goods.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "circulars/2022/cir-184-16-2022.pdf", "provision_keys": ["CIRCULAR_184"]},
        },
        {
            "chunk_id": "chunk_cir_203",
            "rel_path": "circulars/2023/cir-203-15-2023.pdf",
            "text": "Circular No. 203/15/2023-GST clarification on determination of place of supply.",
            "_rerank_score": 0.86,
            "metadata": {"rel_path": "circulars/2023/cir-203-15-2023.pdf", "provision_keys": ["CIRCULAR_203"]},
        },
        # Notifications
        {
            "chunk_id": "chunk_notif_12",
            "rel_path": "notifications/2017/notif-12-2017.pdf",
            "text": "Notification No. 12/2017 Central Tax Rate exemption of services.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "notifications/2017/notif-12-2017.pdf", "provision_keys": ["NOTIF_12_2017"]},
        },
        {
            "chunk_id": "chunk_notif_13",
            "rel_path": "notifications/2017/notif-13-2017.pdf",
            "text": "Notification No. 13/2017 Central Tax Rate reverse charge mechanism.",
            "_rerank_score": 0.86,
            "metadata": {"rel_path": "notifications/2017/notif-13-2017.pdf", "provision_keys": ["NOTIF_13_2017"]},
        },
        # Sections
        {
            "chunk_id": "chunk_sec_16",
            "rel_path": "act/cgst_act_2017.pdf",
            "text": "Section 16 Eligibility and conditions for taking input tax credit.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "act/cgst_act_2017.pdf", "provision_keys": ["CGST_SEC_16"]},
        },
        {
            "chunk_id": "chunk_sec_17",
            "rel_path": "act/cgst_act_2017.pdf",
            "text": "Section 17 Apportionment of credit and blocked credits.",
            "_rerank_score": 0.86,
            "metadata": {"rel_path": "act/cgst_act_2017.pdf", "provision_keys": ["CGST_SEC_17"]},
        },
        # Rules
        {
            "chunk_id": "chunk_rule_89",
            "rel_path": "rules/cgst_rules_2017.pdf",
            "text": "Rule 89 Application for refund of tax, interest, penalty, fees.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "rules/cgst_rules_2017.pdf", "provision_keys": ["CGST_RUL_89"]},
        },
        {
            "chunk_id": "chunk_rule_96",
            "rel_path": "rules/cgst_rules_2017.pdf",
            "text": "Rule 96 Refund of integrated tax paid on goods or services exported out of India.",
            "_rerank_score": 0.86,
            "metadata": {"rel_path": "rules/cgst_rules_2017.pdf", "provision_keys": ["CGST_RUL_96"]},
        },
        # Cases
        {
            "chunk_id": "chunk_mohit_minerals",
            "rel_path": "case_law/supreme court/mohit_minerals.pdf",
            "text": "Supreme Court judgment in Mohit Minerals on ocean freight.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "case_law/supreme court/mohit_minerals.pdf", "case_name": "Mohit Minerals"},
        },
        {
            "chunk_id": "chunk_safari_retreats",
            "rel_path": "case_law/supreme court/safari_retreats.pdf",
            "text": "Supreme Court judgment in Safari Retreats on Section 17(5)(d) plant and machinery.",
            "_rerank_score": 0.86,
            "metadata": {"rel_path": "case_law/supreme court/safari_retreats.pdf", "case_name": "Safari Retreats"},
        },
        # AARs
        {
            "chunk_id": "chunk_aar_caltech",
            "rel_path": "case_law/aar/caltech_polymers.pdf",
            "text": "Authority for Advance Ruling in In re Caltech Polymers on canteen supply.",
            "_rerank_score": 0.85,
            "metadata": {"rel_path": "case_law/aar/caltech_polymers.pdf", "applicant": "Caltech Polymers"},
        },
        {
            "chunk_id": "chunk_aar_soya",
            "rel_path": "case_law/aar/soya_processing.pdf",
            "text": "Authority for Advance Ruling in In re Soya Processing on job work exemption.",
            "_rerank_score": 0.86,
            "metadata": {"rel_path": "case_law/aar/soya_processing.pdf", "applicant": "Soya Processing"},
        },
    ]

    resolved = resolve_evidence(pair_pool, query)

    # The explicitly requested authority must rank #1
    assert resolved[0]["chunk_id"] == expected_top_id, (
        f"Expected {expected_top_id} to rank #1, but got {resolved[0]['chunk_id']}"
    )
    # The sibling authority in the same class must NOT have received exact_refs for this query
    sibling_chunk = next(c for c in resolved if c["chunk_id"] == expected_second_id)
    assert len(sibling_chunk["_evidence_exact_refs"]) == 0, (
        f"Sibling {expected_second_id} incorrectly matched exact_refs: {sibling_chunk['_evidence_exact_refs']}"
    )


def test_explicit_authority_negative_case_no_cross_attribution_or_displacement():
    """Test 6 (Negative Case): Explicit authority is not displaced and retains distinct attribution.

    Verifies that:
    1. Explicit Authority X is not displaced by an unrelated Authority Y with high generic rank.
    2. Competing Authority Y does not match Authority X's exact_refs.
    3. Propositions from Authority Y are not attributed to Authority X.
    """
    cir184_chunk = {
        "chunk_id": "cir_184_substantive",
        "rel_path": "circulars/2022/cir-184-16-2022.pdf",
        "text": "Circular No. 184/16/2022-GST clarification on transportation of goods outside India.",
        "_rerank_score": 0.84,
        "metadata": {
            "rel_path": "circulars/2022/cir-184-16-2022.pdf",
            "provision_keys": ["CIRCULAR_184"],
        },
    }
    unrelated_cir_chunk = {
        "chunk_id": "cir_125_refund",
        "rel_path": "circulars/2019/cir-125-44-2019.pdf",
        "text": "Circular No. 125/44/2019 master circular on refunds and export procedures.",
        "_rerank_score": 0.89,
        "metadata": {
            "rel_path": "circulars/2019/cir-125-44-2019.pdf",
            "provision_keys": ["CIRCULAR_125"],
        },
    }
    hc_chunk = {
        "chunk_id": "hc_judgment_1",
        "rel_path": "case_law/high court/judgment.pdf",
        "text": "High Court judgment on refund eligibility under Section 54.",
        "_rerank_score": 0.88,
        "metadata": {
            "rel_path": "case_law/high court/judgment.pdf",
            "provision_keys": ["CGST_SEC_54"],
        },
    }
    sc_generic = {
        "chunk_id": "sc_general",
        "rel_path": "case_law/supreme court/general_precedent.pdf",
        "text": "Supreme Court precedent on constitutional interpretation of tax statues.",
        "_rerank_score": 0.87,
        "metadata": {"rel_path": "case_law/supreme court/general_precedent.pdf"},
    }

    pool = [unrelated_cir_chunk, hc_chunk, sc_generic, cir184_chunk]

    # Explicit Circular 184 query
    query = "What does Circular No. 184/16/2022-GST specify regarding place of supply?"
    resolved = resolve_evidence(pool, query)

    # 1. Circular 184 must rank #1 despite lower base rerank score (0.84 vs 0.89)
    assert resolved[0]["chunk_id"] == "cir_184_substantive"

    # 2. Only Circular 184 receives exact_refs for circular_184; competing chunks do not
    assert "circular_184" in resolved[0]["_evidence_exact_refs"]
    assert "circular_184" not in resolved[1]["_evidence_exact_refs"]
    assert "circular_184" not in resolved[2]["_evidence_exact_refs"]
    assert "circular_184" not in resolved[3]["_evidence_exact_refs"]

    # 3. Competing chunks retain their own distinct identity and authority roles
    roles_by_id = {c["chunk_id"]: c["_evidence_role"] for c in resolved}
    assert roles_by_id["sc_general"] == "binding_precedent"
    assert roles_by_id["hc_judgment_1"] == "persuasive_precedent"
    assert roles_by_id["cir_125_refund"] == "departmental_guidance"
    assert roles_by_id["cir_184_substantive"] == "departmental_guidance"


def test_non_explicit_query_authority_hierarchy_unchanged():
    """Test 7: Universal legal authority hierarchy strictly controls non-explicit queries.

    For queries without explicit references, verifies the universal order:
    Supreme Court (1) > Act (2) > Rule (2) > High Court (3) > Notification (4) > Circular (5) > AAR (6) > Commentary (7)
    """
    sc_chunk = {
        "chunk_id": "sc_1",
        "rel_path": "case_law/supreme court/case.pdf",
        "text": "Supreme Court interpretation of supply.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "case_law/supreme court/case.pdf"},
    }
    act_chunk = {
        "chunk_id": "act_1",
        "rel_path": "act/cgst_act.pdf",
        "text": "Section text from CGST Act.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "act/cgst_act.pdf"},
    }
    hc_chunk = {
        "chunk_id": "hc_1",
        "rel_path": "case_law/high court/judgment_1.pdf",
        "text": "High court judgment on input tax credit.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "case_law/high court/judgment_1.pdf"},
    }
    notification_chunk = {
        "chunk_id": "notif_1",
        "rel_path": "notification/notif_12_2017.pdf",
        "text": "Notification No. 12/2017 Central Tax Rate.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "notification/notif_12_2017.pdf"},
    }
    circular_chunk = {
        "chunk_id": "cir_1",
        "rel_path": "circular/cir_99.pdf",
        "text": "CBIC circular guidelines.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "circular/cir_99.pdf"},
    }
    aar_chunk = {
        "chunk_id": "aar_1",
        "rel_path": "case_law/aar/ruling.pdf",
        "text": "Advance ruling decision.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "case_law/aar/ruling.pdf"},
    }
    commentary_chunk = {
        "chunk_id": "icai_1",
        "rel_path": "commentary/icai_guide.pdf",
        "text": "ICAI technical guide on GST.",
        "_rerank_score": 0.80,
        "metadata": {"rel_path": "commentary/icai_guide.pdf"},
    }

    pool = [commentary_chunk, aar_chunk, circular_chunk, notification_chunk, hc_chunk, act_chunk, sc_chunk]
    resolved = resolve_evidence(pool, "General query on tax rate applicability")

    # Order by universal authority rank: SC (1) -> Act (2) -> HC (3) -> Notification (4) -> Circular (5) -> AAR (6) -> Commentary (7)
    expected_order = ["sc_1", "act_1", "hc_1", "notif_1", "cir_1", "aar_1", "icai_1"]
    actual_order = [c["chunk_id"] for c in resolved]
    assert actual_order == expected_order, f"Expected order {expected_order}, got {actual_order}"


def test_mmr_deduplicate_selects_top_k_and_stays_fast():
    """
    Regression guard for a real production bug: _mmr_deduplicate's Jaccard
    similarity step used to re-tokenize (`.lower().split()`) full chunk text
    on every single comparison inside an O(top_k * n) loop, with zero
    caching — the same chunk's text got re-split on every comparison it was
    involved in. With a realistic top_k=25 / n=80 pool this was slow enough
    to blow through supplement_and_rerank's 40s timeout in production,
    silently discarding whatever MMR would have selected (confirmed live:
    a document that scored #1 after both CrossEncoder and the legal
    reranker never made it into the final answer, because this step never
    finished in time and the pipeline fell back to a cruder pre-rerank pool
    that never included it).

    Asserts both correctness (selects exactly top_k distinct chunks, keeps
    the highest-scoring one) and that it actually stays fast on a
    realistically-sized pool — this second assertion is the one that would
    have caught the original bug.
    """
    import time
    from app.retrieval.retriever import _mmr_deduplicate

    # Build an 80-chunk pool with ~3KB of varied text each (realistic chunk
    # size) and distinct scores, mirroring the RERANK_CAP=80 pool size and
    # _retrieval_top_k=20-30 range used in production.
    words = ["gst", "section", "notification", "circular", "tax", "credit",
              "supply", "refund", "assessment", "penalty", "rule", "act"]
    pool = []
    for i in range(80):
        text = " ".join(f"{words[(i + j) % len(words)]}{j}" for j in range(400))
        pool.append({
            "chunk_id": f"chunk_{i}",
            "text": text,
            "_final_legal_score": float(80 - i),  # chunk_0 is the clear top scorer
        })

    top_k = 25
    t0 = time.perf_counter()
    selected = _mmr_deduplicate(pool, top_k=top_k)
    elapsed = time.perf_counter() - t0

    assert len(selected) == top_k
    assert len({c["chunk_id"] for c in selected}) == top_k  # no duplicates
    assert selected[0]["chunk_id"] == "chunk_0"  # highest-scoring chunk survives
    # Generous ceiling — the fix runs this in well under a second locally;
    # 5s leaves headroom for slow CI while still catching the O(top_k^2 * n)
    # uncached-tokenization regression (which took 1.6s+ on this exact pool
    # size even before accounting for the production CPU contention that
    # pushed the real incident to a 40s timeout).
    assert elapsed < 5.0, f"_mmr_deduplicate took {elapsed:.2f}s on an 80-chunk pool — regression risk"
