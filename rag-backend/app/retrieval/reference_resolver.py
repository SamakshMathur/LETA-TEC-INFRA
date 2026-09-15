import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Act mappings from context
_ACT_KEYWORDS = [
    ("integrated goods", "IGST"),
    ("igst", "IGST"),
    ("central goods", "CGST"),
    ("cgst", "CGST"),
    ("sgst", "SGST"),
    ("state goods", "SGST"),
    ("utgst", "UTGST"),
    ("union territory", "UTGST"),
    ("customs", "CUSTOMS"),
]

_NON_GST_ACT_KEYWORDS = [
    "reserve bank",
    "rbi act",
    "companies act",
    "income-tax",
    "income tax",
    "securities contracts",
    "code of civil procedure",
    "crpc",
    "ipc",
    "general clauses",
]

_LANDMARK_CASES = {
    "mohit minerals": "Mohit Minerals Pvt. Ltd.",
    "safari retreats": "Safari Retreats Pvt. Ltd.",
    "vkc footsteps": "VKC Footsteps India Pvt. Ltd.",
    "bharti airtel": "Bharti Airtel Ltd.",
    "union of india": "Union of India",
    "northern operating": "Northern Operating Systems",
    "canon india": "Canon India Pvt. Ltd.",
    "eicher motors": "Eicher Motors Ltd.",
    "filco trade": "Filco Trade Centre",
}


def resolve_act(
    context_str: str,
    broader_text: Optional[str] = None,
    match_pos: Optional[int] = None,
    default_act: str = "CGST",
) -> str:
    ctx_lower = context_str.lower()
    
    # 0. Check if context explicitly points to an external, non-GST act
    for non_gst in _NON_GST_ACT_KEYWORDS:
        if non_gst in ctx_lower:
            return "NON_GST"

    # 1. Proximity in immediate context window
    best_act = None
    min_dist = float("inf")
    center = len(context_str) // 2
    for keyword, act_code in _ACT_KEYWORDS:
        idx = ctx_lower.find(keyword)
        while idx != -1:
            # Avoid misidentifying tax type mentions as statute: e.g. "IGST on ocean freight", "refund of IGST"
            if keyword == "igst" and any(tax_q in ctx_lower for tax_q in ["igst on", "igst paid", "refund of igst", "levying igst"]):
                idx = ctx_lower.find(keyword, idx + 1)
                continue
            dist = abs(idx - center)
            if dist < min_dist:
                min_dist = dist
                best_act = act_code
            idx = ctx_lower.find(keyword, idx + 1)
    if best_act:
        return best_act

    # 2. Check broader preceding text context (bounded to local sentence/paragraph)
    if broader_text and match_pos is not None:
        b_full = broader_text[max(0, match_pos - 300):match_pos]
        sent_bound = max(b_full.rfind(".\n"), b_full.rfind(". "), b_full.rfind("\n\n"), b_full.rfind(":\n"))
        b_text = b_full[sent_bound:].lower() if sent_bound != -1 else b_full.lower()
        for non_gst in _NON_GST_ACT_KEYWORDS:
            if non_gst in b_text:
                return "NON_GST"
        max_idx = -1
        b_act = None
        for keyword, act_code in _ACT_KEYWORDS:
            idx = b_text.rfind(keyword)
            if idx > max_idx:
                if keyword == "igst" and any(tq in b_text[idx:] for tq in ["igst on", "igst paid", "refund of igst", "levying igst"]):
                    continue
                max_idx = idx
                b_act = act_code
        if b_act:
            return b_act

        # 3. Check broader forward text context (bounded to local sentence)
        f_full = broader_text[match_pos:min(len(broader_text), match_pos + 150)]
        f_bound = min(
            [pos for pos in [f_full.find(".\n"), f_full.find(". "), f_full.find("\n\n")] if pos != -1] or [len(f_full)]
        )
        f_text = f_full[:f_bound].lower()
        min_f_idx = float("inf")
        f_act = None
        for keyword, act_code in _ACT_KEYWORDS:
            idx = f_text.find(keyword)
            if idx != -1 and idx < min_f_idx:
                if keyword == "igst" and any(tq in f_text[idx:] for tq in ["igst on", "igst paid", "refund of igst", "levying igst"]):
                    continue
                min_f_idx = idx
                f_act = act_code
        if f_act:
            return f_act

    return default_act


def resolve_rule_act(context_str: str, rule_num_str: str) -> str:
    """
    Resolve statute for a rule reference.
    In Indian GST law, substantive rules (such as Rule 89, Rule 96, Rule 42, Rule 43, etc.)
    belong exclusively to the CGST Rules, 2017 (which apply mutatis mutandis to IGST).
    The IGST Rules, 2017 only contain Rules 1 through 5.
    Mentions of 'IGST' near a rule in context almost always refer to the tax type
    (e.g., 'refund of IGST under Rule 96'), NOT 'IGST Rules'.
    Therefore, unless context explicitly states 'igst rule' or 'integrated goods and services tax rule',
    all GST rules default to CGST.
    """
    ctx_lower = context_str.lower()
    if "igst rule" in ctx_lower or "integrated goods and services tax rule" in ctx_lower:
        return "IGST"
    if "sgst rule" in ctx_lower or "state goods and services tax rule" in ctx_lower:
        return "SGST"
    if "utgst rule" in ctx_lower:
        return "UTGST"
    return "CGST"


@dataclass(frozen=True)
class LegalReference:
    """Canonical representation of an Indian GST legal authority."""
    ref_type: str                  # SECTION | RULE | CIRCULAR | NOTIFICATION | SCHEDULE | CASE_LAW
    statute: str                   # CGST | IGST | SGST | UTGST | CUSTOMS
    provision_num: str             # e.g. "17", "73", "88D", "184", "04/2022", "III"
    subsection: Optional[str] = None  # e.g. "5", "1", "9"
    clause: Optional[str] = None      # e.g. "a", "fa", "b"
    subclause: Optional[str] = None   # e.g. "i", "ii"
    year: Optional[str] = None        # e.g. "2022", "2017"
    authority_name: Optional[str] = None  # e.g. "Mohit Minerals"
    raw_text: str = ""
    source_text: str = ""

    @property
    def base_key(self) -> str:
        """Coarse key for indexing and broad taxonomy (e.g. CGST_SEC_17)."""
        if self.ref_type == "SECTION":
            return f"{self.statute}_SEC_{self.provision_num}"
        if self.ref_type == "RULE":
            return f"{self.statute}_RUL_{self.provision_num}"
        if self.ref_type == "CIRCULAR":
            return f"CIRCULAR_{self.provision_num}"
        if self.ref_type == "NOTIFICATION":
            yr_str = f"_{self.year}" if self.year else ""
            return f"NOTIF_{self.provision_num.replace('/', '_')}{yr_str}"
        if self.ref_type == "SCHEDULE":
            return f"CGST_SCH_{self.provision_num.upper()}"
        if self.ref_type == "CASE_LAW":
            return f"CASE_{re.sub(r'[^a-zA-Z0-9]+', '_', (self.authority_name or self.provision_num).upper()).strip('_')}"
        return f"{self.statute}_{self.ref_type}_{self.provision_num}"

    @property
    def canonical_key(self) -> str:
        """Exact specific key preserving subsection and clause (e.g. CGST_SEC_17(5)(a))."""
        if self.ref_type == "CIRCULAR":
            return f"CIRCULAR_{self.provision_num}"
        key = self.base_key
        if self.subsection:
            key += f"({self.subsection})"
        if self.clause:
            key += f"({self.clause})"
        if self.subclause:
            key += f"({self.subclause})"
        return key


    @property
    def display_name(self) -> str:
        if self.ref_type == "SECTION":
            sub = f"({self.subsection})" if self.subsection else ""
            cl = f"({self.clause})" if self.clause else ""
            subcl = f"({self.subclause})" if self.subclause else ""
            return f"Section {self.provision_num}{sub}{cl}{subcl} of {self.statute} Act"
        if self.ref_type == "RULE":
            sub = f"({self.subsection})" if self.subsection else ""
            return f"Rule {self.provision_num}{sub} of {self.statute} Rules"
        if self.ref_type == "CIRCULAR":
            return f"Circular No. {self.provision_num}"
        if self.ref_type == "NOTIFICATION":
            yr = f"/{self.year}" if self.year and "/" not in self.provision_num else ""
            return f"Notification No. {self.provision_num}{yr}"
        if self.ref_type == "SCHEDULE":
            return f"Schedule {self.provision_num.upper()}"
        if self.ref_type == "CASE_LAW":
            return f"Case: {self.authority_name or self.provision_num}"
        return self.raw_text or self.canonical_key

    def is_exact_or_child_of(self, other: "LegalReference") -> bool:
        """
        Check if self is at least as specific as other and belongs to the same provision.
        e.g. Section 17(5)(a) satisfies a request for Section 17(5) or Section 17.
        """
        if self.ref_type != other.ref_type or self.statute != other.statute or self.provision_num != other.provision_num:
            return False
        if other.subsection and self.subsection != other.subsection:
            return False
        if other.clause and self.clause != other.clause:
            return False
        if other.subclause and self.subclause != other.subclause:
            return False
        return True


class ReferenceResolver:
    """
    Authoritative Canonical Legal Reference Resolver for Indian GST Law.
    Extracts, canonicalizes, and verifies legal references across queries,
    retrieved chunks, and generated synthesis text.
    """

    @classmethod
    def resolve_references(cls, text: str, default_statute: Optional[str] = None) -> List[LegalReference]:
        """Extract all canonical LegalReference objects from text."""
        if not text or not text.strip():
            return []

        resolved: List[LegalReference] = []
        seen_keys: Set[str] = set()

        def _add(ref: LegalReference):
            if ref.canonical_key not in seen_keys:
                seen_keys.add(ref.canonical_key)
                resolved.append(ref)

        # Determine document-level default statute
        t_lower = text.lower()
        doc_act = default_statute or "CGST"
        if not default_statute:
            has_igst = ("integrated goods" in t_lower or "igst act" in t_lower)
            has_cgst = ("central goods" in t_lower or "cgst act" in t_lower)
            if has_igst and not has_cgst:
                doc_act = "IGST"
            elif has_igst and has_cgst:
                igst_pos = min(
                    t_lower.find("integrated goods") if "integrated goods" in t_lower else len(t_lower),
                    t_lower.find("igst act") if "igst act" in t_lower else len(t_lower),
                )
                cgst_pos = min(
                    t_lower.find("central goods") if "central goods" in t_lower else len(t_lower),
                    t_lower.find("cgst act") if "cgst act" in t_lower else len(t_lower),
                )
                if igst_pos < cgst_pos and ("section 13" in t_lower or "place of supply" in t_lower):
                    doc_act = "IGST"

        # 1a. Parse inverted Section references:
        # e.g., "sub-clause (i) of clause (a) of sub-section (5) of section 17"
        # e.g., "clause (a) of sub-section (5) of section 17"
        # e.g., "sub-section (6) of section 2", "subsection 6 of section 2", "sub-section (6) of Sec. 2"
        # e.g., "clause (a) of section 17"
        inv_sec_pattern = re.compile(
            r'(?:sub(?:-)?clause\s*\(?([\da-zA-Z]+)\)?\s+of\s+)?'
            r'(?:clause\s*\(?([\da-zA-Z]+)\)?\s+of\s+)?'
            r'(?:sub(?:-)?section\s*\(?([\da-zA-Z]+)\)?\s+of\s+(?:the\s+)?)?'
            r'(?:clause\s*\(?([\da-zA-Z]+)\)?\s+of\s+(?:the\s+)?)?'
            r'\bsec(?:tion)?\s*[-–—\.]?\s*(\d+[A-Za-z]*)',
            re.IGNORECASE,
        )
        for m in inv_sec_pattern.finditer(text):
            subcl = m.group(1)
            cl1 = m.group(2)
            subsec = m.group(3)
            cl2 = m.group(4)
            sec_num = m.group(5).upper()
            clause = cl1 or cl2

            if subsec or clause or subcl:
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                ctx = text[start:end]
                act = resolve_act(ctx, broader_text=text, match_pos=m.start(), default_act=doc_act)
                if act == "NON_GST":
                    continue

                _add(LegalReference(
                    ref_type="SECTION",
                    statute=act,
                    provision_num=sec_num,
                    subsection=subsec,
                    clause=clause,
                    subclause=subcl,
                    raw_text=m.group(0),
                ))

        # 1b. Parse standard Section references:
        # e.g., "Section 17", "Section 17(5)", "Section 17(5)(a)", "Sec. 73(9)", "Section 73 subsection (10)", "Section - 13"
        sec_pattern = re.compile(
            r'\bsec(?:tion)?\s*[-–—\.]?\s*(\d+[A-Za-z]*)'
            r'(?:\s*\((?!S\d+\))([\da-zA-Z]+)\))?'
            r'(?:\s*\((?!S\d+\))([\da-zA-Z]+)\))?'
            r'(?:\s*\((?!S\d+\))([\da-zA-Z]+)\))?',
            re.IGNORECASE,
        )
        for m in sec_pattern.finditer(text):
            sec_num = m.group(1).upper()
            subsec = m.group(2)
            clause = m.group(3)
            subclause = m.group(4)

            # Determine surrounding act context
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            ctx = text[start:end]
            act = resolve_act(ctx, broader_text=text, match_pos=m.start(), default_act=doc_act)
            if act == "NON_GST":
                continue

            # Check for trailing written form "sub-section (10)"
            if not subsec:
                sub_match = re.search(r'\bsub(?:-)?section\s*\(?(\d+)\)?', text[m.end(): min(len(text), m.end() + 30)], re.IGNORECASE)
                if sub_match:
                    subsec = sub_match.group(1)

            _add(LegalReference(
                ref_type="SECTION",
                statute=act,
                provision_num=sec_num,
                subsection=subsec,
                clause=clause,
                subclause=subclause,
                raw_text=m.group(0),
            ))

        # 2a. Parse inverted Rule references:
        # e.g., "clause (b) of sub-rule (4) of rule 89", "sub-rule (4) of rule 89", "subrule 4 of rule 89", "clause (b) of rule 89"
        inv_rule_pattern = re.compile(
            r'(?:sub(?:-)?clause\s*\(?([\da-zA-Z]+)\)?\s+of\s+)?'
            r'(?:clause\s*\(?([\da-zA-Z]+)\)?\s+of\s+)?'
            r'(?:sub(?:-)?rule\s*\(?([\da-zA-Z]+)\)?\s+of\s+(?:the\s+)?)?'
            r'(?:clause\s*\(?([\da-zA-Z]+)\)?\s+of\s+(?:the\s+)?)?'
            r'\brule\s*[-–—\.]?\s*(\d+[A-Za-z]*)',
            re.IGNORECASE,
        )
        for m in inv_rule_pattern.finditer(text):
            subcl = m.group(1)
            cl1 = m.group(2)
            subrule = m.group(3)
            cl2 = m.group(4)
            rule_num = m.group(5).upper()
            clause = cl1 or cl2

            if subrule or clause or subcl:
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                ctx = text[start:end]
                act = resolve_rule_act(ctx, rule_num)

                _add(LegalReference(
                    ref_type="RULE",
                    statute=act,
                    provision_num=rule_num,
                    subsection=subrule,
                    clause=clause,
                    raw_text=m.group(0),
                ))

        # 2b. Parse standard Rule references:
        # e.g., "Rule 88D", "rule 142(1)", "Rule 89(4)(b)", "Rule - 96"
        rule_pattern = re.compile(
            r'\brule\s*[-–—\.]?\s*(\d+[A-Za-z]*)'
            r'(?:\s*\((?!S\d+\))([\da-zA-Z]+)\))?'
            r'(?:\s*\((?!S\d+\))([\da-zA-Z]+)\))?',
            re.IGNORECASE,
        )
        for m in rule_pattern.finditer(text):
            rule_num = m.group(1).upper()
            subrule = m.group(2)
            cl = m.group(3)
            ctx = text[max(0, m.start() - 40): min(len(text), m.end() + 40)]
            act = resolve_rule_act(ctx, rule_num)

            _add(LegalReference(
                ref_type="RULE",
                statute=act,
                provision_num=rule_num,
                subsection=subrule,
                clause=cl,
                raw_text=m.group(0),
            ))

        # 3. Parse Circular references:
        # e.g., "Circular No. 184/16/2022-GST", "Circular 184", "Cir 184/2022", "circularno-37", "Circular-No-241"
        cir_pattern = re.compile(
            r'\b(?:circular[s]?|cir)[-_.\s]*(?:no\.?[-_.\s]*)?(\d{2,3})(?:/(\d+))?(?:/(\d{4}))?',
            re.IGNORECASE,
        )
        for m in cir_pattern.finditer(text):
            cir_num = m.group(1)
            sub_num = m.group(2)
            yr = m.group(3)

            _add(LegalReference(
                ref_type="CIRCULAR",
                statute="CGST",
                provision_num=cir_num,
                subsection=sub_num,
                year=yr,
                raw_text=m.group(0),
            ))

        # 4. Parse Notification references:
        # e.g., "Notification 04/2022", "Notification No. 04/2022-Central Tax", "notif 12/2017"
        notif_pattern = re.compile(
            r'\b(?:notification|notif)[-_.\s]*(?:no\.?[-_.\s]*)?(\d+)[/\-](\d{2,4})',
            re.IGNORECASE,
        )
        for m in notif_pattern.finditer(text):
            num = m.group(1)
            yr = m.group(2)
            if len(yr) == 2:
                yr = "20" + yr
            ctx = text[max(0, m.start() - 40): min(len(text), m.end() + 40)]
            act = resolve_act(ctx, broader_text=text, match_pos=m.start(), default_act=doc_act)
            if act == "NON_GST":
                act = "CGST"

            _add(LegalReference(
                ref_type="NOTIFICATION",
                statute=act,
                provision_num=f"{num}/{yr}",
                year=yr,
                raw_text=m.group(0),
            ))

        # 5. Parse Schedule references:
        # e.g., "Schedule II", "Schedule III", "Schedule 3"
        sch_pattern = re.compile(r'\bschedule\s+([ivxlcdm]+|\d+)\b', re.IGNORECASE)
        for m in sch_pattern.finditer(text):
            sch_val = m.group(1).upper()
            _add(LegalReference(
                ref_type="SCHEDULE",
                statute="CGST",
                provision_num=sch_val,
                raw_text=m.group(0),
            ))

        # 6. Parse Landmark Case Law references:
        t_lower = text.lower()
        for case_kw, full_case_name in _LANDMARK_CASES.items():
            if case_kw in t_lower:
                _add(LegalReference(
                    ref_type="CASE_LAW",
                    statute="CGST",
                    provision_num=case_kw,
                    authority_name=full_case_name,
                    raw_text=full_case_name,
                ))

        return resolved

    @classmethod
    def extract_canonical_keys(cls, text: str) -> List[str]:
        """Convenience method returning list of unique canonical keys."""
        return [ref.canonical_key for ref in cls.resolve_references(text)]

    @classmethod
    def extract_available_chunk_references(cls, chunks: List[Dict[str, Any]]) -> List[LegalReference]:
        """Extract all legal references present in retrieved chunks (metadata + path + text)."""
        available: List[LegalReference] = []
        seen_refs_map: Dict[str, LegalReference] = {}

        def _add_chunk_refs(refs: List[LegalReference], chunk_text: str):
            for r in refs:
                if r.canonical_key not in seen_refs_map:
                    r_with_src = LegalReference(
                        ref_type=r.ref_type,
                        statute=r.statute,
                        provision_num=r.provision_num,
                        subsection=r.subsection,
                        clause=r.clause,
                        subclause=r.subclause,
                        year=r.year,
                        authority_name=r.authority_name,
                        raw_text=r.raw_text,
                        source_text=chunk_text,
                    )
                    seen_refs_map[r.canonical_key] = r_with_src
                    available.append(r_with_src)
                else:
                    existing = seen_refs_map[r.canonical_key]
                    if chunk_text and chunk_text not in existing.source_text:
                        updated = LegalReference(
                            ref_type=existing.ref_type,
                            statute=existing.statute,
                            provision_num=existing.provision_num,
                            subsection=existing.subsection,
                            clause=existing.clause,
                            subclause=existing.subclause,
                            year=existing.year,
                            authority_name=existing.authority_name,
                            raw_text=existing.raw_text,
                            source_text=(existing.source_text + "\n" + chunk_text).strip(),
                        )
                        seen_refs_map[r.canonical_key] = updated
                        try:
                            idx = available.index(existing)
                            available[idx] = updated
                        except ValueError:
                            pass

        for c in chunks:
            chunk_refs: List[LegalReference] = []
            chunk_text = c.get("text") or c.get("embed_text") or c.get("content") or ""

            # 1. Inspect explicit provision keys in metadata & chunk fields
            meta = c.get("metadata") or {}
            prov_keys = (
                list(meta.get("provision_keys") or [])
                + list(meta.get("provisions") or [])
                + ([c.get("provision")] if c.get("provision") else [])
                + ([c.get("_anchor_provision")] if c.get("_anchor_provision") else [])
                + ([c.get("_pinned_canonical_key")] if c.get("_pinned_canonical_key") else [])
            )
            for pk in prov_keys:
                if not pk:
                    continue
                pk_str = str(pk).strip()
                chunk_refs.extend(cls.resolve_references(pk_str.replace("_", " ")))

            # 2. Inspect rel_path, source, and title (critical for case laws and unindexed circulars)
            rel_path = (c.get("rel_path") or meta.get("rel_path") or c.get("source") or "").replace("\\", "/")
            if rel_path:
                normalized_path = re.sub(r'[-_./\\]+', ' ', rel_path)
                chunk_refs.extend(cls.resolve_references(normalized_path))

            # 3. Inspect chunk text
            if chunk_text:
                chunk_refs.extend(cls.resolve_references(chunk_text))

            # 4. Parse statutory numbered paragraphs when parent section/rule is established
            # e.g., "(3) A registered person..." in a Section 16 chunk, "(8)... (a)..." in Section 13 chunk
            is_statute = (
                bool(c.get("_is_statute_first"))
                or "acts" in rel_path.lower()
                or "rules" in rel_path.lower()
                or any(r.ref_type in ("SECTION", "RULE") for r in chunk_refs)
            )
            if is_statute and chunk_text:
                # Find all base parent sections and rules established for this chunk
                parent_sections = [r for r in chunk_refs if r.ref_type == "SECTION" and not r.subsection]
                parent_rules = [r for r in chunk_refs if r.ref_type == "RULE" and not r.subsection]

                # Match statutory numbered paragraphs including omitted/bracketed subsections e.g. "(8) The..." or "(9) 26b[***]"
                para_matches = list(re.finditer(
                    r'(?:^|\n|\.\s+|;\s*)\s*\((\d+[A-Za-z]*)\)\s+([A-Za-z0-9"“\'\[])',
                    chunk_text,
                ))

                # Handle continuation chunks where active_subsection was inherited from a previous chunk
                active_subsec = meta.get("active_subsection") or c.get("active_subsection")
                first_para_start = para_matches[0].start() if para_matches else len(chunk_text)
                leading_span = chunk_text[:first_para_start]
                roman_numerals = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}

                if active_subsec and leading_span:
                    for parent_sec in parent_sections:
                        chunk_refs.append(LegalReference(
                            ref_type="SECTION",
                            statute=parent_sec.statute,
                            provision_num=parent_sec.provision_num,
                            subsection=active_subsec,
                            raw_text=f"({active_subsec})",
                        ))
                        leading_clauses = re.finditer(r'(?:^|\n|\s+|;\s*)\(([a-z]{1,2})\)\s+([A-Za-z"“\'\[])', leading_span)
                        for cm in leading_clauses:
                            cl_val = cm.group(1)
                            if cl_val in roman_numerals:
                                continue
                            chunk_refs.append(LegalReference(
                                ref_type="SECTION",
                                statute=parent_sec.statute,
                                provision_num=parent_sec.provision_num,
                                subsection=active_subsec,
                                clause=cl_val,
                                raw_text=cm.group(0),
                            ))

                for idx, pm in enumerate(para_matches):
                    subsec_val = pm.group(1)
                    sub_start = pm.start()
                    sub_end = para_matches[idx + 1].start() if idx + 1 < len(para_matches) else len(chunk_text)
                    sub_span_text = chunk_text[sub_start:sub_end]

                    for parent_sec in parent_sections:
                        chunk_refs.append(LegalReference(
                            ref_type="SECTION",
                            statute=parent_sec.statute,
                            provision_num=parent_sec.provision_num,
                            subsection=subsec_val,
                            raw_text=pm.group(0),
                        ))
                        clause_matches = re.finditer(r'(?:^|\n|\s+|;\s*)\(([a-z]{1,2})\)\s+([A-Za-z"“\'\[])', sub_span_text)
                        for cm in clause_matches:
                            cl_val = cm.group(1)
                            if cl_val in roman_numerals:
                                continue
                            chunk_refs.append(LegalReference(
                                ref_type="SECTION",
                                statute=parent_sec.statute,
                                provision_num=parent_sec.provision_num,
                                subsection=subsec_val,
                                clause=cl_val,
                                raw_text=cm.group(0),
                            ))

                    for parent_rul in parent_rules:
                        chunk_refs.append(LegalReference(
                            ref_type="RULE",
                            statute=parent_rul.statute,
                            provision_num=parent_rul.provision_num,
                            subsection=subsec_val,
                            raw_text=pm.group(0),
                        ))
                        clause_matches = re.finditer(r'(?:^|\n|\s+|;\s*)\(([a-z]{1,2})\)\s+([A-Za-z"“\'\[])', sub_span_text)
                        for cm in clause_matches:
                            cl_val = cm.group(1)
                            if cl_val in roman_numerals:
                                continue
                            chunk_refs.append(LegalReference(
                                ref_type="RULE",
                                statute=parent_rul.statute,
                                provision_num=parent_rul.provision_num,
                                subsection=subsec_val,
                                clause=cl_val,
                                raw_text=cm.group(0),
                            ))

            # Add all references found in this chunk with source_text attached
            _add_chunk_refs(chunk_refs, chunk_text)

        return available

    @classmethod
    def verify_citation_against_evidence(
        cls,
        cited_ref: LegalReference,
        available_refs: List[LegalReference],
    ) -> Tuple[bool, Optional[LegalReference]]:
        """
        Verify if cited_ref is supported by available_refs.
        Enforces strict specificity invariants:
        - Section 17(5) requires an available Section 17(5) or Section 17(5)(a).
        - Section 17 does NOT validate Section 17(5).
        - Section 17(5) does NOT validate general Section 17 unless exact 17 is also available.
        - Circular 184 requires Circular 184.
        - Case law (e.g. Safari Retreats) requires matching Case Law evidence.
        """
        for avail in available_refs:
            # 1. Exact canonical key match
            if avail.canonical_key == cited_ref.canonical_key:
                return True, avail

            # 2. Case Law matching by authority name or provision num
            if cited_ref.ref_type == "CASE_LAW" and avail.ref_type == "CASE_LAW":
                if (cited_ref.provision_num and cited_ref.provision_num == avail.provision_num) or \
                   (cited_ref.authority_name and avail.authority_name and cited_ref.authority_name.lower() in avail.authority_name.lower()):
                    return True, avail

            # 3. If avail is exact or more specific than cited (e.g. avail Sec 17(5)(a) supports claim Sec 17(5) or Sec 17; avail Rule 86A(1) supports claim Rule 86A)
            if avail.is_exact_or_child_of(cited_ref):
                return True, avail

            # 4. If cited has subsection/clause and avail is parent provision, check if avail source_text explicitly contains the child provision
            if cited_ref.subsection and avail.ref_type == cited_ref.ref_type and avail.statute == cited_ref.statute and avail.provision_num == cited_ref.provision_num:
                src = (avail.source_text or "").lower()
                if src:
                    subsec = cited_ref.subsection.lower()
                    sub_patterns = [
                        f"({subsec})",
                        f"sub-section ({subsec})",
                        f"sub-section {subsec}",
                        f"subsection ({subsec})",
                        f"subsection {subsec}",
                        f"sub section ({subsec})",
                        f"sub-rule ({subsec})",
                        f"sub-rule {subsec}",
                        f"subrule ({subsec})",
                        f"subrule {subsec}",
                        f"sub rule ({subsec})",
                    ]
                    has_sub = any(p in src for p in sub_patterns)
                    if has_sub:
                        if cited_ref.clause:
                            cl = cited_ref.clause.lower()
                            cl_patterns = [
                                f"({cl})",
                                f"clause ({cl})",
                                f"clause {cl}",
                            ]
                            has_cl = any(p in src for p in cl_patterns)
                            if has_cl:
                                return True, avail
                        else:
                            return True, avail

        return False, None
