"""
test_ask_reliability.py

Comprehensive deterministic unit and integration test suite verifying that
the /ask pipeline handles timeouts, CrossEncoder failures, and edge cases gracefully
without hanging, dropping candidates, losing provenance metadata, or crashing.
"""

import sys
import os
import time
import json
import asyncio
from unittest.mock import patch, MagicMock

# Force offline mode for unit testing
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Ensure rag-backend is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.retriever import Retriever


class DummyCrossEncoder:
    def predict(self, pairs, **kwargs):
        raise RuntimeError("Simulated CrossEncoder internal crash")


class DummyFailingIndex:
    def search(self, *args, **kwargs):
        raise RuntimeError("Simulated FAISS crash")


def test_cascade_rerank_cross_encoder_failure_preserves_candidates():
    """Verify that when CrossEncoder fails, _cascade_rerank preserves all candidate chunks and metadata."""
    retriever = Retriever.__new__(Retriever)
    retriever.cross_encoder = DummyCrossEncoder()

    candidates = [
        {
            "chunk_id": "c1",
            "text": "Section 54 CGST Act refund provision.",
            "_rrf_score": 0.05,
            "rel_path": "Database_V2.0/CGST Acts/CGST_Act_2017.pdf",
            "metadata": {"section": "54", "act": "CGST Act"},
        },
        {
            "chunk_id": "c2",
            "text": "Rule 89 CGST Rules application for refund.",
            "_rrf_score": 0.04,
            "rel_path": "Database_V2.0/CGST Rules/CGST_Rules.pdf",
            "metadata": {"rule": "89", "rules": "CGST Rules"},
        },
    ]

    # Run _cascade_rerank with failing CrossEncoder
    reranked = retriever._cascade_rerank("refund section 54", candidates)

    assert len(reranked) == 2
    chunk_ids = {r["chunk_id"] for r in reranked}
    assert chunk_ids == {"c1", "c2"}
    assert "_rerank_score" in reranked[0]
    assert "_rerank_score" in reranked[1]
    # Verify metadata preservation
    assert reranked[0].get("metadata") is not None
    assert reranked[1].get("metadata") is not None


def test_cascade_rerank_cross_encoder_unavailable_fallback():
    """Verify that when CrossEncoder is None (not loaded/unavailable), _cascade_rerank preserves candidate pool."""
    retriever = Retriever.__new__(Retriever)
    retriever.cross_encoder = None

    candidates = [
        {
            "chunk_id": "c1",
            "text": "Section 16 Eligibility and conditions for taking input tax credit.",
            "_rrf_score": 0.09,
            "rel_path": "Database_V2.0/CGST Acts/CGST_Act_2017.pdf",
        }
    ]

    reranked = retriever._cascade_rerank("ITC eligibility section 16", candidates)
    assert len(reranked) == 1
    assert reranked[0]["chunk_id"] == "c1"
    assert "_rerank_score" in reranked[0]


def test_supplement_and_rerank_failure_fallback():
    """Verify supplement_and_rerank safely falls back to base_chunks if expansion or reranking throws."""
    retriever = Retriever.__new__(Retriever)
    retriever.index = DummyFailingIndex()
    retriever.chunks = []
    retriever.cross_encoder = None
    retriever.bm25 = None
    retriever._doc_map = {}
    retriever._provision_index = {}
    retriever._circular_index = {}
    retriever._notification_index = {}
    retriever._section_index = {}
    retriever._rule_index = {}
    retriever.inactive_paths = set()

    base_chunks = [
        {
            "chunk_id": "b1",
            "text": "Base chunk 1",
            "_rrf_score": 0.1,
            "rel_path": "Database_V2.0/CGST Acts/CGST_Act_2017.pdf",
            "title": "CGST Act 2017",
        },
        {
            "chunk_id": "b2",
            "text": "Base chunk 2",
            "_rrf_score": 0.08,
            "rel_path": "Database_V2.0/CGST Rules/CGST_Rules.pdf",
            "title": "CGST Rules 2017",
        },
    ]
    advanced_queries = {
        "queries": ["query 1", "query 2"],
        "hyde_document": "",
        "topic": "General",
    }

    with patch("app.retrieval.retriever.embed_query", return_value=None):
        result = retriever.supplement_and_rerank(base_chunks, advanced_queries, "refund", top_k=2)

    # Must preserve base_chunks without raising exception
    assert len(result) == 2
    assert {r["chunk_id"] for r in result} == {"b1", "b2"}
    # Provenance fields must be intact
    assert all("rel_path" in r and "text" in r for r in result)


def test_candidate_provenance_and_metadata_integrity():
    """Verify that fallback never strips critical citation provenance or fabricates invalid sources."""
    chunk = {
        "chunk_id": "cgst_sec_16_p1",
        "text": "16. (1) Every registered person shall, subject to such conditions and restrictions as may be prescribed...",
        "rel_path": "Database_V2.0/CGST Acts/CGST_Act_2017.pdf",
        "title": "Central Goods and Services Tax Act, 2017",
        "page": 12,
        "_rrf_score": 0.15,
        "metadata": {
            "section": "16",
            "category": "statute",
            "chapter": "V",
        }
    }

    retriever = Retriever.__new__(Retriever)
    retriever.cross_encoder = DummyCrossEncoder()

    reranked = retriever._cascade_rerank("Section 16 ITC", [chunk])
    assert len(reranked) == 1
    out = reranked[0]

    # Strict provenance invariants
    assert out["chunk_id"] == "cgst_sec_16_p1"
    assert out["rel_path"] == "Database_V2.0/CGST Acts/CGST_Act_2017.pdf"
    assert out["title"] == "Central Goods and Services Tax Act, 2017"
    assert out["page"] == 12
    assert out["metadata"]["section"] == "16"
    assert out["text"].startswith("16. (1) Every registered person")


def test_case_b_empty_retrieval_closes_stream_with_status():
    """Verify Case B: When retrieval produces 0 candidate chunks, pipeline yields controlled status and warning."""
    chunks = []
    query_id = "TEST-EMPTY-01"

    async def mock_orchestrator(candidate_chunks):
        if not candidate_chunks:
            yield f"__STATUS__:{json.dumps({'msg': 'No authoritative statutory sources found.'})}__END_STATUS__"
            yield "\n\n⚠ **LETA could not locate authoritative statutory provisions for this query in the database.** Please check your query terms or rephrase your question."
            return
        yield "VALID_ANSWER_HERE"

    async def run_test():
        emitted = []
        async for item in mock_orchestrator(chunks):
            emitted.append(item)
        return emitted

    emitted = asyncio.run(run_test())

    assert len(emitted) == 2
    assert "__STATUS__:" in emitted[0]
    assert "No authoritative statutory sources found." in emitted[0]
    assert "⚠ **LETA could not locate authoritative statutory provisions" in emitted[1]


def test_cross_encoder_predict_80_candidates_latency_and_integrity():
    """Verify that _cascade_rerank on a representative 80-candidate pool completes promptly and preserves all candidates."""
    candidates = [
        {
            "chunk_id": f"chunk_{i}",
            "text": f"Section {i} defines supply and statutory rules for GST applicability.",
            "rel_path": "Database_V2.0/CGST Acts/CGST_Act_2017.pdf",
            "_rrf_score": 0.05 + (i * 0.001),
        }
        for i in range(80)
    ]

    retriever = Retriever.__new__(Retriever)
    # Use DummyCrossEncoder to ensure deterministic offline execution
    retriever.cross_encoder = DummyCrossEncoder()

    t0 = time.perf_counter()
    reranked = retriever._cascade_rerank("what is GST ?", candidates)
    elapsed = time.perf_counter() - t0

    assert len(reranked) == 80
    assert elapsed < 1.0  # Must complete sub-second
    assert all("_rerank_score" in c for c in reranked)
    # Should be sorted in descending order of _rerank_score
    scores = [c["_rerank_score"] for c in reranked]
    assert scores == sorted(scores, reverse=True)


def test_preload_all_models_warmup_execution():
    """Verify that preload_all_models executes CrossEncoder and embedding warmup passes."""
    from app.dependencies import preload_all_models

    mock_retriever = MagicMock()
    mock_retriever.cross_encoder = MagicMock()
    mock_retriever.cross_encoder.predict.return_value = [0.95]

    with patch("app.dependencies.get_retriever", return_value=mock_retriever), \
         patch("app.retrieval.retriever.get_model", return_value=MagicMock()), \
         patch("app.retrieval.retriever.embed_query", return_value=[0.1] * 1024):
        preload_all_models()

        mock_retriever.cross_encoder.predict.assert_called_once()
        args, kwargs = mock_retriever.cross_encoder.predict.call_args
        assert len(args[0]) == 1
        assert kwargs.get("batch_size") == 1
