from app.routing.intent_classifier import _keyword_classify


def route_query(question: str) -> dict:
    """Fast keyword-only routing — no LLM call needed."""
    intent_info = _keyword_classify(question.lower().strip())
    intent = intent_info["intent"]

    if intent == "definition":
        return {"use_sources": [".pdf", ".docx", ".txt"], "mode": "text"}

    if intent == "comparison":
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "structured"}

    if intent == "rate_classification":
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "hybrid"}

    if intent == "section_advisory":
        return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general"}

    return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general"}
