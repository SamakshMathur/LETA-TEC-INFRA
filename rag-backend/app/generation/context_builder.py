"""
Context builder — assembles retrieved chunks into the LLM context block.

Phase 2 citation binding: every source gets a short [S1], [S2], ... marker.
The system prompt instructs the model to tag each claim inline with the
marker of the chunk it's drawn from, e.g. "ITC is blocked [S3]".
Server-side post-processing (parse_markers) then resolves markers to real
document links deterministically — no guessing, no regex scoring.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from typing import List, Dict, Any


# ── Public API ────────────────────────────────────────────────────────────────

def build_context(chunks: List[Dict[str, Any]], is_draft: bool = False) -> str:
    """
    Build the LLM context block from retrieved chunks.

    Each source is labelled with [S1], [S2], ... so the model can cite inline.
    The model's system prompt instructs it to append the marker of any chunk
    it draws a claim from.
    """
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks):
        marker  = f"[S{i + 1}]"
        rel     = _rel(c)
        doc     = os.path.basename(rel) if rel else (c.get("source") or "unknown document")
        page    = c.get("page")
        page_str = f", page {page}" if page else ""
        text    = c.get("text") or c.get("embed_text") or ""
        parts.append(
            f"SOURCE {marker} — {doc}{page_str}\n{text}"
        )
    return "\n\n".join(parts)


def build_marker_map(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return the ordered list of {marker → chunk metadata} used to resolve
    [S1], [S2], ... references that appear in the model's output.

    Call this with the SAME chunks list passed to build_context so indices match.
    """
    result = []
    for i, c in enumerate(chunks):
        marker   = f"[S{i + 1}]"
        rel      = _rel(c)
        doc      = os.path.basename(rel) if rel else (c.get("source") or "unknown document")
        enc_path = urllib.parse.quote(rel.replace("\\", "/"), safe="") if rel else ""
        url      = (
            f"/api/documents/view_by_path?path={enc_path}"
            if enc_path else "#"
        )
        result.append({
            "marker":   marker,
            "chunk_id": c.get("chunk_id") or (c.get("metadata") or {}).get("chunk_id", ""),
            "title":    doc,
            "rel_path": rel,
            "page":     c.get("page", 1),
            "url":      url,
        })
    return result


def parse_markers(answer: str, marker_map: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract every [Sn] marker actually present in the model's answer and map
    each to the corresponding chunk metadata via a direct index lookup.

    Returns a dict with:
      "citations": list of resolved entries (in order of first appearance)
      "unresolved": list of marker strings the model used but that have no
                    corresponding chunk (should be flagged, not silently guessed)
    """
    found_markers = list(dict.fromkeys(re.findall(r'\[S(\d+)\]', answer)))  # ordered, deduped
    index_by_n   = {str(i + 1): entry for i, entry in enumerate(marker_map)}

    citations  = []
    unresolved = []
    for n in found_markers:
        marker_str = f"[S{n}]"
        if n in index_by_n:
            citations.append(index_by_n[n])
        else:
            unresolved.append(marker_str)

    return {"citations": citations, "unresolved": unresolved}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rel(chunk: Dict[str, Any]) -> str:
    """Extract the rel_path from a chunk, checking metadata sub-dict."""
    return (
        chunk.get("rel_path")
        or (chunk.get("metadata") or {}).get("rel_path")
        or chunk.get("source")
        or ""
    )
