"""
Answer Verifier — LLM second-pass that checks whether the generated
legal answer is internally consistent with the cited provisions.

This catches cases where the LLM correctly retrieves Section 17(5) but
then concludes "ITC is allowed" (contradicting the provision).
Uses the cheap utility model for speed.
"""
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def verify_answer(
    question: str,
    answer: str,
    chunks: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Verifies the generated answer against the retrieved source chunks.

    Returns:
      - None if the answer passes verification (no issues found)
      - A correction/warning string to append if issues are detected
    """
    if not answer or not chunks or len(answer.strip()) < 100:
        return None

    # Build a concise evidence summary from top chunks
    evidence_lines = []
    for i, c in enumerate(chunks[:8]):
        text = c.get("text", "").strip()[:500]
        source = c.get("source", "unknown")
        evidence_lines.append(f"[Source {i+1}: {source}]\n{text}")
    evidence = "\n\n".join(evidence_lines)

    system = """You are a Legal Quality Assurance Reviewer for Indian GST law.
Your task is to verify whether a legal answer is CONSISTENT with the source documents provided.

Check for these specific error types:
1. CONCLUSION CONTRADICTION: The answer cites a provision but reaches the OPPOSITE conclusion
   (e.g., cites Section 17(5) which BLOCKS ITC but concludes ITC is available).
2. WRONG NUMBERS: The answer states a rate, threshold, or time limit that contradicts the source text.
3. MISSING CRITICAL CAVEAT: The answer omits a proviso, exception, or condition that changes the outcome.

Respond with ONLY a JSON object:
{
  "verified": true/false,
  "issues": ["list of issues found, empty if verified"],
  "correction": "brief correction text if issues found, empty string if verified"
}"""

    user_prompt = f"""QUESTION: {question}

GENERATED ANSWER (first 2000 chars):
{answer[:2000]}

SOURCE DOCUMENTS:
{evidence}

Verify the answer against the source documents."""

    try:
        from app.retrieval.query_refiner import _call_llm_json
        raw = _call_llm_json(system, user_prompt, temperature=0.0)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)

        if result.get("verified", True):
            return None

        issues = result.get("issues", [])
        correction = result.get("correction", "")

        if not issues and not correction:
            return None

        # Build a warning block to append
        warning = "\n\n" + "=" * 40 + "\n"
        warning += "LETA ACCURACY REVIEW\n"
        warning += "=" * 40 + "\n"
        warning += "STATUS: POTENTIAL INACCURACY DETECTED\n"
        for issue in issues:
            warning += f"- {issue}\n"
        if correction:
            warning += f"\nCORRECTION: {correction}\n"
        warning += "RECOMMENDATION: Cross-verify with the original statutory text.\n"
        warning += "=" * 40 + "\n"
        return warning

    except Exception as e:
        logger.warning(f"Answer verification failed (non-fatal): {e}")
        return None
