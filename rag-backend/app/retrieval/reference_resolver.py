import re
import logging

logger = logging.getLogger(__name__)

# Act mappings from context
_ACT_KEYWORDS = [
    ("cgst", "CGST"),
    ("igst", "IGST"),
    ("sgst", "SGST"),
    ("utgst", "UTGST"),
    ("central goods", "CGST"),
    ("integrated goods", "IGST"),
    ("union territory", "UTGST")
]

def resolve_act(context_str: str) -> str:
    ctx_lower = context_str.lower()
    for keyword, act_code in _ACT_KEYWORDS:
        if keyword in ctx_lower:
            return act_code
    return "CGST"  # default standard falls back to CGST

class ReferenceResolver:
    """
    Generic Reference Resolver for Indian GST Law.
    Resolves explicit section, rule, notification, and circular citations
    into normalized structural objects.
    """

    @staticmethod
    def resolve_references(query: str) -> list[dict]:
        if not query or not query.strip():
            return []

        q = query.lower()
        resolved = []
        seen_keys = set()

        # Helper to avoid duplicates
        def _add(ref_obj: dict):
            key = ref_obj["canonical_key"]
            if key not in seen_keys:
                seen_keys.add(key)
                resolved.append(ref_obj)

        # 1. Parse Section references: "Section 73", "sec. 73(10)", "Section 73 subsection (10)"
        sec_pattern = r'\bsec(?:tion)?\s*\.?\s*(\d+[A-Z]*)(?:\s*\(([^)]+)\))?(?:\s*\(([^)]+)\))?'
        for m in re.finditer(sec_pattern, q):
            sec_num = m.group(1).upper()
            subsec = m.group(2) if m.group(2) else None
            clause = m.group(3) if m.group(3) else None

            # Find surrounding act context (40 chars before/after)
            ctx = q[max(0, m.start() - 40): m.end() + 40]
            act = resolve_act(ctx)

            # Sub-sections could be written as "sub-section (10)" later in query - we check for this
            if not subsec:
                sub_match = re.search(r'\bsub(?:-)?section\s*\(?(\d+)\)?', q[m.end(): m.end() + 30])
                if sub_match:
                    subsec = sub_match.group(1)

            canonical_key = f"{act}_SEC_{sec_num}"
            _add({
                "reference_type": "STATUTE_PROVISION",
                "statute": act,
                "provision": sec_num,
                "subsection": subsec,
                "clause": clause,
                "canonical_key": canonical_key,
                "confidence": 1.0
            })

        # 2. Parse Rule references: "Rule 88D", "rule 142(1)"
        rule_pattern = r'\brule\s+(\d+[A-Z]*)(?:\s*\(([^)]+)\))?'
        for m in re.finditer(rule_pattern, q):
            rule_num = m.group(1).upper()
            subrule = m.group(2) if m.group(2) else None

            ctx = q[max(0, m.start() - 40): m.end() + 40]
            act = resolve_act(ctx)

            canonical_key = f"{act}_RUL_{rule_num}"
            _add({
                "reference_type": "RULE",
                "statute": act,
                "provision": rule_num,
                "subsection": subrule,
                "clause": None,
                "canonical_key": canonical_key,
                "confidence": 1.0
            })

        # 3. Parse Notification references: "Notification 40/2021", "Notification No. 40/2021-Central Tax"
        notif_pattern = r'\bnotif(?:ication)?\s*(?:no\.?\s*)?(\d+)[/\-](\d{4})'
        for m in re.finditer(notif_pattern, q):
            num = m.group(1)
            year = m.group(2)

            ctx = q[max(0, m.start() - 40): m.end() + 40]
            act = resolve_act(ctx)

            canonical_key = f"{act}_NOT_{num}_{year}"
            _add({
                "reference_type": "NOTIFICATION",
                "statute": act,
                "provision": f"{num}/{year}",
                "subsection": None,
                "clause": None,
                "canonical_key": canonical_key,
                "confidence": 1.0
            })

        # 4. Parse Circular references: "Circular 185", "Circular No. 185/17/2022-GST"
        cir_pattern = r'\bcircular\s+(?:no\.?\s*)?(\d{2,3})(?:/\d+)?(?:/\d{4})?\b'
        for m in re.finditer(cir_pattern, q):
            cir_num = m.group(1)

            canonical_key = f"CIRCULAR_{cir_num}"
            _add({
                "reference_type": "CIRCULAR",
                "statute": "CGST",  # Circulars are issued globally under CGST
                "provision": cir_num,
                "subsection": None,
                "clause": None,
                "canonical_key": canonical_key,
                "confidence": 1.0
            })

        return resolved
