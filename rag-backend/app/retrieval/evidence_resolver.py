"""Deterministic legal evidence resolution after retrieval.

Retrieval answers "what is relevant?". This module answers the next question:
"what kind of authority is this, how directly does it govern the query, and
does the retrieved set contain a conflict that the generator must explain?"

This is deliberately metadata- and text-based. It does not decide the law or
silently discard lower-authority material; it ranks evidence, labels it, and
surfaces possible conflicts for the prompt and downstream verification.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List


_REF_PATTERNS = (
    r"\b(?:section|sec\.)\s*\d+[A-Za-z]?(?:\s*\(\s*[\da-zA-Z]+\s*\))*",
    r"\b(?:rule)\s*\d+[A-Za-z]?(?:\s*\(\s*[\da-zA-Z]+\s*\))*",
    r"\b(?:article)\s*\d+[A-Za-z]?(?:\s*\(\s*[\da-zA-Z]+\s*\))*",
    r"\b(?:circular|notification)\s+no\.?\s*[\w./-]+",
)
_REF_RE = re.compile("|".join(_REF_PATTERNS), re.IGNORECASE)
_CONFLICT_TERMS = re.compile(
    r"\b(?:overruled|reversed|distinguished|superseded|amended|contrary|"
    r"notwithstanding|however|in contrast|not available|ineligible|eligible|"
    r"allowed|disallowed|blocked|permitted)\b",
    re.IGNORECASE,
)


def _path(chunk: Dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    return str(
        chunk.get("rel_path")
        or metadata.get("rel_path")
        or chunk.get("source")
        or ""
    ).replace("\\", "/").lower()


def _text(chunk: Dict[str, Any]) -> str:
    return str(chunk.get("text") or chunk.get("embed_text") or "")


def _source_profile(path: str) -> tuple[str, str, int]:
    """Return (role, authority label, rank), where lower rank is stronger."""
    if "supreme court" in path:
        return "binding_precedent", "Supreme Court precedent", 1
    if "high court" in path:
        return "persuasive_precedent", "High Court precedent", 3
    if "cgst acts" in path or "igst acts" in path or "/act/" in path or path.startswith("act/"):
        return "primary_legislation", "Act", 2
    if "rules" in path:
        return "delegated_legislation", "Rule", 2
    if "notification" in path:
        return "delegated_authority", "Notification", 4
    if "circular" in path:
        return "departmental_guidance", "CBIC circular", 5
    if "aar" in path or "advance ruling" in path:
        return "persuasive_authority", "Advance ruling", 6
    if "icai" in path or "faq" in path or "brochure" in path:
        return "secondary_material", "Commentary", 7
    return "unclassified", "Unclassified source", 8


def _normalise_ref(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("sec.", "section")).strip()


def _query_refs(query: str) -> set[str]:
    return {_normalise_ref(match) for match in _REF_RE.findall(query or "")}


def _chunk_refs(chunk: Dict[str, Any]) -> set[str]:
    metadata = chunk.get("metadata") or {}
    values: Iterable[Any] = (
        list(metadata.get("citations") or [])
        + list(metadata.get("provisions") or [])
        + list(metadata.get("provision_keys") or [])
    )
    refs = {_normalise_ref(str(value)) for value in values if value}
    refs.update(_normalise_ref(match) for match in _REF_RE.findall(_text(chunk)))
    return refs


def resolve_evidence(chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Annotate and order retrieved chunks for legally explicit generation.

    Authority is a bounded tie-breaker, not a replacement for semantic
    relevance. Directly requested provisions receive the strongest additional
    signal. Possible conflicts are grouped by shared legal reference and
    surfaced in metadata so the answer can distinguish current law from a
    departmental or historical position.
    """
    if not chunks:
        return []

    requested_refs = _query_refs(query)
    prepared: List[Dict[str, Any]] = []
    by_ref: dict[str, list[Dict[str, Any]]] = defaultdict(list)

    for position, original in enumerate(chunks):
        chunk = original.copy()
        path = _path(chunk)
        role, authority, authority_rank = _source_profile(path)
        refs = _chunk_refs(chunk)
        exact_refs = sorted(requested_refs & refs)
        text = _text(chunk)
        conflict_terms = sorted({m.lower() for m in _CONFLICT_TERMS.findall(text)})

        # Keep the authority influence bounded so a highly relevant lower-tier
        # source is not blindly displaced by a vaguely related primary source.
        authority_bonus = max(0.0, (8 - authority_rank) * 0.025)
        exact_bonus = min(0.20, len(exact_refs) * 0.10)
        base_score = float(
            chunk.get("_final_legal_score", chunk.get("_rerank_score", chunk.get("_debug_score", 0.0)))
        )
        chunk["_evidence_role"] = role
        chunk["_evidence_authority"] = authority
        chunk["_evidence_authority_rank"] = authority_rank
        chunk["_evidence_exact_refs"] = exact_refs
        chunk["_evidence_conflict_terms"] = conflict_terms
        chunk["_evidence_resolution_score"] = round(
            base_score + authority_bonus + exact_bonus, 6
        )
        chunk["_evidence_original_rank"] = position + 1
        prepared.append(chunk)
        for ref in refs:
            by_ref[ref].append(chunk)

    conflict_refs = set()
    for ref, related in by_ref.items():
        roles = {item["_evidence_role"] for item in related}
        has_conflict_language = any(item["_evidence_conflict_terms"] for item in related)
        has_primary_and_guidance = (
            "primary_legislation" in roles
            and "departmental_guidance" in roles
        )
        if len(roles) > 1 and (has_conflict_language or has_primary_and_guidance):
            conflict_refs.add(ref)

    for chunk in prepared:
        refs = set(_chunk_refs(chunk))
        flagged = sorted(refs & conflict_refs)
        chunk["_evidence_conflict_refs"] = flagged
        chunk["_evidence_requires_resolution"] = bool(flagged)
        if flagged:
            chunk["_evidence_resolution_note"] = (
                "Potentially conflicting authorities share: " + ", ".join(flagged[:4])
            )
        else:
            chunk["_evidence_resolution_note"] = "No cross-authority conflict detected in retrieved evidence."

    prepared.sort(
        key=lambda item: (
            item["_evidence_resolution_score"],
            -item["_evidence_original_rank"],
        ),
        reverse=True,
    )
    return prepared


def build_resolution_summary(chunks: List[Dict[str, Any]]) -> str:
    """Create a compact instruction block for the answer generator."""
    if not chunks:
        return ""
    roles = []
    seen_roles = set()
    conflict_refs = []
    for chunk in chunks:
        role = chunk.get("_evidence_authority", "Unclassified source")
        if role not in seen_roles:
            roles.append(role)
            seen_roles.add(role)
        for ref in chunk.get("_evidence_conflict_refs", []):
            if ref not in conflict_refs:
                conflict_refs.append(ref)

    lines = [
        "LEGAL EVIDENCE RESOLUTION:",
        "Use evidence according to its labelled authority and explain disagreement instead of blending it.",
        "Binding precedent controls where applicable; Acts and Rules state the governing text; notifications and circulars show delegated or departmental position; AARs and commentary are persuasive only.",
        "Retrieved authority types: " + ", ".join(roles) + ".",
    ]
    if conflict_refs:
        lines.append(
            "Potential conflicts requiring explicit treatment: " + ", ".join(conflict_refs[:8]) + "."
        )
    return "\n".join(lines)