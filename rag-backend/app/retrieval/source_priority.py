import re
from pathlib import Path


# Map of folder/keyword → authority weight (1–5)
# Ordered from highest to lowest authority.
# Uses exact path-segment matching to prevent false positives like:
#   "practice.pdf" triggering "act" rule, or "abstract.pdf" matching "act".
_AUTHORITY_MAP = [
    # Weight 5 — Primary Statute + Supreme Court (both are highest authority)
    (5, ["act", "cgst", "igst", "utgst", "sgst", "supreme court case laws"]),

    # Weight 4 — Rules + High Court + CBIC Circulars
    # CBIC Circulars are binding interpretive instruments under CGST Act s.168.
    # They have mandatory force on field officers and practitioners — not merely
    # persuasive like AARs. Weight 4 puts them on par with Rules and High Court.
    (4, ["rules", "rule", "high court case laws", "tribunal", "judgement", "judgment",
         "circulars", "circular"]),

    # Weight 3 — Notifications / AARs / Instructions / Trade Notices
    (3, ["notification", "notifications", "aar", "advance ruling", "other app result", "export",
         "instruction", "trade notice"]),

    # Weight 2 — ICAI, press releases, misc guidance
    (2, ["press release", "icai"]),

    # Weight 1 — Forms, Brochures, FAQs, Misc
    (1, ["forms", "form", "brochures", "brochure", "faqs", "faq", "flyer",
         "excel", ".xlsx", "responses", "response",
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
