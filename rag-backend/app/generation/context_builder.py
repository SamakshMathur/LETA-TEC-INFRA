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

import os
import re
import urllib.parse
from collections import defaultdict
from typing import List, Dict, Any, Set, Tuple

from app.retrieval.evidence_resolver import build_resolution_summary


# Context & Evidence Token Budget Allocation
# Claude Context Window: 200,000 tokens
# System & Instructions Budget: ~3,500 tokens
# Generation Output Budget: 3,000 – 8,000 tokens
# Allocated RAG Authoritative Evidence Budget:
# - Standard Q&A: 7,500 tokens (~30,000 characters of primary statutory/judicial text)
# - Advisory & Drafting: 12,000 tokens (~48,000 characters)
MAX_EVIDENCE_TOKENS = 7500
MAX_EVIDENCE_TOKENS_DRAFT = 12000
MAX_GENERATION_CHUNKS_CEILING = 45  # Safety ceiling against fragmented micro-chunks


def _estimate_tokens(text: str) -> int:
    """Estimate token count from legal text (~4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text.strip()) // 4)


def _get_authority_tier(chunk: Dict[str, Any]) -> str:
    """Classify chunk into legal authority tier."""
    role = str(chunk.get("_evidence_role", "")).lower()
    if role in ("primary_legislation",):
        return "STATUTE"
    if role in ("delegated_legislation",):
        return "RULE"
    if role in ("delegated_authority",):
        return "NOTIFICATION"
    if role in ("departmental_guidance",):
        return "CIRCULAR"
    if role in ("binding_precedent", "persuasive_precedent"):
        return "CASE_LAW"
    if role in ("persuasive_authority",):
        return "AAR"

    # Fallback by inspecting path and metadata
    rel = _rel(chunk).replace("\\", "/").lower()
    if "cgst acts" in rel or "igst acts" in rel or "/act/" in rel or rel.startswith("act/") or bool(chunk.get("_is_statute_first")):
        return "STATUTE"
    if "rule" in rel or "rules" in rel:
        return "RULE"
    if "notification" in rel or "notif" in rel:
        return "NOTIFICATION"
    if "circular" in rel or "cir" in rel:
        return "CIRCULAR"
    if "case" in rel or "supreme court" in rel or "high court" in rel or "judgment" in rel:
        return "CASE_LAW"
    if "aar" in rel or "advance ruling" in rel:
        return "AAR"
    return "OTHER"


# ── Public API ────────────────────────────────────────────────────────────────

def select_generation_chunks(chunks: List[Dict[str, Any]], query: str, is_draft: bool = False) -> List[Dict[str, Any]]:
    """
    Evidence-aware utility and token-budgeted generation selection policy:
    1. EXPLICIT EVIDENCE: Chunks belonging to explicitly requested authorities
       (matching canonical keys, provision keys, or document identity)
       plus all retrieved substantive sibling chunks from the same document.
    2. MULTI-TIER RELEVANCE: For topical queries, preserves balanced representation
       across all retrieved authority tiers (Acts, Rules, Notifications, Circulars, Case Law)
       proportional to their relevance and distinct document sources.
    3. DOCUMENT DEDUPLICATION: Caps repetitive chunks from the same document to preserve
       marginal utility across diverse legal authorities.
    4. TOKEN BUDGETING: Selection is constrained strictly by the allocated evidence token budget.
    """
    if not chunks:
        return []

    from app.retrieval.reference_resolver import ReferenceResolver
    explicit_refs = ReferenceResolver.resolve_references(query)

    max_tokens = MAX_EVIDENCE_TOKENS_DRAFT if is_draft else MAX_EVIDENCE_TOKENS

    def _get_cid(c: Dict[str, Any]) -> str:
        return str(c.get("chunk_id") or (c.get("metadata") or {}).get("chunk_id") or id(c))

    selected: List[Dict[str, Any]] = []
    seen_cids: Set[str] = set()
    total_tokens = 0
    doc_chunk_counts: Dict[str, int] = defaultdict(int)

    def _try_add(c: Dict[str, Any], max_per_doc: int = 4) -> bool:
        nonlocal total_tokens
        cid = _get_cid(c)
        if cid in seen_cids:
            return False
        doc = _rel(c).replace("\\", "/")
        if doc and doc_chunk_counts[doc] >= max_per_doc:
            return False
        text = (c.get("text") or c.get("embed_text") or c.get("content") or "").strip()
        tokens = _estimate_tokens(text)
        if len(selected) >= MAX_GENERATION_CHUNKS_CEILING:
            return False
        if selected and (total_tokens + tokens > max_tokens):
            return False
        seen_cids.add(cid)
        selected.append(c)
        total_tokens += tokens
        if doc:
            doc_chunk_counts[doc] += 1
        return True

    if not explicit_refs:
        # Broad topical query: group candidate chunks by authority tier
        tier_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for c in chunks:
            tier = _get_authority_tier(c)
            tier_map[tier].append(c)

        # Detect broad intent signals from query to prioritize the relevant tier
        q_lower = query.lower()
        is_case_intent = any(k in q_lower for k in ["case law", "case-law", "caselaw", "judgment", "judgement", "precedent", "court", "high court", "supreme court", "tribunal", "cestat"])
        is_circular_intent = any(k in q_lower for k in ["circular", "clarification", "guideline", "instruction"])

        if is_case_intent:
            tier_order = ["CASE_LAW", "STATUTE", "RULE", "CIRCULAR", "NOTIFICATION", "AAR", "OTHER"]
            max_docs_primary = 6
        elif is_circular_intent:
            tier_order = ["CIRCULAR", "STATUTE", "RULE", "NOTIFICATION", "CASE_LAW", "AAR", "OTHER"]
            max_docs_primary = 5
        else:
            tier_order = ["STATUTE", "RULE", "NOTIFICATION", "CIRCULAR", "CASE_LAW", "AAR", "OTHER"]
            max_docs_primary = 3

        # Pass 1: Multi-tier authority representation — preserve top distinct documents from each retrieved tier
        for tier in tier_order:
            seen_docs_in_tier: Set[str] = set()
            limit = max_docs_primary if tier == tier_order[0] else 3
            for c in tier_map.get(tier, []):
                doc = _rel(c).replace("\\", "/")
                if doc not in seen_docs_in_tier and len(seen_docs_in_tier) < limit:
                    if _try_add(c, max_per_doc=2):
                        seen_docs_in_tier.add(doc)

        # Pass 2: Marginal utility fill — add highest-ranked remaining chunks across all tiers until token budget
        for c in chunks:
            _try_add(c, max_per_doc=4)

        return selected

    # Explicit reference query path
    req_canonical_keys = {r.canonical_key for r in explicit_refs}
    req_base_keys = {r.base_key for r in explicit_refs}
    req_cir_nums = {r.provision_num for r in explicit_refs if r.ref_type == "CIRCULAR"}
    req_notif_nums = {r.provision_num for r in explicit_refs if r.ref_type == "NOTIFICATION"}
    req_case_kws = {r.provision_num.lower() for r in explicit_refs if r.ref_type == "CASE_LAW"}

    direct_evidence: List[Dict[str, Any]] = []
    matched_doc_paths: Set[str] = set()

    # Pass 1: Identify direct evidence chunks matching explicit references
    for c in chunks:
        meta = c.get("metadata") or {}
        rel = _rel(c).replace("\\", "/")
        rel_lower = rel.lower()

        is_pinned = bool(c.get("_pinned_by_ref"))
        anchor_prov = str(c.get("_anchor_provision") or c.get("_pinned_canonical_key") or "")

        chunk_provs = (
            list(meta.get("provision_keys") or [])
            + list(meta.get("provisions") or [])
            + ([c.get("provision")] if c.get("provision") else [])
            + ([anchor_prov] if anchor_prov else [])
        )
        chunk_prov_strs = [str(p).strip() for p in chunk_provs if p]

        is_direct = False

        # 1. Match provision keys
        if any(p in req_canonical_keys or p in req_base_keys for p in chunk_prov_strs):
            is_direct = True

        # 2. Match circular number in document path / title
        if req_cir_nums and any(f"circular_{num}" in rel_lower or f"cir_{num}" in rel_lower or f"circular-{num}" in rel_lower or f"circular no. {num}" in rel_lower or f"circular {num}" in rel_lower for num in req_cir_nums):
            is_direct = True

        # 3. Match notification number in document path / title
        if req_notif_nums and any(num.replace("/", "_").lower() in rel_lower or num.replace("/", "-").lower() in rel_lower for num in req_notif_nums):
            is_direct = True

        # 4. Match case law keyword in document path / title
        if req_case_kws and any(kw in rel_lower for kw in req_case_kws):
            is_direct = True

        # 5. Check if pinned for an explicit reference
        if is_pinned and (anchor_prov in req_canonical_keys or anchor_prov in req_base_keys or not anchor_prov):
            is_direct = True

        if is_direct:
            direct_evidence.append(c)
            if rel:
                matched_doc_paths.add(rel)

    # Pass 2: Sibling chunk recovery — bring retrieved chunks from the exact same document
    if matched_doc_paths:
        for c in chunks:
            rel = _rel(c).replace("\\", "/")
            if rel in matched_doc_paths and _get_cid(c) not in seen_cids:
                direct_evidence.append(c)

    # Sort direct evidence to prioritize content-rich operative text over short headers
    direct_evidence.sort(
        key=lambda c: (
            0 if len((c.get("text") or c.get("content") or "").strip()) >= 250 else 1,
            -len((c.get("text") or c.get("content") or "").strip())
        )
    )

    # Add direct evidence up to budget
    for c in direct_evidence:
        _try_add(c, max_per_doc=6)

    # Pass 3: Identify connected statutory evidence (statute text for provisions connected to the query)
    connected_evidence: List[Dict[str, Any]] = []
    for c in chunks:
        if _get_cid(c) in seen_cids:
            continue
        tier = _get_authority_tier(c)
        if tier in ("STATUTE", "RULE"):
            connected_evidence.append(c)

    for c in connected_evidence:
        _try_add(c, max_per_doc=3)

    # Pass 4: Fill remaining token budget (excluding unrequested circulars/cases when direct evidence exists)
    for c in chunks:
        tier = _get_authority_tier(c)
        if direct_evidence and tier in ("CIRCULAR", "CASE_LAW") and _get_cid(c) not in seen_cids:
            continue
        _try_add(c, max_per_doc=3)

    return selected


def build_canonical_authority_registry(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build the canonical registry of allowed authorities strictly present in the retrieved chunks.
    Used for evidence-bound generation and claim-level verification.
    """
    if not chunks:
        return []

    from app.retrieval.reference_resolver import ReferenceResolver

    registry: List[Dict[str, Any]] = []
    for i, c in enumerate(chunks):
        marker = f"[S{i + 1}]"
        rel = _rel(c).replace("\\", "/")
        doc_name = os.path.basename(rel) if rel else (c.get("source") or "unknown document")
        tier = _get_authority_tier(c)
        text = (c.get("text") or c.get("embed_text") or c.get("content") or "").strip()

        # Extract legal references specifically for this chunk
        refs = ReferenceResolver.extract_available_chunk_references([c])

        # Support span: first meaningful text excerpt, clean of markdown headers, max 200 chars
        clean_lines = [line.strip() for line in text.split("\n") if line.strip() and not line.strip().startswith("#")]
        first_line = clean_lines[0] if clean_lines else text[:180]
        support_span = (first_line[:197] + "...") if len(first_line) > 200 else first_line

        canonical_keys = list(dict.fromkeys(r.canonical_key for r in refs))
        display_names = list(dict.fromkeys(r.display_name for r in refs))
        statutes = list(dict.fromkeys(r.statute for r in refs if r.statute))

        registry.append({
            "marker": marker,
            "chunk_index": i + 1,
            "chunk_id": str(c.get("chunk_id") or (c.get("metadata") or {}).get("chunk_id", "") or id(c)),
            "doc_name": doc_name,
            "rel_path": rel,
            "authority_tier": tier,
            "statutes": statutes,
            "canonical_keys": canonical_keys,
            "display_names": display_names,
            "support_span": support_span,
            "references": refs,
        })
    return registry


def format_allowed_authorities_block(registry: List[Dict[str, Any]]) -> str:
    """Format canonical authority registry into an XML-tagged block for prompt injection."""
    if not registry:
        return ""

    lines = [
        "<allowed_authorities>",
        "THE FOLLOWING LEGAL AUTHORITIES ARE GROUNDED IN RETRIEVED EVIDENCE.",
        "YOU MAY ONLY CITE OR ASSERT SUBSTANTIVE CLAIMS ABOUT THESE AUTHORITIES OR THOSE EXPLICITLY REQUESTED BY THE USER:",
    ]
    for item in registry:
        marker = item["marker"]
        doc = item["doc_name"]
        tier = item["authority_tier"]
        disp = ", ".join(item["display_names"][:4]) if item["display_names"] else f"{tier} ({doc})"
        span = item["support_span"].replace("\n", " ").strip()
        lines.append(f"{marker} [{tier}] {disp} | Source: {doc}")
        if span:
            lines.append(f"     Substance: \"{span}\"")
    lines.append("</allowed_authorities>")
    return "\n".join(lines)


def build_context(chunks: List[Dict[str, Any]], is_draft: bool = False, include_registry: bool = True) -> str:
    """
    Build the LLM context block from retrieved chunks.

    Each source is labelled with [S1], [S2], ... so the model can cite inline.
    Prepend <allowed_authorities> and evidence resolution summary.
    """
    if not chunks:
        return ""
    parts = []
    if include_registry:
        registry = build_canonical_authority_registry(chunks)
        reg_block = format_allowed_authorities_block(registry)
        if reg_block:
            parts.append(reg_block)

    parts.append(build_resolution_summary(chunks))
    for i, c in enumerate(chunks):
        marker  = f"[S{i + 1}]"
        rel     = _rel(c)
        doc     = os.path.basename(rel) if rel else (c.get("source") or "unknown document")
        page    = c.get("page")
        page_str = f", page {page}" if page else ""
        text    = c.get("text") or c.get("embed_text") or ""
        authority = c.get("_evidence_authority", "Unclassified source")
        resolution_note = c.get("_evidence_resolution_note", "")
        parts.append(
            f"SOURCE {marker} — {doc}{page_str} | AUTHORITY: {authority}\n"
            f"{resolution_note}\n{text}"
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
