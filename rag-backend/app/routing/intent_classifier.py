"""
Intent classifier — routes queries to the right document-type filter.

Strategy: LLM-first (Claude Haiku, cached) with keyword fallback on any error.
The LLM classification is better for multi-signal queries (e.g., a rate question
that also mentions an AAR ruling) that stumble the keyword path.
"""
import re
import json
import logging
import functools

logger = logging.getLogger(__name__)

# ── Valid intents ─────────────────────────────────────────────────────────────
_VALID_INTENTS = {
    "form_lookup", "rate_comparison", "rate_lookup", "aar_lookup",
    "jobwork_rate", "act_section_lookup", "procedure", "general",
}

# ── Keyword fallback (always available, zero latency) ────────────────────────

def _keyword_classify(question: str) -> dict:
    q = question.lower()

    if "cheque bounce" in q or "cheque dishonour" in q:
        return {"intent": "aar_lookup", "confidence": 0.95}

    if "job work" in q and ("rate" in q or "%" in q):
        return {"intent": "jobwork_rate", "confidence": 0.9}

    if re.search(r"\b(form|apl-\d+|gst apl)\b", q):
        return {"intent": "form_lookup", "confidence": 0.95}

    if any(word in q for word in ["difference", "compare", "vs", "versus"]):
        if "%" in q or "percent" in q or re.search(r"\b\d{1,2}%\b", q):
            return {"intent": "rate_comparison", "confidence": 0.9}

    if any(word in q for word in ["rate", "gst rate", "%", "percent"]):
        return {"intent": "rate_lookup", "confidence": 0.85}

    if any(word in q for word in ["aar", "advance ruling"]):
        return {"intent": "aar_lookup", "confidence": 0.9}

    if re.search(r"\bsection\s+\d+", q):
        return {"intent": "act_section_lookup", "confidence": 0.9}

    if any(word in q for word in ["how to", "procedure", "process", "steps"]):
        return {"intent": "procedure", "confidence": 0.8}

    return {"intent": "general", "confidence": 0.5}


# ── LLM classification (Haiku — fast, ~100ms) ────────────────────────────────

_SYSTEM = """You classify Indian GST legal queries into one of these intent categories:
- form_lookup: user needs a specific GST form (GSTR, REG, DRC, APL forms)
- rate_comparison: comparing rates across goods/services
- rate_lookup: finding the GST rate for a specific good/service
- aar_lookup: advance rulings or case-based queries
- jobwork_rate: job work GST rate queries
- act_section_lookup: queries about a specific section/rule of CGST/IGST/GST Rules
- procedure: how-to compliance queries (registration, filing, refund steps)
- general: anything else (ITC eligibility, penalty, demand, circular interpretation, etc.)

Respond with ONLY a JSON object: {"intent": "<one of the above>", "confidence": <0.0-1.0>}"""


def _llm_classify(question: str) -> dict:
    """Call Haiku for intent classification. Raises on any failure."""
    from app.config import ANTHROPIC_API_KEY, CLAUDE_UTILITY_MODEL
    import anthropic
    from app.utils.anthropic_client import get_anthropic_client
    # Hard 5-second ceiling — intent classification must be instant.
    # Without this the default 600-second SDK timeout blocks the entire
    # pipeline on any transient Anthropic API slowness, making every query
    # appear stuck at RETRIEVE for up to 10 minutes before the fallback fires.
    client = get_anthropic_client(timeout=5.0, connect=2.0)
    msg = client.messages.create(
        model=CLAUDE_UTILITY_MODEL,
        max_tokens=64,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"Query: {question[:500]}"}],
    )
    if not msg.content:
        return "general"
    raw = msg.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    result = json.loads(raw)
    intent = result.get("intent", "general")
    if intent not in _VALID_INTENTS:
        intent = "general"
    return {"intent": intent, "confidence": float(result.get("confidence", 0.7))}


def classify_intent(question: str) -> dict:
    """
    LLM-first intent classification with keyword fallback.
    Falls back to keyword matching on any LLM error (network, auth, parse).
    """
    try:
        result = _llm_classify(question)
        logger.debug(f"[intent:llm] {result['intent']} ({result['confidence']:.2f})")
        return result
    except Exception as e:
        logger.debug(f"[intent:llm-err] {e!r} — falling back to keyword classifier")
        result = _keyword_classify(question)
        logger.debug(f"[intent:keyword] {result['intent']} ({result['confidence']:.2f})")
        return result
