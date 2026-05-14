import re
from app.routing.intent_classifier import _keyword_classify

# ─── Domain path mappings ─────────────────────────────────────────────────────
# Maps query signals to sub-folders inside RAG_INFORMATION_DATABASE.
# Keeps retrieval targeted; empty list = no path restriction (search all).
_DOMAIN_PATHS: dict[str, list[str]] = {
    "itc":          ["Rules", "Act", "Circulars", "CGST", "IGST", "Notification"],
    "rule4x":       ["Rules", "Act", "Circulars"],
    "refund":       ["Act", "Rules", "Circulars", "Notification", "Forms"],
    "rate_hsn":     ["Act", "Notification", "IGST", "Forms"],
    "export":       ["Export", "Act", "Notification", "Circulars"],
    "eway":         ["Rules", "Circulars", "Notification"],
    "appeal":       ["Act", "Rules", "High Court Case Laws"],
    "annual":       ["Rules", "Forms", "Circulars"],
    "registration": ["Act", "Rules", "Circulars"],
    "audit":        ["Act", "Rules", "Circulars"],
}


def _detect_domain_paths(question: str) -> list[str]:
    """
    Return the list of RAG_INFORMATION_DATABASE sub-folder names most
    relevant to this query. An empty list signals 'no restriction'.
    Runs in microseconds — pure regex, no LLM call.
    """
    q = question.lower()
    paths: set[str] = set()

    if re.search(r'rule\s*4[23]|common\s+input|revers.*itc|itc.*revers', q):
        paths.update(_DOMAIN_PATHS["rule4x"])

    if re.search(r'\bitc\b|input\s+tax\s+credit|sec(?:tion)?\.?\s*1[67]', q):
        paths.update(_DOMAIN_PATHS["itc"])

    if re.search(r'refund|igst\s+refund|export.*refund|unutilised\s+credit', q):
        paths.update(_DOMAIN_PATHS["refund"])

    if re.search(r'hsn|sac|\bgst\s+rate\b|percent|gst\s+on\s+\w', q):
        paths.update(_DOMAIN_PATHS["rate_hsn"])

    if re.search(r'export|zero.?rated|\blut\b|letter\s+of\s+undertaking|sez\b', q):
        paths.update(_DOMAIN_PATHS["export"])

    if re.search(r'e.?way\s*bill|eway', q):
        paths.update(_DOMAIN_PATHS["eway"])

    if re.search(r'appeal|tribunal|gstat|high\s+court|supreme\s+court', q):
        paths.update(_DOMAIN_PATHS["appeal"])

    if re.search(r'annual\s+return|gstr.?9\b', q):
        paths.update(_DOMAIN_PATHS["annual"])

    if re.search(r'registr(?:ation|ed|ing)', q):
        paths.update(_DOMAIN_PATHS["registration"])

    if re.search(r'\baudit\b|gst\s+audit|gstr.?9c', q):
        paths.update(_DOMAIN_PATHS["audit"])

    return list(paths)  # empty = no restriction


def route_query(question: str) -> dict:
    """
    Fast keyword-only routing — no LLM call needed.
    Returns use_sources (file extensions), mode, and domain_paths
    (RAG_INFORMATION_DATABASE sub-folder names to restrict retrieval).
    """
    intent_info = _keyword_classify(question.lower().strip())
    intent = intent_info["intent"]
    domain_paths = _detect_domain_paths(question)

    if intent == "definition":
        return {"use_sources": [".pdf", ".docx", ".txt"], "mode": "text", "domain_paths": domain_paths}

    if intent == "comparison":
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "structured", "domain_paths": domain_paths}

    if intent == "rate_classification":
        return {"use_sources": [".xlsx", ".xls", ".pdf"], "mode": "hybrid", "domain_paths": domain_paths}

    if intent == "section_advisory":
        return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general", "domain_paths": domain_paths}

    return {"use_sources": [".pdf", ".docx", ".xlsx", ".xls"], "mode": "general", "domain_paths": domain_paths}
