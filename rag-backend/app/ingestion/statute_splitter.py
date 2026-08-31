"""
statute_splitter.py — Phase 4: Secondary chunk-splitting for oversized Statute/Rule chunks.

The LegalParser.structural_split() method produces provision-level chunks for
Statute and Rule documents (one chunk per section/rule). It applies NO secondary
size constraint, allowing pathologically large sections (e.g. ~76k chars) to
become single embedding chunks.

This module implements a deterministic secondary splitter that:

  1. Preserves 100% of the original section/rule text.
  2. Never truncates content.
  3. Produces deterministic, ordered output.
  4. Preserves the parent legal identity (provision marker, metadata).
  5. Gives every child chunk a unique, deterministic chunk_id derived from its text.
  6. Prefers natural legal text boundaries in priority order:
       paragraph → numbered clause/sub-paragraph → bullet/list → sentence → whitespace

Size policy (reusing the existing Case Law sub-chunker convention):
  - TARGET_CHARS = 1500   (matches the 1500-char target in structural_split's case-law path)
  - MAX_CHARS    = 6000   (hard ceiling; no chunk may exceed this regardless of boundary)
  - Trigger      = 2000   (same as the case-law recursive trigger; smaller sections pass through)

These constants match the existing project conventions found in:
  - legal_parser.py L377:  ``if len(current_chunk) + len(p) < 1500``
  - legal_parser.py L372:  ``if len(seg["text"]) > 2000``
  - ingest_all_to_s3.py:   ``WINDOW, STEP = 1500, 1300``
"""

import re
import hashlib
from typing import List, Dict, Any

# ─── Size policy ─────────────────────────────────────────────────────────────

# Chunks at or below this threshold are returned unchanged.
SECONDARY_SPLIT_TRIGGER = 2000

# Target size for each child chunk (soft: splitter may slightly exceed to avoid
# cutting in the middle of a natural boundary unit).
SECONDARY_SPLIT_TARGET = 1500

# Absolute maximum: no child chunk may exceed this. The splitter will force-split
# at a whitespace boundary if no earlier legal boundary exists.
SECONDARY_SPLIT_MAX = 6000


# ─── Boundary patterns (in descending priority) ──────────────────────────────

# Pattern 1: double-newline (paragraph boundary)
_PARA_BOUNDARY = re.compile(r'\n\n+')

# Pattern 2: numbered sub-paragraph / clause (e.g. "(1)", "(a)", "1.", "a.")
_NUMBERED_CLAUSE = re.compile(
    r'(?<!\w)'                       # not preceded by word char (avoids mid-word match)
    r'(?:'
    r'\(\d+[a-zA-Z]?\)'              # (1), (1a)
    r'|\([a-z]{1,3}\)'               # (a), (aa)
    r'|\b\d{1,3}\.'                  # 1.  2.  10.
    r'|\b[a-z]\.'                    # a.  b.
    r')'
)

# Pattern 3: bullet / list marker
_BULLET_BOUNDARY = re.compile(r'(?:^|\n)\s*(?:[-•*◦▪–])\s+', re.MULTILINE)

# Pattern 4: sentence boundary — period/exclamation/question followed by space + uppercase
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def _best_split_point(text: str, target: int, maximum: int) -> int:
    """
    Find the best character position at which to split *text* such that the left
    part is <= maximum chars and as close to *target* chars as possible.

    Tries boundary types in descending priority order. Returns the index of the
    split point (the left slice is text[:idx], right is text[idx:]).

    Falls back to whitespace, then hard-cuts at *maximum* as last resort.
    """
    search_end = min(maximum, len(text))
    # Search in [target//2 .. maximum] so we don't produce tiny leading chunks
    search_start = max(target // 2, 1)

    def _last_match_before(pattern: re.Pattern, limit: int) -> int:
        """Return start of last match of pattern at or before limit, or -1."""
        best = -1
        for m in pattern.finditer(text[:limit]):
            if m.start() >= search_start:
                best = m.start()
        return best

    # 1. Paragraph boundary
    pos = _last_match_before(_PARA_BOUNDARY, search_end)
    if pos != -1:
        return pos

    # 2. Numbered clause / sub-paragraph
    pos = _last_match_before(_NUMBERED_CLAUSE, search_end)
    if pos != -1:
        return pos

    # 3. Bullet / list marker
    pos = _last_match_before(_BULLET_BOUNDARY, search_end)
    if pos != -1:
        return pos

    # 4. Sentence boundary
    pos = _last_match_before(_SENTENCE_BOUNDARY, search_end)
    if pos != -1:
        return pos

    # 5. Last whitespace before limit
    chunk = text[:search_end]
    ws_pos = chunk.rfind(' ')
    if ws_pos != -1 and ws_pos >= search_start:
        return ws_pos

    # 6. Hard cut at maximum (last resort — avoids infinite loop / excessive recursion)
    return search_end


def _deterministic_child_id(parent_chunk: Dict[str, Any], child_text: str, child_index: int) -> str:
    """
    Generate a unique, deterministic chunk_id for a secondary child chunk.

    Strategy (mirrors LegalParser.generate_chunk_id):
      {DOC_TYPE_SHORT}_{FILE_SHORT}_{STRUCTURE}_{CONTENT_HASH6}

    For secondary children we append _Pn (where n is the 0-based child index) to
    the content hash to guarantee uniqueness even if two chunks have the same
    (unlikely) MD5 prefix collision.
    """
    metadata = parent_chunk.get("metadata", {})
    rel_path = metadata.get("rel_path") or parent_chunk.get("rel_path", "unknown")

    name_match = re.search(r'([^\\/]+)\.(?:pdf|docx|xlsx)', rel_path, re.IGNORECASE)
    name = name_match.group(1).upper()[:20] if name_match else "DOC"

    doc_type = metadata.get("document_type") or parent_chunk.get("document_type", "DOC")
    doc_type_short = str(doc_type)[:3].upper()

    structure = parent_chunk.get("structure", "PROVISION")
    content_hash = hashlib.md5(child_text.encode()).hexdigest()[:6].upper()

    return f"{doc_type_short}_{name}_{structure}_{content_hash}_P{child_index}".upper()


def split_oversized_provision(
    chunk: Dict[str, Any],
    target: int = SECONDARY_SPLIT_TARGET,
    maximum: int = SECONDARY_SPLIT_MAX,
    trigger: int = SECONDARY_SPLIT_TRIGGER,
) -> List[Dict[str, Any]]:
    """
    Secondary splitter for a single Statute/Rule provision chunk.

    If ``len(chunk["text"]) <= trigger``, returns ``[chunk]`` unchanged.

    Otherwise splits the text into children <= *maximum* chars each,
    preferring natural legal text boundaries. Every child inherits all parent
    metadata and is augmented with:

      - ``chunk_id``         : unique deterministic ID (see _deterministic_child_id)
      - ``_secondary_split`` : True  (marker for auditing; not used by retrieval logic)
      - ``_parent_chunk_id`` : the parent chunk's original chunk_id for traceability
      - ``_child_index``     : 0-based index of this child within the parent
      - ``_child_count``     : total number of children produced

    The child's ``provision`` and ``metadata.provision`` fields retain the parent
    provision marker (e.g. "Section 16") so every child remains attributable to
    the same legal provision.
    """
    text = chunk.get("text", "")
    if len(text) <= trigger:
        return [chunk]

    # Build ordered list of text segments by repeatedly splitting at the best
    # legal boundary until the remaining text fits within *target* chars.
    # *maximum* is used only as the upper-bound for _best_split_point's search
    # window — it is the absolute ceiling per child, not the loop-exit threshold.
    segments: List[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= target:
            # Remaining text fits in one chunk — collect and stop
            segments.append(remaining)
            break
        split_at = _best_split_point(remaining, target, maximum)
        left = remaining[:split_at]
        remaining = remaining[split_at:]
        if left:
            segments.append(left)
        if not remaining:
            break

    if not segments:
        return [chunk]

    # If only one segment was produced (shouldn't happen, but guard), return original
    if len(segments) == 1:
        return [chunk]

    parent_chunk_id = chunk.get("chunk_id", "")
    children: List[Dict[str, Any]] = []
    total = len(segments)

    for i, seg_text in enumerate(segments):
        child = {
            **chunk,                                # inherit all parent fields
            "text": seg_text,
            "_secondary_split": True,
            "_parent_chunk_id": parent_chunk_id,
            "_child_index": i,
            "_child_count": total,
        }
        # Override chunk_id with deterministic child ID
        child["chunk_id"] = _deterministic_child_id(chunk, seg_text, i)

        # Also update it inside metadata if metadata dict is present
        if isinstance(child.get("metadata"), dict):
            # Make a shallow copy of metadata to avoid mutating the parent chunk's dict
            child["metadata"] = {
                **child["metadata"],
                "chunk_id": child["chunk_id"],
                "_secondary_split": True,
                "_parent_chunk_id": parent_chunk_id,
                "_child_index": i,
                "_child_count": total,
            }

        children.append(child)

    return children


def apply_secondary_split_to_statute_chunks(
    chunks: List[Dict[str, Any]],
    target: int = SECONDARY_SPLIT_TARGET,
    maximum: int = SECONDARY_SPLIT_MAX,
    trigger: int = SECONDARY_SPLIT_TRIGGER,
) -> List[Dict[str, Any]]:
    """
    Apply secondary splitting to a list of Statute/Rule provision chunks.

    Small chunks (text <= trigger) pass through unchanged.
    Oversized chunks are replaced by their ordered list of children.

    Order is strictly preserved.
    """
    result: List[Dict[str, Any]] = []
    for chunk in chunks:
        children = split_oversized_provision(chunk, target=target, maximum=maximum, trigger=trigger)
        result.extend(children)
    return result
