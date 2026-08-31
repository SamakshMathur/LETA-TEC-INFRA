"""
Context builder — assembles retrieved chunks into the LLM context block.

Phase 2 citation binding: every source is labelled SOURCE [S1], [S2], …
in the context block so the model knows which chunk is which.
The CITATION BINDING RULE in the system prompt instructs the model to tag
each claim inline with *parenthesised* markers: (S1), (S2), …  (not [S1]).
Server-side post-processing (parse_markers) scans for those parenthesised
markers and resolves each to real document metadata — no guessing, no regex
scoring.  The context-block labels use square brackets; the inline output
markers use parentheses — this is intentional: it lets parse_markers
unambiguously distinguish output citations from the label headers.
"""
from __future__ import annotations

import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Character caps — tuned for TITAN sub-5s target.
# Q&A mode: 15 000 chars. Draft mode: 30 000 chars (needed for 5000-word replies).
MAX_CONTEXT_CHARS_QA    = 18000   # was 15000 — circulars are dense, more context helps
MAX_CONTEXT_CHARS_DRAFT = 30000
MAX_CHUNK_CHARS_QA      = 1400   # was 1000 — prevents circulars being truncated mid-clause
MAX_CHUNK_CHARS_DRAFT   = 1800  # longer excerpts needed for verbatim statutory reproduction

# ─────────────────────────────────────────────────────────────
# Citation extraction patterns — used to build the registry
# ─────────────────────────────────────────────────────────────
_CITATION_PATTERNS = [
    r'\bSection\s+\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bSec\.\s*\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bRule\s+\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bArticle\s+\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bNotification\s+No\.?\s*[\d]+\s*/\s*[\d\-\w]+(?:-\w+)*',
    r'\bCircular\s+No\.?\s*[\d]+\s*/\s*[\d\-\w]+(?:/[\d\w]+)*',
    r'\bOrder\s+No\.?\s*[\d/\-\w]+',
    r'\bSchedule\s+[IVX]+',
]


def extract_citations(text: str) -> list[str]:
    """Extract all statutory citations from a chunk of text."""
    found = []
    for pattern in _CITATION_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            cleaned = " ".join(m.split())
            if cleaned not in found:
                found.append(cleaned)
    return found


def extract_case_law_name(source_path: str, text: str) -> str | None:
    """
    Extract the case law name from the file path or chunk text.
    Handles High Court, Supreme Court, and AAR rulings.
    """
    filename = os.path.basename(source_path)
    clean_name = re.sub(r'\.(pdf|docx|txt)$', '', filename, flags=re.IGNORECASE)

    parts = _path_segments(source_path)
    if "high court case laws" in parts or "supreme court case laws" in parts:
        clean_name = re.sub(r'^\d+[\s\-_.]*', '', clean_name)
        if clean_name.strip():
            return clean_name.strip()

    if "aar" in parts:
        return f"AAR Ruling: {clean_name.strip()}"

    first_lines = "\n".join(text.split("\n")[:4])
    vs_match = re.search(r'([A-Z][A-Za-z\s,\.]{3,40}\s+v(?:s\.?|ersus)\s+[A-Z][A-Za-z\s,\.]{3,40})', first_lines)
    if vs_match:
        return vs_match.group(1).strip()

    return None


def build_citation_registry(chunks: list[dict], is_draft: bool = False) -> str:
    """
    Builds the VERIFIED CITATION REGISTRY block that is injected
    at the very top of the LLM context.
    """
    sections = []
    rules = []
    notifications = []
    circulars = []
    case_laws = []

    for c in chunks:
        raw_source = c.get('source', '') or c.get('metadata', {}).get('source', '')
        rel_path = c.get('rel_path', '') or c.get('metadata', {}).get('rel_path', '')
        source_path = rel_path if rel_path else raw_source

        text = c.get('text', '')

        for cit in extract_citations(text):
            cit_lower = cit.lower()
            if cit_lower.startswith(('section', 'sec.')) and cit not in sections:
                sections.append(cit)
            elif cit_lower.startswith('rule') and cit not in rules:
                rules.append(cit)
            elif cit_lower.startswith('notification') and cit not in notifications:
                notifications.append(cit)
            elif cit_lower.startswith('circular') and cit not in circulars:
                circulars.append(cit)

        case_name = extract_case_law_name(source_path, text)
        if case_name and case_name not in case_laws:
            case_laws.append(case_name)

    lines = [
        "VERIFIED CITATIONS AVAILABLE IN RETRIEVED SOURCES:",
        f"  Sections     : {', '.join(sections[:8]) or 'None retrieved'}",
        f"  Rules        : {', '.join(rules[:6]) or 'None retrieved'}",
        f"  Notifications: {', '.join(notifications[:5]) or 'None retrieved'}",
        f"  Circulars    : {', '.join(circulars[:5]) or 'None retrieved'}",
        f"  Case Laws    : {', '.join(case_laws[:4]) or 'None retrieved'}",
    ]

    if not case_laws and is_draft:
        lines.append(
            "\n⚠️  CRITICAL FOR DRAFTING: No case law documents were retrieved for this query.\n"
            "DO NOT INVENT ANY CASE CITATIONS (no fictitious parties, citations, or court names).\n"
            "Use statutory provisions from TRUTH RULES only. Mark each argument:\n"
            "[No supporting case law retrieved — practitioner to verify from database]"
        )

    lines.append("INSTRUCTION: Every item above MUST appear in the draft letter with verbatim extract.")
    lines.append("Missing even one is a drafting failure. Use the SOURCE DOCUMENTS below to get the text.")
    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def build_context(chunks: list[dict], is_draft: bool = False) -> str:
    """
    Builds a citation-ready context block from retrieved chunks.
    Draft mode uses larger limits (30 000 chars, 1800 chars/chunk) and
    includes the case law name registry for hallucination grounding.
    """
    if not chunks:
        return "No relevant documents found."

    max_context = MAX_CONTEXT_CHARS_DRAFT if is_draft else MAX_CONTEXT_CHARS_QA
    max_chunk   = MAX_CHUNK_CHARS_DRAFT   if is_draft else MAX_CHUNK_CHARS_QA

    base_url = "/api/documents/view"

    # ── Step 0: Exact & Normalized Deduplication + Jaccard evaluation ──
    seen_texts = set()
    unique_chunks = []
    pid = os.getpid()

    for c in chunks:
        raw_text = c.get("text", "")
        norm_text = " ".join(raw_text.lower().strip().split())

        # Deduplicate exact / normalized texts
        if norm_text in seen_texts:
            logger.info(f"DEDUPLICATION: Skipped exact/normalized duplicate chunk in context builder: {c.get('chunk_id')}")
            continue

        # Jaccard evaluation check (measure and log only, do not skip)
        w_current = set(re.findall(r'\b[a-z]{3,}\b', norm_text))
        for existing in unique_chunks:
            existing_text = " ".join(existing.get("text", "").lower().strip().split())
            w_existing = set(re.findall(r'\b[a-z]{3,}\b', existing_text))
            if w_current and w_existing:
                jaccard = len(w_current & w_existing) / max(len(w_current | w_existing), 1)
                if jaccard > 0.85:
                    logger.info(
                        f"DEDUPLICATION_MEASURE process={pid} "
                        f"source1={c.get('chunk_id')} "
                        f"source2={existing.get('chunk_id')} "
                        f"jaccard={jaccard:.4f}"
                    )

        seen_texts.add(norm_text)
        unique_chunks.append(c)

    # ── Step 1: Build the Citation Registry ──────────────────
    registry = build_citation_registry(unique_chunks, is_draft=is_draft)

    # ── Step 2: Build Quotable Source Blocks ─────────────────
    context_blocks = []
    for i, c in enumerate(unique_chunks):
        raw_source = c.get('source', '') or c.get('metadata', {}).get('source', 'Unknown')
        rel_path = c.get('rel_path', '') or c.get('metadata', {}).get('rel_path', '')
        filename = os.path.basename(rel_path) if rel_path else (os.path.basename(raw_source) or 'Unknown')

        classify_path = rel_path if rel_path else raw_source
        source_type = _classify_source(classify_path)
        authority_rank = _get_authority_rank(classify_path)

        safe_filename = filename.replace(" ", "%20")
        link = f"{base_url}?category=all&filename={safe_filename}"

        rerank_score = c.get('_rerank_score', 0.0) or 0.0

        chunk_text = (c.get('context_text') or c['text']).strip()
        if len(chunk_text) > max_chunk:
            chunk_text = chunk_text[:max_chunk] + "... [truncated]"

        # Structured packet metadata assembly
        source_id = f"SRC-{i+1}"
        chunk_id = c.get("chunk_id", "N/A")
        doc_num = c.get("document_number", c.get("metadata", {}).get("document_number", "N/A"))
        doc_date = c.get("date", c.get("metadata", {}).get("date", "N/A"))
        provisions_str = ", ".join(c.get("provisions", c.get("metadata", {}).get("provisions", []))) or "N/A"

        pinned_tier = c.get("_pinned_tier", "N/A")
        retrieval_reason = f"EXPLICIT_REFERENCE ({pinned_tier})" if c.get("_pinned_by_ref", False) else "SEMANTIC"

        context_blocks.append(
            f"════════════════════════════════════════\n"
            f"SOURCE_ID: {source_id} | CHUNK_ID: {chunk_id}\n"
            f"DOCUMENT_TITLE: {filename}\n"
            f"DOCUMENT_TYPE: {source_type} | AUTHORITY_RANK: {authority_rank}\n"
            f"DOCUMENT_NUMBER: {doc_num} | DATE/YEAR: {doc_date}\n"
            f"PROVISIONS/SECTIONS: {provisions_str}\n"
            f"RETRIEVAL_REASON: {retrieval_reason}\n"
            f"RELEVANCE_SCORE: {c.get('score', 0.0):.4f} | RERANK_SCORE: {rerank_score:.4f}\n"
            f"DOCUMENT LINK: {link}\n"
            f"Page: {c.get('page', 'N/A')}\n"
            f"════════════════════════════════════════\n"
            f"[QUOTABLE TEXT — cite «{filename}» verbatim and include its DOCUMENT LINK as [📄 View]({link})]\n"
            f"\"\"\"\n"
            f"{chunk_text}\n"
            f"\"\"\"\n"
            f"════════════════════════════════════════"
        )

    sources_section = "\n\n".join(context_blocks)

    # ── Step 3: Assemble Full Context ─────────────────────────
    full_context = (
        f"╔══════════════════════════════════════════╗\n"
        f"║   VERIFIED CITATION REGISTRY             ║\n"
        f"╚══════════════════════════════════════════╝\n"
        f"{registry}\n\n"
        f"╔══════════════════════════════════════════╗\n"
        f"║   RETRIEVED SOURCE DOCUMENTS             ║\n"
        f"╚══════════════════════════════════════════╝\n"
        f"{sources_section}"
    )

    if len(full_context) > max_context:
        full_context = full_context[:max_context] + "\n\n[Context truncated]"

    return full_context


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
    Extract every (Sn) marker actually present in the model's answer and map
    each to the corresponding chunk metadata via a direct index lookup.

    The CITATION BINDING RULE instructs the model to write parenthesised
    markers — (S1), (S2), etc. — NOT square-bracket [S1] form.  This regex
    deliberately matches only the parenthesised form so that the SOURCE [S1]
    context-block headers are never confused with real inline citations.

    Returns a dict with:
      "citations": list of resolved entries (in order of first appearance)
      "unresolved": list of marker strings the model used but that have no
                    corresponding chunk (should be flagged, not silently guessed)
    """
    # Match (S1), (S2), … — the parenthesised form the model is told to write
    found_markers = list(dict.fromkeys(re.findall(r'\(S(\d+)\)', answer)))  # ordered, deduped
    index_by_n   = {str(i + 1): entry for i, entry in enumerate(marker_map)}

    citations  = []
    unresolved = []
    for n in found_markers:
        marker_str = f"(S{n})"
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


def _path_segments(source_path: str) -> set:
    """Returns the set of lowercased path components for exact folder matching."""
    return {p.lower() for p in Path(source_path.replace("\\", "/")).parts}


def _classify_source(source_path: str) -> str:
    """Classify by folder name (path segment), not filename substring."""
    parts = _path_segments(source_path)
    if parts & {"act", "cgst", "igst", "utgst", "sgst"}:
        return "PRIMARY LAW (Act)"
    if parts & {"notification", "notifications"}:
        return "NOTIFICATION (Statutory)"
    if parts & {"circular", "circulars"}:
        return "CIRCULAR (CBIC)"
    if parts & {"rules", "rule"}:
        return "RULES"
    if parts & {"aar"}:
        return "ADVANCE RULING"
    if parts & {"high court case laws", "supreme court case laws"}:
        return "COURT JUDGMENT"
    if parts & {"icai"}:
        return "ICAI GUIDANCE"
    if parts & {"form", "forms"}:
        return "FORM"
    return "REFERENCE DOCUMENT"


def _get_authority_rank(source_path: str) -> str:
    """Rank by folder name (path segment), not filename substring."""
    parts = _path_segments(source_path)
    if parts & {"act", "cgst", "igst", "utgst", "sgst"}:
        return "RANK-1 (Act)"
    if parts & {"rules", "rule"}:
        return "RANK-2 (Rules)"
    if parts & {"notification", "notifications"}:
        return "RANK-3 (Notification)"
    if parts & {"circular", "circulars"}:
        return "RANK-4 (Circular)"
    if parts & {"aar", "high court case laws", "supreme court case laws"}:
        return "RANK-5 (Case Law/AAR)"
    if parts & {"icai"}:
        return "RANK-5 (ICAI)"
    return "RANK-6 (Reference)"
