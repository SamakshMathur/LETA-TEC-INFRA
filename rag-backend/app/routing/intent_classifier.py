import re
import logging

logger = logging.getLogger(__name__)


def _keyword_classify(q: str) -> dict:
    """
    Fast keyword-based fallback classifier.
    Uses phrase-level matching with disambiguation to avoid false positives.
    """
    # 1. RATE / CLASSIFICATION — require rate-specific phrases, not bare "rate"
    rate_phrases = [
        "gst rate", "tax rate", "rate of gst", "rate of tax", "rate applicable",
        "hsn code", "hsn ", "sac code", "sac ", "applicable gst",
        "tax on ", "taxable at", "what percent", "how much gst", "how much tax",
    ]
    if any(phrase in q for phrase in rate_phrases):
        return {"intent": "rate_classification", "confidence": 0.85}
    # Bare "%" only if near gst/tax context
    if "%" in q and any(w in q for w in ["gst", "tax", "rate", "cess"]):
        return {"intent": "rate_classification", "confidence": 0.8}

    # 2. COMPARISON — require comparison-specific phrases
    comparison_phrases = [
        "difference between", "distinguish between", "compare ",
        " vs ", " versus ", "comparison of", "differentiate between",
    ]
    if any(phrase in q for phrase in comparison_phrases):
        return {"intent": "comparison", "confidence": 0.9}

    # 3. DEFINITION / CONCEPT
    definition_phrases = [
        "what is ", "what are ", "define ", "meaning of ",
        "explain ", "concept of ", "what does ",
    ]
    if any(phrase in q for phrase in definition_phrases):
        # Disambiguate: "what is the rate" -> rate_classification
        if any(w in q for w in ["rate", "hsn", "sac", "percent"]):
            return {"intent": "rate_classification", "confidence": 0.8}
        return {"intent": "definition", "confidence": 0.9}

    # 4. SECTION-BASED LEGAL ADVISORY — require legal-specific terms
    advisory_phrases = [
        "section ", "sec ", "penalty for", "late fee", "time limit",
        "eligibility for", "blocked credit", "blocked itc",
        "input tax credit", " itc ", "refund of", "refund claim",
        "rule ", "notification no", "circular no",
    ]
    if any(phrase in q for phrase in advisory_phrases):
        return {"intent": "section_advisory", "confidence": 0.85}

    # 5. Short question-word queries default to definition
    if len(q.split()) < 6 and any(q.startswith(w) for w in ["what", "who", "which", "how"]):
        return {"intent": "definition", "confidence": 0.6}

    # Fallback — general advisory
    return {"intent": "section_advisory", "confidence": 0.4}


def _llm_classify(question: str) -> dict:
    """
    Uses the cheap utility LLM model for accurate intent classification.
    Falls back to keyword classifier on failure.
    """
    try:
        from app.retrieval.query_refiner import _call_llm_json
        system = """You are a GST Query Intent Classifier.
Classify the user's query into exactly ONE intent.

Intents:
- "rate_classification": Questions about GST rates, HSN/SAC codes, percentages, cess.
- "comparison": Questions comparing two or more concepts, provisions, or tax treatments.
- "definition": Questions asking what something is, meaning, explanation of a concept.
- "section_advisory": Legal advisory questions about sections, rules, penalties, ITC, refunds, compliance.

Respond with ONLY a JSON object: {"intent": "INTENT_NAME", "confidence": 0.95}"""

        raw = _call_llm_json(system, question, temperature=0.0)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        import json
        result = json.loads(raw)
        intent = result.get("intent", "")
        valid_intents = {"rate_classification", "comparison", "definition", "section_advisory"}
        if intent in valid_intents:
            return {"intent": intent, "confidence": float(result.get("confidence", 0.9))}
    except Exception as e:
        logger.warning(f"LLM intent classification failed, using keyword fallback: {e}")

    return None


def classify_intent(question: str) -> dict:
    """
    Two-stage intent classifier:
      1. Try LLM-based classification (accurate, handles ambiguity)
      2. Fall back to keyword heuristics if LLM fails
    """
    q = question.lower().strip()

    # Stage 1: LLM classification
    llm_result = _llm_classify(question)
    if llm_result:
        return llm_result

    # Stage 2: Keyword fallback
    return _keyword_classify(q)
