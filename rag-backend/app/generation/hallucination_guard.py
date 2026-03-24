"""
Hallucination Guard — Post-generation filter that detects and flags
numeric claims (rates, thresholds, penalties, time limits) NOT grounded
in the retrieved context or Truth Rules.

This is a FAST regex-based check (no LLM call) that runs after streaming
completes.  It does NOT strip text — it appends warnings so the user
can see exactly which numbers need independent verification.
"""
import re
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

# ── Patterns that extract numeric claims from the LLM answer ──────────
_RATE_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*%',
    re.IGNORECASE,
)
_RUPEE_PATTERN = re.compile(
    r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:Lakh|Crore|per|/-)?',
    re.IGNORECASE,
)
_DAYS_PATTERN = re.compile(
    r'(\d+)\s*(?:days?|months?|years?)',
    re.IGNORECASE,
)

# Numbers that are always safe (page numbers, point labels, etc.)
_SAFE_NUMBERS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}


def _extract_numbers_from_text(text: str) -> Set[str]:
    """Extract all numeric strings (rates, rupees, time periods) from text."""
    numbers = set()
    for m in _RATE_PATTERN.finditer(text):
        numbers.add(m.group(1) + "%")
    for m in _RUPEE_PATTERN.finditer(text):
        raw = m.group(1).replace(",", "")
        numbers.add(raw)
    for m in _DAYS_PATTERN.finditer(text):
        numbers.add(m.group(1))
    return numbers


def check_hallucinated_numbers(
    answer: str,
    context: str,
    truth_rules_text: str,
    chunks: List[Dict[str, Any]],
) -> str:
    """
    Compares numeric claims in the answer against the source context
    and truth rules.  Returns a warning string to append (empty if clean).
    """
    if not answer or len(answer.strip()) < 100:
        return ""

    # Build the "ground truth" number pool from context + truth rules + chunks
    ground_text = context + "\n" + truth_rules_text
    for c in chunks:
        ground_text += "\n" + c.get("text", "")

    grounded_numbers = _extract_numbers_from_text(ground_text)
    answer_numbers = _extract_numbers_from_text(answer)

    # Filter out safe/trivial numbers
    ungrounded = []
    for num in answer_numbers:
        bare = num.replace("%", "").replace(",", "").strip()
        if bare in _SAFE_NUMBERS:
            continue
        if num not in grounded_numbers and bare not in grounded_numbers:
            # Check if the bare number appears anywhere in ground text
            if bare not in ground_text:
                ungrounded.append(num)

    if not ungrounded:
        return ""

    warning = "\n\n" + "-" * 40 + "\n"
    warning += "LETA NUMBER VERIFICATION\n"
    warning += "-" * 40 + "\n"
    warning += f"The following {len(ungrounded)} numeric claim(s) could not be "
    warning += "verified against the retrieved source documents:\n"
    for num in sorted(ungrounded):
        warning += f"  - {num}\n"
    warning += "These numbers may be correct but are NOT present in the "
    warning += "retrieved documents. Please verify from official CBIC sources.\n"
    warning += "-" * 40 + "\n"
    return warning
