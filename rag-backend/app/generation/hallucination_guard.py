"""
Hallucination Guard — Post-generation filter that detects and flags
numeric claims (rates, thresholds, penalties, time limits) NOT grounded
in the retrieved context or Truth Rules.

This is a FAST regex-based check (no LLM call) that runs after streaming
completes.  It does NOT strip text — it appends a warning so the user
can see exactly which numbers need independent verification.

Upgrade (chunk-bound verification)
-----------------------------------
When called with `sn_text_map` (a dict mapping "S1", "S2", … to the
actual text of the chunk at that marker position), the guard checks each
number against the SPECIFIC chunk it was cited from, not just whether the
number appears anywhere in the full concatenated context blob.

Example of the failure this catches:
  Answer says: "The GST rate is 18% (S3)"
  S3's actual text: "applicable rate is 5%"
  Full context blob: contains "18%" from a different chunk about IGST.
  Old guard: "18% found in context blob" → PASSES (false negative)
  New guard: "18% not in S3's text"     → FLAGGED (correct)

If `sn_text_map` is None, falls back to the original full-blob check.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# ── Patterns that extract numeric claims from the LLM answer ──────────
_RATE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
_RUPEE_PATTERN = re.compile(
    r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:Lakh|Crore|per|/-)?', re.IGNORECASE
)
_DAYS_PATTERN = re.compile(r'(\d+)\s*(?:days?|months?|years?)', re.IGNORECASE)

# Numbers that are always safe (page numbers, list markers, etc.)
_SAFE_NUMBERS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}

# Regex that finds (Sn) inline citation markers in the answer
_MARKER_RE = re.compile(r'\(S(\d+)\)')

# Sentence boundary — split on end-of-sentence punctuation followed by
# whitespace + capital (conservative; avoids splitting abbreviations).
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z•\-])')


def _extract_numbers_from_text(text: str) -> Set[str]:
    """Extract all numeric strings (rates, rupees, time periods) from text."""
    numbers: Set[str] = set()
    for m in _RATE_PATTERN.finditer(text):
        numbers.add(m.group(1) + "%")
    for m in _RUPEE_PATTERN.finditer(text):
        numbers.add(m.group(1).replace(",", ""))
    for m in _DAYS_PATTERN.finditer(text):
        numbers.add(m.group(1))
    return numbers


def _num_in_text(num: str, text: str) -> bool:
    """Check whether a number string (with or without %) appears in text."""
    bare = num.replace("%", "").replace(",", "").strip()
    return num in text or bare in text


def check_hallucinated_numbers(
    answer: str,
    context: str,
    truth_rules_text: str,
    chunks: List[Dict[str, Any]],
    sn_text_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    Compares numeric claims in the answer against the source context.
    Returns a warning string to append (empty if everything checks out).

    Parameters
    ----------
    answer          : The full LLM-generated answer text.
    context         : The full RAG context string (for fallback blob check).
    truth_rules_text: Hardcoded truth rules (rates, thresholds, etc.).
    chunks          : Retrieved source chunks (each has a "text" field).
    sn_text_map     : Optional dict mapping "S1", "S2", … to the text of
                      that specific chunk.  When provided, numbers in sentences
                      with an explicit (Sn) citation are checked against that
                      chunk's text rather than the full blob.
    """
    if not answer or len(answer.strip()) < 100:
        return ""

    # ── Full-blob ground truth (always built; used as fallback) ──────────────
    ground_text = context + "\n" + truth_rules_text
    for c in chunks:
        ground_text += "\n" + (c.get("text") or "")
    grounded_blob = _extract_numbers_from_text(ground_text)

    answer_numbers = _extract_numbers_from_text(answer)
    if not answer_numbers:
        return ""

    # ── Per-citation check (only when sn_text_map is available) ──────────────
    if sn_text_map:
        # Split answer into sentences so we can correlate numbers with the
        # (Sn) markers in the same sentence.
        sentences = _SENT_SPLIT.split(answer)
        if len(sentences) <= 1:
            # Fallback split on newlines if sentence-boundary splitting fails
            sentences = [s for s in answer.split("\n") if s.strip()]

        # num → True if grounded, False if not yet determined
        grounded_map: Dict[str, bool] = {}

        for sent in sentences:
            # Find all (Sn) citation markers in this sentence
            cited_sn = _MARKER_RE.findall(sent)   # list of digit strings, e.g. ["1", "3"]
            sent_nums = _extract_numbers_from_text(sent)

            for num in sent_nums:
                bare = num.replace("%", "").replace(",", "").strip()
                if bare in _SAFE_NUMBERS:
                    grounded_map[num] = True
                    continue

                if num in grounded_map and grounded_map[num]:
                    continue  # already confirmed grounded — no need to re-check

                if cited_sn:
                    # Strict mode: check only against the cited chunk texts.
                    # If the number appears in ANY of the cited chunks it's grounded.
                    found_in_citation = any(
                        _num_in_text(num, sn_text_map.get(f"S{sn}", ""))
                        for sn in cited_sn
                    )
                    if found_in_citation:
                        grounded_map[num] = True
                    else:
                        # Not in the cited chunk.  Log at DEBUG — still flag it
                        # unless it was already grounded from another sentence.
                        logger.debug(
                            f"[hallu_guard] {num!r} not found in cited chunk(s) "
                            f"S{cited_sn} — may be misgrounded"
                        )
                        grounded_map.setdefault(num, False)
                else:
                    # No citation marker — fall back to full-blob check
                    if _num_in_text(num, ground_text) or num in grounded_blob:
                        grounded_map[num] = True
                    else:
                        grounded_map.setdefault(num, False)

        ungrounded = [n for n in answer_numbers if not grounded_map.get(n, False)]
        bare_safe  = {n.replace("%", "").replace(",", "").strip() for n in answer_numbers
                      if n.replace("%", "").replace(",", "").strip() in _SAFE_NUMBERS}
        ungrounded = [n for n in ungrounded
                      if n.replace("%", "").replace(",", "").strip() not in bare_safe]

    else:
        # ── Original full-blob check (no sn_text_map) ────────────────────────
        ungrounded = []
        for num in answer_numbers:
            bare = num.replace("%", "").replace(",", "").strip()
            if bare in _SAFE_NUMBERS:
                continue
            if not _num_in_text(num, ground_text) and num not in grounded_blob:
                ungrounded.append(num)

    if not ungrounded:
        return ""

    unique_ungrounded = sorted(set(ungrounded))
    warning  = "\n\n" + "─" * 44 + "\n"
    warning += "⚠ LETA TEC NUMBER VERIFICATION\n"
    warning += "─" * 44 + "\n"
    warning += (
        f"The following {len(unique_ungrounded)} numeric claim(s) could not be "
        "verified against the retrieved source documents they were cited from:\n"
    )
    for num in unique_ungrounded:
        warning += f"  · {num}\n"
    warning += (
        "Please verify these figures from official CBIC sources "
        "before relying on them.\n"
    )
    warning += "─" * 44 + "\n"
    return warning
