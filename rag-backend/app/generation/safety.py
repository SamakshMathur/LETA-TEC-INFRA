"""
Safety Guards — Post-generation safety layer that adjusts the answer
based on confidence signals and detects potentially dangerous outputs.
"""
import re
from typing import List, Dict, Any, Optional


def apply_safety_guards(
    answer: str,
    confidence: float,
    sources: str,
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Multi-level safety guards:
      1. Refuse if confidence is critically low (no reliable sources)
      2. Flag if answer contradicts a known blocked-credit / exception pattern
      3. Warn if medium confidence
      4. Pass through if high confidence
    """
    # --- Level 1: Critical low confidence — refuse ---
    if confidence < 0.4:
        return (
            "LETA could not determine a reliable answer based on the "
            "available documents. The retrieved sources did not contain "
            "sufficient information to address this query accurately.\n\n"
            "**Recommendation:** Please consult the relevant CGST/IGST Act "
            "provisions directly or seek professional legal advice."
        )

    # --- Level 2: Contradiction detection (common traps) ---
    contradiction_warning = _detect_contradictions(answer)
    if contradiction_warning:
        answer += contradiction_warning

    # --- Level 3: Medium confidence — append caveat ---
    if confidence < 0.65:
        answer += (
            "\n\n---\n"
            "**LETA Confidence Notice:** This answer is based on limited "
            "information from the available documents. Some aspects may be "
            "incomplete. Please verify critical conclusions from official "
            "CBIC / GST Portal sources before relying on this opinion."
        )
    elif confidence < 0.8:
        answer += (
            "\n\n---\n"
            "**Note:** While the core provisions have been identified, "
            "please verify specific numbers and dates from official sources."
        )

    return answer


def _detect_contradictions(answer: str) -> str:
    """
    Detects common logical contradictions in GST answers.
    Returns a warning string if contradictions found, empty string otherwise.
    """
    lower = answer.lower()
    warnings = []

    # Trap 1: Says ITC is available but also mentions Section 17(5)
    if "section 17(5)" in lower or "sec 17(5)" in lower:
        # Check if answer says ITC is available/allowed while citing 17(5)
        itc_allowed_phrases = [
            "itc is available", "itc is allowed", "credit is available",
            "credit is allowed", "can claim itc", "eligible for itc",
            "itc can be availed", "input tax credit is available",
        ]
        itc_blocked_phrases = [
            "blocked", "not available", "not allowed", "cannot claim",
            "ineligible", "restricted", "denied",
        ]
        has_allowed = any(p in lower for p in itc_allowed_phrases)
        has_blocked = any(p in lower for p in itc_blocked_phrases)

        # If it says both allowed AND blocked, that's fine (discussing exceptions)
        # But if it ONLY says allowed while citing 17(5), that's suspect
        if has_allowed and not has_blocked:
            warnings.append(
                "Section 17(5) is cited which BLOCKS ITC for specified categories. "
                "Verify whether an exception applies to your specific case."
            )

    # Trap 2: Says exempt but gives a non-zero rate
    if "exempt" in lower and re.search(r'(?:at|@)\s*\d+\s*%', lower):
        # Check if it's discussing an exempt AND a taxable scenario
        if "taxable" not in lower and "however" not in lower:
            warnings.append(
                "The answer mentions both 'exempt' and a percentage rate. "
                "Verify whether the supply is truly exempt or taxable."
            )

    if not warnings:
        return ""

    result = "\n\n" + "-" * 40 + "\n"
    result += "LETA SAFETY CHECK\n"
    result += "-" * 40 + "\n"
    for w in warnings:
        result += f"- {w}\n"
    result += "-" * 40 + "\n"
    return result
