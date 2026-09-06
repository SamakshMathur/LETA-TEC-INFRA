"""
Debug endpoints for RetrievalTrace inspection.

Routes:
  GET /debug/traces                    — list last 50 traces (summary)
  GET /debug/trace/{query_id}          — full trace for one query
  GET /debug/trace/{query_id}/stages   — just the stage-by-stage score snapshots

These endpoints are INTERNAL ONLY. They are protected by a secret header
(X-Debug-Token) to prevent public exposure of retrieval internals.

Set the token via environment variable: LETA_DEBUG_TOKEN
If the env var is not set, the endpoints return 403 (fail-closed).
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.retrieval.retrieval_trace import get_trace, list_traces

logger = logging.getLogger(__name__)
router = APIRouter()

# Fail-closed: if LETA_DEBUG_TOKEN is not set, all debug endpoints return 403.
_DEBUG_TOKEN = os.getenv("LETA_DEBUG_TOKEN", "")


def _check_token(x_debug_token: Optional[str]):
    if not _DEBUG_TOKEN:
        raise HTTPException(status_code=403, detail="Debug endpoints not configured (LETA_DEBUG_TOKEN not set)")
    if x_debug_token != _DEBUG_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid debug token")


@router.get("/debug/traces")
def get_recent_traces(
    limit: int = 50,
    x_debug_token: Optional[str] = Header(None),
):
    """
    List the most recent queries with summary info.

    Returns: list of {query_id, query (truncated), elapsed_ms, topic, final_count, cache_hit}
    Newest first.

    CloudWatch Logs Insights alternative (no auth needed in production):
      fields trace_type, query_id, query, elapsed_ms, @timestamp
      | filter trace_type = "retrieval_trace"
      | sort @timestamp desc
      | limit 50
    """
    _check_token(x_debug_token)
    limit = max(1, min(limit, 200))
    return {"traces": list_traces(limit)}


@router.get("/debug/trace/{query_id}")
def get_full_trace(
    query_id: str,
    x_debug_token: Optional[str] = Header(None),
):
    """
    Full provenance trace for one query.

    Contains:
      - preprocessing: query refinement, sub-queries, HyDE, taxonomy, domain route
      - stages: ordered (chunk_id, score) snapshots at every pipeline stage
      - all_chunks: per-chunk records with FAISS/BM25/TF-IDF/RRF/CrossEncoder/
                    LegalReranker/MMR/selection data
      - documents: per-document aggregation (how many chunks, best score, sources)
      - validation: authority coverage, Layer 6 injections
      - answer: model, mode, latency, cache_hit

    Use this to answer: "Why did LETA TEC give this answer?"
    Starting point: look at stages.final vs stages.faiss — was the correct document
    in the FAISS top-20? If yes, track where it dropped out (CrossEncoder? MMR?).
    """
    _check_token(x_debug_token)
    trace = get_trace(query_id)
    if trace is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trace not found for query_id={query_id}. Traces expire after 500 queries or server restart."
        )
    return trace


@router.get("/debug/trace/{query_id}/stages")
def get_trace_stages(
    query_id: str,
    x_debug_token: Optional[str] = Header(None),
):
    """
    Just the stage-by-stage ranking snapshots for one query.
    Lighter than the full trace — useful for quick "where did it go wrong?" analysis.

    Each stage is an ordered list of {chunk_id, rank, score, document_id}.
    Key stages to compare:
      faiss           → raw semantic search result
      bm25            → raw keyword search result
      rrf             → fused ranking
      after_crossencoder  → after CrossEncoder reranking
      after_legalreranker → after LegalReranker
      post_mmr        → after MMR deduplication
      final           → what the LLM actually received

    Example: if Section 17(5) is #2 in faiss but #8 in after_crossencoder,
    the CrossEncoder is the bottleneck — not FAISS.
    """
    _check_token(x_debug_token)
    trace = get_trace(query_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found: {query_id}")

    # Enrich each stage snapshot with document_id from the all_chunks map
    chunk_to_doc = {
        c["chunk_id"]: {"doc": c["document_id"], "type": c["document_type"]}
        for c in trace.get("all_chunks", [])
    }

    stages = {}
    for stage_name, snap in trace.get("stages", {}).items():
        enriched = []
        for entry in snap:
            cid = entry.get("chunk_id", "")
            doc_info = chunk_to_doc.get(cid, {})
            enriched.append({
                "rank":      entry.get("rank"),
                "chunk_id":  cid[:24],
                "doc":       doc_info.get("doc", "?"),
                "type":      doc_info.get("type", "?"),
                "score":     entry.get("score"),
            })
        stages[stage_name] = enriched

    return {
        "query_id": query_id,
        "query":    trace.get("query", "")[:200],
        "stages":   stages,
        "stage_counts": trace.get("stage_counts", {}),
    }
