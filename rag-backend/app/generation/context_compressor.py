"""
LETA TEC Context Compressor — Stage 4 of TITAN architecture.

Reduces injected LLM context from the raw 80 KB chunk dump to a
targeted ~8 KB focused-excerpt block. The compressor:

  1. Scores every chunk for query relevance (token overlap, no extra model call)
  2. Extracts the best sentence window from each chunk
  3. Caps total output at MAX_COMPRESSED_CHARS

This sits between retriever and synthesizer. build_context() is still
used for source-citation metadata; compress_context() provides the
dense factual block the LLM actually reasons over.
"""
import os
import re
from typing import List

MAX_COMPRESSED_CHARS_QA    = 18000   # ~4 500 tokens — Q&A mode
MAX_COMPRESSED_CHARS_DRAFT = 20000   # ~5 000 tokens — draft mode needs full statutory text
MAX_EXCERPT_CHARS_QA       = 1200    # per-chunk window Q&A — full statutory provisions fit
MAX_EXCERPT_CHARS_DRAFT    = 1400    # per-chunk window draft — needs verbatim statutory paragraphs
MAX_CHUNKS_USED_QA         = 20      # Q&A cap
MAX_CHUNKS_USED_DRAFT      = 25      # draft uses all retrieved chunks


def _query_tokens(query: str) -> set:
    """Lower-cased word stems ≥ 3 chars from the query."""
    return set(re.findall(r'\b[a-z]{3,}\b', query.lower()))


def _overlap_score(text: str, q_tokens: set) -> float:
    """Jaccard-like token overlap — fast, no embeddings needed."""
    if not text or not q_tokens:
        return 0.0
    chunk_tokens = set(re.findall(r'\b[a-z]{3,}\b', text.lower()))
    return len(chunk_tokens & q_tokens) / max(len(q_tokens), 1)


def _best_window(text: str, q_tokens: set, max_chars: int = MAX_EXCERPT_CHARS_QA) -> str:
    """
    Split text into sentences and return the highest-scoring 2-sentence
    window (± 1 sentence context around the best match).
    Falls back to a straight head-truncation if no sentence found.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= 2:
        return text[:max_chars]

    best_idx = max(range(len(sentences)), key=lambda i: _overlap_score(sentences[i], q_tokens))
    start = max(0, best_idx - 1)
    end = min(len(sentences), best_idx + 2)
    window = " ".join(sentences[start:end])

    if len(window) > max_chars:
        window = window[:max_chars] + "…"
    return window


def compress_context(chunks: List[dict], query: str, is_draft: bool = False) -> str:
    """
    Build a focused, compressed context string from retrieved chunks.

    Draft mode uses larger limits so verbatim statutory text and full judgment
    paragraphs fit — needed for 5000-word SCN replies.

    Args:
        chunks:   Retrieved chunk dicts (as returned by retriever.search)
        query:    Original user query string
        is_draft: True for SCN replies / appeals / drafting mode

    Returns:
        Compressed context string.
    """
    if not chunks:
        return "No relevant statutory documents retrieved."

    max_total   = MAX_COMPRESSED_CHARS_DRAFT if is_draft else MAX_COMPRESSED_CHARS_QA
    max_excerpt = MAX_EXCERPT_CHARS_DRAFT    if is_draft else MAX_EXCERPT_CHARS_QA
    max_chunks  = MAX_CHUNKS_USED_DRAFT      if is_draft else MAX_CHUNKS_USED_QA

    q_tokens = _query_tokens(query)

    # Score each chunk: combine reranker score with query-overlap score
    scored = []
    for c in chunks:
        rerank = float(c.get("_final_legal_score", c.get("_rerank_score", 0.0)) or 0.0)
        text = c.get("text", "")
        overlap = _overlap_score(text, q_tokens)
        combined = 0.6 * rerank + 0.4 * overlap
        scored.append((combined, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_chunks]

    parts: List[str] = []
    total = 0

    for rank, (score, chunk) in enumerate(top, 1):
        if total >= max_total:
            break

        text = chunk.get("text", "").strip()
        source = os.path.basename(chunk.get("source", "Unknown"))
        page = chunk.get("page", "N/A")

        excerpt = _best_window(text, q_tokens, max_chars=max_excerpt)

        remaining = max_total - total
        if len(excerpt) > remaining:
            excerpt = excerpt[:remaining] + "…"

        entry = f"[{rank}] {source} p.{page}\n{excerpt}"
        parts.append(entry)
        total += len(entry) + 4  # +4 for separator

    return "\n\n---\n\n".join(parts)
