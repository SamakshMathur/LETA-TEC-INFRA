"""
Answer Verifier — LLM second-pass that checks whether the generated
legal answer is internally consistent with the cited provisions.

This catches cases where the LLM correctly retrieves Section 17(5) but
then concludes "ITC is allowed" (contradicting the provision).
Uses CLAUDE_UTILITY_MODEL (Haiku) for speed and low cost.
"""
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _call_haiku(system: str, user: str) -> str:
    """Call Claude Haiku via the Anthropic client. Raises on failure."""
    from app.config import ANTHROPIC_API_KEY, CLAUDE_UTILITY_MODEL
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_UTILITY_MODEL,
        max_tokens=512,
        temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


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

    # Build a concise evidence summary from top chunks only (cost control)
    evidence_lines = []
    for i, c in enumerate(chunks[:6]):
        text = c.get("text", "").strip()[:600]
        rel_path = c.get("rel_path") or c.get("metadata", {}).get("rel_path", c.get("source", "unknown"))
        import os as _os
        doc_name = _os.path.basename(str(rel_path))
        evidence_lines.append(f"[Source {i+1}: {doc_name}]\n{text}")
    evidence = "\n\n".join(evidence_lines)

    system = """You are a Legal Quality Assurance Reviewer for Indian GST law.
Your task is to verify whether a legal answer is CONSISTENT with the source documents provided.

Check for these specific error types:
1. CONCLUSION CONTRADICTION: The answer cites a provision but reaches the OPPOSITE conclusion
   (e.g., cites Section 17(5) which BLOCKS ITC but concludes ITC is available).
2. WRONG NUMBERS: The answer states a rate, threshold, or time limit that contradicts the source text.
3. IRRELEVANT CITATION: The answer cites a document (e.g., a circular) whose retrieved text is
   clearly about a different topic than the claim it is cited for.

Respond with ONLY a JSON object:
{
  "verified": true/false,
  "issues": ["list of issues found, empty if verified"],
  "correction": "brief correction text if issues found, empty string if verified"
}"""

    user_prompt = f"""QUESTION: {question}

GENERATED ANSWER (first 2000 chars):
{answer[:2000]}

SOURCE DOCUMENTS RETRIEVED:
{evidence}

Verify the answer against the source documents. Focus on factual contradictions."""

    try:
        raw = _call_haiku(system, user_prompt)

        # Strip markdown code fences if present
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

        # Build a visible warning block
        warning = "\n\n" + "═" * 50 + "\n"
        warning += "⚠️  LETA ACCURACY REVIEW — POTENTIAL ISSUE DETECTED\n"
        warning += "═" * 50 + "\n"
        for issue in issues:
            warning += f"• {issue}\n"
        if correction:
            warning += f"\n📌 Suggested correction: {correction}\n"
        warning += "\nRecommendation: Cross-verify with the original statutory text at cbic.gov.in\n"
        warning += "═" * 50 + "\n"
        return warning

    except Exception as e:
        logger.warning(f"Answer verification failed (non-fatal): {e}")
        return None
