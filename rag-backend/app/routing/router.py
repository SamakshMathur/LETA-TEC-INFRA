from app.routing.intent_classifier import classify_intent


def route_query(question: str) -> dict:
    intent_info = classify_intent(question)
    intent = intent_info["intent"]

    if intent == "definition":
        # Broad search, prefer text docs
        return {"use_sources": [".pdf", ".docx", ".txt"], "mode": "text"}
        
    if intent == "comparison":
        # Comparisons often need tables -> Excel, but also conceptual -> PDF
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "structured"}

    if intent == "rate_classification":
        # Rates -> Schedules (Excel) + Notifications (PDF)
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "hybrid"}

    if intent == "section_advisory":
        # Deep legal search -> EVERYTHING
        return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general"}

    # --- FALLBACK ---
    return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general"}
