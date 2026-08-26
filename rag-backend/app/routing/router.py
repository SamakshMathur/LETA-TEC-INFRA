import re
from app.routing.intent_classifier import classify_intent

_HC_SC = ["High Court Case Laws", "Supreme Court Case Laws", "AAR"]

# ─── Domain path mappings ─────────────────────────────────────────────────────
_DOMAIN_PATHS: dict[str, list[str]] = {
    "itc":          ["Rules", "Act", "Circulars", "CGST", "IGST", "Notification"] + _HC_SC,
    "rule4x":       ["Rules", "Act", "Circulars"] + _HC_SC,
    "refund":       ["Act", "Rules", "Circulars", "Notification", "Forms"] + _HC_SC,
    "rate_hsn":     ["Act", "Notification", "IGST", "Forms"] + _HC_SC,
    "export":       ["Export", "Act", "Notification", "Circulars"] + _HC_SC,
    "eway":         ["Rules", "Circulars", "Notification"] + _HC_SC,
    "appeal":       ["Act", "Rules"] + _HC_SC,
    "annual":       ["Rules", "Forms", "Circulars"] + _HC_SC,
    "registration": ["Act", "Rules", "Circulars"] + _HC_SC,
    "audit":        ["Act", "Rules", "Circulars"] + _HC_SC,
    "penalty":      ["Act", "Rules", "Circulars", "Notification"] + _HC_SC,
    "scn":          ["Act", "Rules", "Circulars", "Notification"] + _HC_SC,
    "draft":        ["Act", "Rules", "Circulars", "Notification"] + _HC_SC,
    # Intermediary services: definition in IGST Act s.2(13), PoS in s.13(8)(b)
    "intermediary": ["Act", "IGST", "Circulars", "Notification"] + _HC_SC,
    # Place of supply — needs both Acts and circulars for PoS disputes
    "place_of_supply": ["Act", "IGST", "Circulars", "Notification"] + _HC_SC,
}


def _detect_domain_paths(question: str) -> list[str]:
    q = question.lower()
    domain_specific: set[str] = set()  # only domain matches — NOT the HC/SC fallback

    if re.search(r'rule\s*4[23]|common\s+input|revers.*itc|itc.*revers', q):
        domain_specific.update(_DOMAIN_PATHS["rule4x"])

    if re.search(r'\bitc\b|input\s+tax\s+credit|sec(?:tion)?\.?\s*1[67]', q):
        domain_specific.update(_DOMAIN_PATHS["itc"])

    if re.search(r'refund|igst\s+refund|export.*refund|unutilised\s+credit', q):
        domain_specific.update(_DOMAIN_PATHS["refund"])

    if re.search(r'hsn|sac|\bgst\s+rate\b|percent|gst\s+on\s+\w', q):
        domain_specific.update(_DOMAIN_PATHS["rate_hsn"])

    if re.search(r'export|zero.?rated|\blut\b|letter\s+of\s+undertaking|sez\b', q):
        domain_specific.update(_DOMAIN_PATHS["export"])

    if re.search(r'e.?way\s*bill|eway', q):
        domain_specific.update(_DOMAIN_PATHS["eway"])

    if re.search(r'appeal|tribunal|gstat|high\s+court|supreme\s+court', q):
        domain_specific.update(_DOMAIN_PATHS["appeal"])

    if re.search(r'annual\s+return|gstr.?9\b', q):
        domain_specific.update(_DOMAIN_PATHS["annual"])

    if re.search(r'registr(?:ation|ed|ing)', q):
        domain_specific.update(_DOMAIN_PATHS["registration"])

    if re.search(r'\baudit\b|gst\s+audit|gstr.?9c', q):
        domain_specific.update(_DOMAIN_PATHS["audit"])

    if re.search(r'penalty|penalt|section\s*12[2-9]|sec\s*12[2-9]', q):
        domain_specific.update(_DOMAIN_PATHS["penalty"])

    if re.search(r'scn|show\s*cause|notice|drc.?0?1|section\s*7[34]|sec\s*7[34]', q):
        domain_specific.update(_DOMAIN_PATHS["scn"])

    if re.search(r'draft|reply|response|representation|appeal\s+letter|submission', q):
        domain_specific.update(_DOMAIN_PATHS["draft"])

    if re.search(r'intermediary|commission\s+agent|broker\s+service|facilitator|agent\s+service', q):
        domain_specific.update(_DOMAIN_PATHS["intermediary"])

    if re.search(r'place\s+of\s+supply|pos\b|section\s*1[23]\s*igst|cross.?border\s+service', q):
        domain_specific.update(_DOMAIN_PATHS["place_of_supply"])

    # Include HC/SC ONLY when at least one domain-specific path was found.
    # If nothing matched, return an EMPTY list so search() applies NO folder
    # filter and searches all sources. Previously we returned just HC/SC/AAR as
    # a fallback, which accidentally excluded Acts and Circulars for every query
    # that didn't match a domain pattern (e.g., definition queries).
    if domain_specific:
        domain_specific.update(_HC_SC)
        return list(domain_specific)

    return []  # empty = no restriction, search all sources


def route_query(question: str) -> dict:
    """
    Intent classification via classify_intent() (LLM-first, keyword fallback).
    Also runs domain-path detection for folder-level source filtering.
    Returns use_sources (file extensions), mode, and domain_paths.
    """
    intent_info = classify_intent(question.lower().strip())
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
