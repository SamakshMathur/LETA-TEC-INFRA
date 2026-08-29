"""
Shared RAG pipeline helpers.

Pure-Python, no I/O — used by both /ask (streaming) and /ask-sync (blocking)
so the core business logic lives in one place rather than being duplicated and
allowed to drift between the two endpoints.

Functions here have NO side effects: they take data in, return data out.
All I/O (retriever calls, DB reads, cache lookups) stays in the endpoint
handlers so the streaming vs blocking mechanics remain straightforward.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword-based query expansion
# ---------------------------------------------------------------------------

def build_keyword_queries(query: str, is_draft: bool) -> dict:
    """
    Build 4-angle sub-queries covering statutory / circular / notification /
    case-law angles without an LLM call.

    Used by both /ask (replaced LLM expansion that was causing 75s pipeline
    hangs) and /ask-sync (always used keyword expansion).

    Returns the same shape as generate_advanced_queries() so supplement_and_rerank
    and search() receive consistent input regardless of which endpoint calls them.
    """
    if is_draft:
        return {
            "queries": [
                query,
                query + " section rule act provisions conditions eligibility liability",
                query + " high court supreme court judgment held ruling decision AAR",
                query + " CBIC circular notification clarification instruction",
            ],
            "hyde_document": "",
            "topic": "General",
            "subtopic": None,
        }
    return {
        "queries": [
            query,
            query + " section CGST IGST Act rule proviso conditions eligibility",
            query + " CBIC Circular clarification instruction guidance",
            query + " GST Notification Central Tax Rate exemption 2017 2018 2019 2020 2021 2022 2023 2024 2025",
        ],
        "hyde_document": "",
        "topic": "General",
        "subtopic": None,
    }


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def assemble_full_rag_context(
    *,
    citation_block: str,
    compressed_block: str,
    history_context: str = "",
    cross_session_context: str = "",
    calc_block: str = "",
    is_followup: bool = False,
) -> str:
    """
    Assemble the complete context string sent to the LLM.

    Keeps the ordering consistent between /ask and /ask-sync and makes the
    structure visible in one place:
        [cross-session memory] [chat history] [citation block] [calc] [compressed]
    """
    parts: list[str] = []

    if cross_session_context:
        parts.append(
            f"--- MEMORY FROM PREVIOUS SESSIONS ---\n{cross_session_context}\n"
            "--- END MEMORY ---"
        )

    if history_context:
        label = (
            "⚠ ACTIVE CONVERSATION — CONTINUE FROM HERE. Do NOT restart with basics "
            "already covered. Directly continue the specific legal discussion in progress."
            if is_followup
            else "CHAT HISTORY"
        )
        parts.append(f"--- {label} ---\n{history_context}\n--- END HISTORY ---")

    parts.append(citation_block)

    if calc_block:
        parts.append(calc_block)

    parts.append(
        "--- COMPRESSED STATUTORY EXCERPTS (for quick reference) ---\n\n"
        + compressed_block
    )

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Source metadata builder
# ---------------------------------------------------------------------------

def build_unique_sources(chunks: list[dict[str, Any]], max_sources: int = 8) -> list[dict]:
    """
    Convert retrieved chunks into the source-metadata list shown to the user.

    Deduplicates by (rel_path, page), sorts by rerank score, and caps at
    max_sources.  Same logic previously duplicated in /ask (stream_and_save)
    and /ask-sync.
    """
    import os
    import urllib.parse as _urlparse

    seen: set = set()
    sources: list[dict] = []

    for chunk in chunks:
        _rel = chunk.get("rel_path", "") or chunk.get("metadata", {}).get("rel_path", "") or chunk.get("source", "")
        _page = chunk.get("page", 0)
        key = (_rel, _page)
        if key in seen:
            continue
        seen.add(key)

        _raw_src = chunk.get("source", "") or chunk.get("metadata", {}).get("source", "")
        _rel_path = chunk.get("rel_path", "") or chunk.get("metadata", {}).get("rel_path", "")
        _basename = os.path.basename(_rel_path) if _rel_path else os.path.basename(_raw_src)
        _enc_path = _urlparse.quote(_rel_path.replace("\\", "/"), safe="") if _rel_path else ""
        _enc_name = _urlparse.quote(_basename, safe="")
        _url = (
            f"/api/documents/view_by_path?path={_enc_path}"
            if _enc_path
            else f"/api/documents/view?category=all&filename={_enc_name}"
        )
        _snippet = (chunk.get("text") or "").strip()

        sources.append({
            "title":    _basename or "Document",
            "page":     _page or 1,
            "url":      _url,
            "rel_path": _rel_path,
            "score":    float(chunk.get("_rerank_score", 0)),
            "snippet":  _snippet[:800] if _snippet else "",
        })

        if len(sources) >= max_sources * 3:  # collect extra for sorting
            break

    sources.sort(key=lambda s: s.get("score", 0), reverse=True)
    return sources[:max_sources]
