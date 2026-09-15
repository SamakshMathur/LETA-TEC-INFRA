import pytest
import subprocess
import sys

def test_crossencoder_in_retriever_subprocess():
    """
    Verify that CrossEncoder.predict completes without SIGSEGV inside the initialized Retriever process
    using generic candidate pairs derived directly from the loaded index.
    """
    cmd = [
        sys.executable,
        "-c",
        """
import sys
import os
from app.dependencies import get_retriever

retriever = get_retriever()
assert len(retriever.chunks) >= 80, f"Expected at least 80 chunks in index, got {len(retriever.chunks)}"

# Generic probe query and candidate pairs
generic_query = "What are the rules and statutory conditions for tax compliance?"
pairs = [(generic_query, (c.get("context_text") or c.get("text", ""))[:512]) for c in retriever.chunks[:80]]

scores = retriever.cross_encoder.predict(pairs, show_progress_bar=False, batch_size=32)
assert len(scores) == 80, f"Expected 80 scores, got {len(scores)}"
print("CROSSENCODER_SUBPROCESS_SUCCESS")
sys.exit(0)
"""
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"CrossEncoder failed with code {proc.returncode}:\nStdout: {proc.stdout}\nStderr: {proc.stderr}"
    assert "CROSSENCODER_SUBPROCESS_SUCCESS" in proc.stdout


def test_supplement_and_rerank_subprocess():
    """
    Verify that supplement_and_rerank completes end-to-end without SIGSEGV or timeout
    for a generic query and dynamically retrieved candidate chunks.
    """
    cmd = [
        sys.executable,
        "-c",
        """
import sys
import os
from app.dependencies import get_retriever
from app.retrieval.retrieval_trace import RetrievalTrace

retriever = get_retriever()
generic_query = "Applicability and procedure for statutory refund claims"
trace = RetrievalTrace(query_id="TEST-STABILITY-GENERIC", query=generic_query)

fast_chunks = retriever.search(generic_query, top_k=25, skip_rerank=True, trace=trace)
assert len(fast_chunks) > 0, "Expected non-empty fast retrieval candidates"

advanced_queries = {
    'queries': [
        generic_query,
        'statutory refund procedure guidelines',
        'timelines and documentation for refund application'
    ],
    'hyde_document': 'Statutory refund claims must be filed in accordance with prescribed procedures.',
    'topic': 'Refund',
    'subtopic': 'General Refund'
}

final_chunks = retriever.supplement_and_rerank(
    fast_chunks, advanced_queries, generic_query, top_k=25, trace=trace
)
assert len(final_chunks) > 0, "Expected non-empty final chunks after supplement_and_rerank"

log_dict = trace.to_log_dict()
assert "after_crossencoder" in log_dict.get("stage_counts", {}), "Missing after_crossencoder in trace stage_counts"
assert "final" in log_dict.get("stage_counts", {}), "Missing final in trace stage_counts"
print("SUPPLEMENT_RERANK_SUBPROCESS_SUCCESS")
sys.exit(0)
"""
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"supplement_and_rerank failed with code {proc.returncode}:\nStdout: {proc.stdout}\nStderr: {proc.stderr}"
    assert "SUPPLEMENT_RERANK_SUBPROCESS_SUCCESS" in proc.stdout


def test_mmr_termination_on_negative_scores():
    """
    Verify that _mmr_deduplicate terminates deterministically and selects top_k candidates
    even when all candidates have negative CrossEncoder / legal reranker scores (e.g. < -1.0).
    """
    from app.retrieval.retriever import _mmr_deduplicate
    import time

    # Create 50 synthetic candidates with all negative scores
    candidates = [
        {
            "chunk_id": f"chunk_{i}",
            "text": f"This is candidate document number {i} discussing legal provision variation {i % 5}.",
            "_final_legal_score": -2.0 - (i * 0.1),  # Scores from -2.0 to -6.9 (all < -1.0)
        }
        for i in range(50)
    ]

    t0 = time.monotonic()
    selected = _mmr_deduplicate(candidates, top_k=20, lambda_param=0.7)
    elapsed_ms = (time.monotonic() - t0) * 1000.0

    assert len(selected) == 20, f"Expected 20 selected items, got {len(selected)}"
    assert elapsed_ms < 200, f"MMR took too long ({elapsed_ms:.2f}ms), expected <200ms"
    # Verify first selected is the candidate with highest relevance (-2.0)
    assert selected[0]["chunk_id"] == "chunk_0"
