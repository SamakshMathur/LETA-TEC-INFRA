import re


def classify_intent(question: str) -> dict:
    q = question.lower()

    # --- CHEQUE BOUNCE (AAR) ---
    if "cheque bounce" in q or "cheque dishonour" in q:
        return {"intent": "aar_lookup", "confidence": 0.95}

    # --- JOB WORK RATE ---
    if "job work" in q and ("rate" in q or "%" in q):
        return {"intent": "jobwork_rate", "confidence": 0.9}

    # --- FORM LOOKUP ---
    if re.search(r"\b(form|apl-\d+|gst apl)\b", q):
        return {"intent": "form_lookup", "confidence": 0.95}

    # --- RATE COMPARISON ---
    if any(word in q for word in ["difference", "compare", "vs", "versus"]):
        if "%" in q or "percent" in q or re.search(r"\b\d{1,2}%\b", q):
            return {"intent": "rate_comparison", "confidence": 0.9}

    # --- RATE LOOKUP ---
    if any(word in q for word in ["rate", "gst rate", "%", "percent"]):
        return {"intent": "rate_lookup", "confidence": 0.85}

    # --- AAR / ADVANCE RULING ---
    if any(word in q for word in ["aar", "advance ruling"]):
        return {"intent": "aar_lookup", "confidence": 0.9}

    # --- ACT / SECTION LOOKUP ---
    if re.search(r"\bsection\s+\d+", q):
        return {"intent": "act_section_lookup", "confidence": 0.9}

    # --- PROCEDURE ---
    if any(word in q for word in ["how to", "procedure", "process", "steps"]):
        return {"intent": "procedure", "confidence": 0.8}

    # --- FALLBACK ---
    return {"intent": "general", "confidence": 0.5}
