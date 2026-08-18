from app.routing.intent_classifier import classify_intent


def route_query(question: str) -> dict:
    intent_info = classify_intent(question)
    intent = intent_info["intent"]

    # Source filtering based on file extensions in the source path
    # We use file extensions usually: .pdf, .docx, .xlsx

    if intent == "form_lookup":
        # Forms might be in PDF or DOCX
        return {"use_sources": [".docx", ".pdf"], "mode": "text"}

    if intent == "rate_comparison":
        # Comparisons often need tables -> Excel
        return {"use_sources": [".xlsx", ".xls"], "mode": "structured"}

    if intent == "rate_lookup":
        # Rates can be in notifications (PDF) or schedules (Excel)
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "hybrid"}

    if intent == "aar_lookup":
        # Rulings are PDFs
        return {"use_sources": [".pdf"], "mode": "text"}

    if intent == "jobwork_rate":
        return {"use_sources": [".pdf"], "mode": "text"}

    if intent == "act_section_lookup":
        # Acts can be PDFs or Excels
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "structured"}

    if intent == "procedure":
        return {"use_sources": [".docx", ".pdf"], "mode": "text"}

    # --- FALLBACK ---
    # Search everything
    return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general"}
