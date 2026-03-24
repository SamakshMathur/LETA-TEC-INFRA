import re
from pathlib import Path


# Map of folder/keyword → authority weight (1–5)
# Ordered from highest to lowest authority.
# Uses exact path-segment matching to prevent false positives like:
#   "practice.pdf" triggering "act" rule, or "abstract.pdf" matching "act".
_AUTHORITY_MAP = [
    # Weight 5 — Primary Statute (Act)
    # Folder names: Act, CGST, IGST
    (5, ["act", "cgst", "igst", "utgst", "sgst"]),

    # Weight 4 — Subordinate Legislation (Rules)
    # Folder names: Rules, rule
    (4, ["rules", "rule"]),

    # Weight 3 — Quasi-Judicial / Administrative (Notifications, Case Law, AAR)
    # Folder names: Notification, AAR, High Court Case Laws, Supreme Court Case Laws
    (3, ["notification", "notifications", "aar", "advance ruling",
         "high court case laws", "supreme court case laws",
         "tribunal", "judgement", "judgment", "export"]),

    # Weight 2 — Clarificatory (Circulars, Instructions, Trade Notices)
    # Folder names: Circulars
    (2, ["circulars", "circular", "instruction", "trade notice", "press release", "icai"]),

    # Weight 1 — Forms, Brochures, FAQs, Misc
    # Folder names: Forms, Brochures, FAQs, Other APP Result, Responses, generated_reports
    (1, ["forms", "form", "brochures", "brochure", "faqs", "faq", "flyer",
         "other app result", "excel", ".xlsx", "responses", "response",
         "generated_reports", "generated_report"]),
]


def _path_segments(source_path: str):
    """
    Returns a set of lowercase path segments from the source path.
    e.g. "RAG_INFORMATION_DATABASE/Act/cgst_act.pdf"
         → {"rag_information_database", "act", "cgst_act.pdf"}
    Only uses folder names and the filename stem — NOT substring of words —
    to prevent "practice.pdf" from matching "act".
    """
    p = Path(source_path.replace("\\", "/"))
    segments = set()
    for part in p.parts:
        # Normalise: lowercase, strip extension from filename
        clean = part.lower()
        segments.add(clean)                    # full part  e.g. "act"
        segments.add(Path(part).stem.lower())  # part without extension
    return segments


def source_priority(source_path: str) -> int:
    """
    Returns a legal authority weight from 1 to 5.
    Higher = higher authority in the Indian GST legal hierarchy.

    Uses path-segment matching (not substring search) so that filenames
    like 'practice.pdf', 'impact_study.pdf', 'abstract.pdf' never
    accidentally match 'act'.
    """
    if not source_path:
        return 1

    segments = _path_segments(source_path)

    for weight, keywords in _AUTHORITY_MAP:
        for kw in keywords:
            # kw must be an exact segment, not a substring of a word
            if kw in segments:
                return weight
            # Also handle multi-word keywords by checking if they appear as
            # a contiguous sequence in the full lowercased path string
            if " " in kw and kw in source_path.lower():
                return weight

    return 1
