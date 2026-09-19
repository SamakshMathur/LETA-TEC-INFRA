"""
Legal Provision & Structural Section Extractor
==============================================
Provides robust, data-driven statutory section detection for GST and general legal corpora.
Accurately distinguishes:
1. Primary provision headings (e.g. "Section 16", "Section - 16", "16. (1) 'Zero rated supply'").
2. Genuine multiple provision boundaries within a single chunk.
3. Subsections and paragraph hierarchies (e.g. (1), (2), (a), (b)).
4. Cross-references (e.g. "subject to section 17 of the CGST Act", "in accordance with section 54").
5. Footnotes, enactment dates, and amendment notes (e.g. "31. Enforced w.e.f. 1-7-2017", "30a. Inserted by...").
6. Document-level circular and notification identifiers.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple


# ── Act Code Resolution ───────────────────────────────────────────────────────
_ACT_PATTERNS = [
    (re.compile(r'\b(?:integrated\s+goods\s+and\s+services\s+tax|igst)\b', re.IGNORECASE), "IGST"),
    (re.compile(r'\b(?:central\s+goods\s+and\s+services\s+tax|cgst)\b', re.IGNORECASE), "CGST"),
    (re.compile(r'\b(?:union\s+territory\s+goods\s+and\s+services\s+tax|utgst)\b', re.IGNORECASE), "UTGST"),
    (re.compile(r'\b(?:state\s+goods\s+and\s+services\s+tax|sgst)\b', re.IGNORECASE), "SGST"),
    (re.compile(r'\bcustoms\b', re.IGNORECASE), "CUSTOMS"),
]

def resolve_default_act(rel_path: str = "", text: str = "") -> str:
    """Determine default governing act from document path and header context."""
    path_lower = rel_path.lower().replace("\\", "/")
    if "igst" in path_lower or "/igst" in path_lower:
        return "IGST"
    if "utgst" in path_lower:
        return "UTGST"
    if "customs" in path_lower:
        return "CUSTOMS"
    
    # Fallback to text header scan if path is neutral
    if text:
        first_500 = text[:500]
        for pat, act in _ACT_PATTERNS:
            if pat.search(first_500):
                return act

    return "CGST"


# ── Primary Section / Provision Patterns ─────────────────────────────────────
# Matches:
# - "Section 16", "Section - 16", "Section: 16", "Sec. 16", "Sec 16"
# - "Section 16(1)", "Section 16(1)(a)", "Section 16A"
_PRIMARY_SEC_HEADER_RE = re.compile(
    r'(?:^|\n|\.\s+)\s*(?:Section|Sec\.)\s*[-:\s]+\s*(\d+[A-Z]?)(?:\s*\(([^)\n]+)\))?(?:\s*,\s*([A-Za-z\s]+Act[^\n,]*))?',
    re.IGNORECASE | re.MULTILINE
)

# Matches standalone statutory section starts:
# e.g. "16. (1) \"Zero rated supply\" means..." or "\n16. Zero rated supply.— (1)"
_STANDALONE_SEC_START_RE = re.compile(
    r'(?:^|\n)\s*(\d+[A-Z]?)\.\s*(?:\(\s*(\d+[a-z]?)\s*\)|\"?[A-Z][a-z]+|\—)',
    re.MULTILINE
)

# Matches Rule headers: "Rule 89", "Rule - 89", "89. Application for refund..."
_PRIMARY_RULE_HEADER_RE = re.compile(
    r'(?:^|\n|\.\s+)\s*Rule\s*[-:\s]+\s*(\d+[A-Z]?)(?:\s*\(([^)\n]+)\))?',
    re.IGNORECASE | re.MULTILINE
)
_STANDALONE_RULE_START_RE = re.compile(
    r'(?:^|\n)\s*Rule\s+(\d+[A-Z]?)\b',
    re.IGNORECASE | re.MULTILINE
)

# Matches Schedule headers: "Schedule I", "Schedule II", "Schedule III"
_SCHEDULE_HEADER_RE = re.compile(
    r'\bSchedule\s+(I{1,3}|IV|V|VI|[1-6])\b',
    re.IGNORECASE
)

# Matches Circular / Notification numbers
_CIRCULAR_RE = re.compile(
    r'\b(?:Circular\s+No\.?|Cir\.?)\s*(\d+)(?:/(\d+))?(?:/(\d{4}))?',
    re.IGNORECASE
)
_NOTIF_RE = re.compile(
    r'\bNotification\s+No\.?\s*(\d+)\s*[/–-]\s*(\d{4})',
    re.IGNORECASE
)

# ── Footnote & Amendment Note Recognizers ─────────────────────────────────────
_FOOTNOTE_START_RE = re.compile(
    r'^\s*\d+[a-z]?\.\s+(?:Enforced\s+with\s+effect|Inserted\s+by|Substituted\s+by|Omitted\s+by|See\s+Circular|Prior\s+to\s+its\s+substitution|w\.e\.f\.)',
    re.IGNORECASE | re.MULTILINE
)

# ── Cross-Reference Signals ───────────────────────────────────────────────────
_CROSS_REF_CONTEXT_RE = re.compile(
    r'(?:subject\s+to|under|in\s+accordance\s+with|referred\s+to\s+in|read\s+with|as\s+provided\s+in|within\s+the\s+meaning\s+of|pursuant\s+to|provisions\s+of|terms\s+of)\s+'
    r'(?:sub-section\s*\(\d+\)\s*of\s+)?(?:section|rule)\s*(\d+[A-Z]?)'
    r'(?:\s*of\s+the\s+([A-Za-z\s]+Act))?',
    re.IGNORECASE
)


@dataclass
class StructuralProvisionResult:
    """Result of structural provision extraction for a chunk."""
    primary_provision_keys: List[str] = field(default_factory=list)
    secondary_citation_keys: List[str] = field(default_factory=list)
    primary_section_labels: List[str] = field(default_factory=list)
    primary_section_label: Optional[str] = None
    all_provision_keys: List[str] = field(default_factory=list)
    subsections: List[str] = field(default_factory=list)


class StructuralProvisionExtractor:
    """
    Data-driven structural legal provision extractor.
    Extracts primary provisions with structural hierarchy while isolating cross-references and footnotes.
    """

    @classmethod
    def extract(cls, text: str, rel_path: str = "", category: str = "") -> StructuralProvisionResult:
        """
        Extract structural provisions from chunk text and path context.
        """
        result = StructuralProvisionResult()
        if not text or not text.strip():
            return result

        default_act = resolve_default_act(rel_path, text)
        is_statute_doc = any(k in rel_path.lower() for k in ["act", "acts", "rules", "rule", "cgst", "igst", "utgst"])
        
        primary_keys: Set[str] = set()
        secondary_keys: Set[str] = set()
        section_labels: List[str] = []
        subsections_found: Set[str] = set()

        # ── Step 1: Detect Primary Section Headers ───────────────────────────
        for m in _PRIMARY_SEC_HEADER_RE.finditer(text):
            sec_num = m.group(1).upper()
            sub_raw = m.group(2)
            act_override = m.group(3)

            act_code = default_act
            if act_override:
                for pat, act in _ACT_PATTERNS:
                    if pat.search(act_override):
                        act_code = act
                        break

            # Check if this occurrence is purely a cross-reference
            # Look at 40 chars preceding the match
            pre_start = max(0, m.start() - 40)
            pre_context = text[pre_start:m.start()].lower()
            if any(cue in pre_context for cue in ["subject to", "referred to in", "under", "in accordance with", "read with"]):
                # This is a cross-reference, not a primary header
                secondary_keys.add(f"{act_code}_SEC_{sec_num}")
                continue

            pkey = f"{act_code}_SEC_{sec_num}"
            primary_keys.add(pkey)
            label = f"Section {sec_num}"
            if sub_raw:
                label += f"({sub_raw})"
            if label not in section_labels:
                section_labels.append(label)

        # ── Step 2: Detect Standalone Statutory Section Starts ────────────────
        # e.g. "16. (1) "Zero rated supply"..." in an Act document
        if is_statute_doc:
            for m in _STANDALONE_SEC_START_RE.finditer(text):
                sec_num = m.group(1).upper()
                sub_num = m.group(2)
                
                # Check preceding context: ensure not inside a footnote or sentence tail
                pre_start = max(0, m.start() - 30)
                pre_context = text[pre_start:m.start()].strip()
                if pre_context and not pre_context.endswith((".", "\n", ":", "—")):
                    continue
                if _FOOTNOTE_START_RE.search(text[max(0, m.start() - 10):m.end() + 40]):
                    continue

                pkey = f"{default_act}_SEC_{sec_num}"
                primary_keys.add(pkey)
                label = f"Section {sec_num}"
                if label not in section_labels:
                    section_labels.append(label)
                if sub_num:
                    subsections_found.add(sub_num)

        # ── Step 3: Detect Primary Rule Headers ──────────────────────────────
        for m in _PRIMARY_RULE_HEADER_RE.finditer(text):
            rule_num = m.group(1).upper()
            sub_raw = m.group(2)
            pre_start = max(0, m.start() - 40)
            pre_context = text[pre_start:m.start()].lower()
            if any(cue in pre_context for cue in ["subject to", "referred to in", "under", "in accordance with", "read with"]):
                secondary_keys.add(f"{default_act}_RUL_{rule_num}")
                continue

            pkey = f"{default_act}_RUL_{rule_num}"
            primary_keys.add(pkey)
            label = f"Rule {rule_num}"
            if sub_raw:
                label += f"({sub_raw})"
            if label not in section_labels:
                section_labels.append(label)

        # ── Step 4: Detect Schedules ──────────────────────────────────────────
        for m in _SCHEDULE_HEADER_RE.finditer(text):
            sch_num = m.group(1).upper()
            pkey = f"CGST_SCH_{sch_num}"
            primary_keys.add(pkey)
            label = f"Schedule {sch_num}"
            if label not in section_labels:
                section_labels.append(label)

        # ── Step 5: Detect Cross-References ───────────────────────────────────
        for m in _CROSS_REF_CONTEXT_RE.finditer(text):
            sec_num = m.group(1).upper()
            act_name = m.group(2)
            act_code = default_act
            if act_name:
                for pat, act in _ACT_PATTERNS:
                    if pat.search(act_name):
                        act_code = act
                        break
            secondary_keys.add(f"{act_code}_SEC_{sec_num}")

        # ── Step 6: Extract Document Identity (Circular / Notification) ──────
        fname = Path(rel_path).name if rel_path else ""
        if "circular" in rel_path.lower() or category == "circulars":
            cm = _CIRCULAR_RE.search(fname) or _CIRCULAR_RE.search(text[:300])
            if cm:
                cir_key = f"CIRCULAR_{cm.group(1)}"
                primary_keys.add(cir_key)
                if f"Circular {cm.group(1)}" not in section_labels:
                    section_labels.append(f"Circular {cm.group(1)}")
        
        if "notification" in rel_path.lower() or category == "notifications":
            nm = _NOTIF_RE.search(fname) or _NOTIF_RE.search(text[:300])
            if nm:
                notif_key = f"NOTIF_{nm.group(1)}_{nm.group(2)}"
                primary_keys.add(notif_key)
                if f"Notification {nm.group(1)}/{nm.group(2)}" not in section_labels:
                    section_labels.append(f"Notification {nm.group(1)}/{nm.group(2)}")

        # ── Step 7: Inherit Section from Filename if Document is Section-Dedicated ──
        # e.g. "Section 17.pdf" or "section-13_igst.pdf"
        if not primary_keys and fname:
            sec_match = re.search(r'section[_-]?(\d+[A-Z]?)', fname, re.IGNORECASE)
            if sec_match:
                sec_num = sec_match.group(1).upper()
                primary_keys.add(f"{default_act}_SEC_{sec_num}")
                if f"Section {sec_num}" not in section_labels:
                    section_labels.append(f"Section {sec_num}")

        # ── Step 8: Build Final Provision Keys ────────────────────────────────
        # Primary keys ALWAYS take precedence. Secondary cross-references are added
        # if no primary key was detected, or as supplementary references.
        all_keys = sorted(primary_keys if primary_keys else secondary_keys)
        
        result.primary_provision_keys = sorted(primary_keys)
        result.secondary_citation_keys = sorted(secondary_keys)
        result.primary_section_labels = section_labels
        result.primary_section_label = section_labels[0] if section_labels else None
        result.all_provision_keys = all_keys
        result.subsections = sorted(subsections_found)

        return result
