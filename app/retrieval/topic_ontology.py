"""
Legal Topic Ontology  (Priority 8)
====================================
Hierarchical GST concept tree enabling automatic query expansion.

When a user asks about "ISD", the system recognises it as a leaf under:
    GST → Input Tax Credit → Cross Charge → ISD
…and automatically includes keywords from parent + sibling nodes
so the retriever also surfaces the broader "cross charge" literature.

Design principles:
  - FLAT_EXPANSION: Lookup dict for O(1) expansion at query time
  - No LLM needed — pure keyword matching
  - Additive: expansion adds keywords but never removes the original query terms
  - Capped: max EXPANSION_CAP extra terms so the query doesn't explode
"""
from __future__ import annotations

EXPANSION_CAP = 8   # Maximum number of terms added per query


# ── The ontology tree ─────────────────────────────────────────────────────────
# Format:  concept → {
#     "parent":    str | None,      # parent concept slug
#     "keywords":  list[str],       # canonical keywords for this node
#     "related":   list[str],       # sibling/cousin concepts whose keywords help
# }
#
# All keywords are lowercase; matching is case-insensitive.
# ─────────────────────────────────────────────────────────────────────────────

GST_TOPIC_ONTOLOGY: dict[str, dict] = {

    # ══ Root ═══════════════════════════════════════════════════════════════════
    "gst": {
        "parent": None,
        "keywords": ["gst", "goods and services tax", "cgst", "igst", "sgst", "utgst"],
        "related":  [],
    },

    # ══ Input Tax Credit branch ═════════════════════════════════════════════════
    "itc": {
        "parent": "gst",
        "keywords": ["input tax credit", "itc", "section 16", "input service", "capital goods credit"],
        "related":  ["cross_charge", "apportionment", "blocked_credit"],
    },
    "blocked_credit": {
        "parent": "itc",
        "keywords": ["blocked credit", "section 17(5)", "ineligible itc", "motor vehicles",
                     "club membership", "personal consumption"],
        "related":  ["itc"],
    },
    "apportionment": {
        "parent": "itc",
        "keywords": ["apportionment", "rule 42", "rule 43", "exempt supply",
                     "non-taxable supply", "common credit"],
        "related":  ["cross_charge"],
    },
    "cross_charge": {
        "parent": "itc",
        "keywords": ["cross charge", "distinct person", "inter-branch", "head office",
                     "branch office", "section 25(4)", "section 25(5)", "inter-state"],
        "related":  ["isd", "valuation_related_party", "schedule_i"],
    },
    "isd": {
        "parent": "cross_charge",
        "keywords": ["isd", "input service distributor", "section 20", "rule 39",
                     "distribution of credit", "common input services", "circular 199"],
        "related":  ["cross_charge"],
    },
    "schedule_i": {
        "parent": "cross_charge",
        "keywords": ["schedule i", "supply without consideration", "deemed supply",
                     "entry 2 schedule i", "related person"],
        "related":  ["cross_charge", "valuation_related_party"],
    },

    # ══ Reverse Charge branch ══════════════════════════════════════════════════
    "rcm": {
        "parent": "gst",
        "keywords": ["reverse charge", "rcm", "section 9(3)", "section 9(4)", "unregistered",
                     "notification 13/2017", "rule 85", "rule 86"],
        "related":  ["import_services"],
    },
    "import_services": {
        "parent": "rcm",
        "keywords": ["import of services", "oidar", "section 5(3) igst", "section 5(4) igst",
                     "cross border services", "reverse charge import"],
        "related":  ["rcm", "place_of_supply"],
    },

    # ══ Export / Zero-rated branch ═════════════════════════════════════════════
    "export": {
        "parent": "gst",
        "keywords": ["export", "zero rated", "section 16 igst", "lut", "letter of undertaking",
                     "rule 96", "refund on export", "foreign currency"],
        "related":  ["refund", "sez"],
    },
    "sez": {
        "parent": "export",
        "keywords": ["sez", "special economic zone", "sez unit", "sez developer",
                     "deemed export", "rule 89"],
        "related":  ["export"],
    },

    # ══ Valuation branch ═══════════════════════════════════════════════════════
    "valuation": {
        "parent": "gst",
        "keywords": ["valuation", "transaction value", "section 15", "rule 27", "rule 28",
                     "rule 29", "rule 30", "rule 31", "open market value"],
        "related":  ["valuation_related_party"],
    },
    "valuation_related_party": {
        "parent": "valuation",
        "keywords": ["related party", "distinct person valuation", "rule 28", "rule 28 second proviso",
                     "100% itc", "open market value proviso"],
        "related":  ["cross_charge", "valuation"],
    },

    # ══ Registration branch ════════════════════════════════════════════════════
    "registration": {
        "parent": "gst",
        "keywords": ["registration", "section 22", "section 23", "section 24", "section 25",
                     "distinct person", "voluntary registration", "compulsory registration"],
        "related":  ["cross_charge"],
    },

    # ══ Place of Supply branch ═════════════════════════════════════════════════
    "place_of_supply": {
        "parent": "gst",
        "keywords": ["place of supply", "section 12 igst", "section 13 igst", "pos",
                     "intra-state", "inter-state supply", "intermediary"],
        "related":  ["import_services"],
    },

    # ══ Refund branch ══════════════════════════════════════════════════════════
    "refund": {
        "parent": "gst",
        "keywords": ["refund", "section 54", "rule 89", "unjust enrichment",
                     "refund of itc", "inverted duty structure"],
        "related":  ["export"],
    },

    # ══ GST Rate branch ════════════════════════════════════════════════════════
    "gst_rate": {
        "parent": "gst",
        "keywords": ["rate", "gst rate", "hsn", "sac", "schedule i schedule ii schedule iii",
                     "nil rated", "5%", "12%", "18%", "28%", "notification rate",
                     "tariff heading", "classification"],
        "related":  ["exemption"],
    },
    "exemption": {
        "parent": "gst_rate",
        "keywords": ["exemption", "exempt supply", "nil rate", "section 11",
                     "notification 2/2017", "notification 12/2017"],
        "related":  ["gst_rate"],
    },

    # ══ Works Contract branch ═══════════════════════════════════════════════════
    "works_contract": {
        "parent": "gst",
        "keywords": ["works contract", "section 17(5)(c)", "section 17(5)(d)", "schedule ii entry 6",
                     "construction service", "immovable property", "real estate"],
        "related":  ["real_estate", "blocked_credit"],
    },
    "real_estate": {
        "parent": "works_contract",
        "keywords": ["real estate", "housing project", "commercial apartment", "under construction",
                     "notification 3/2019", "affordable housing", "joint development"],
        "related":  ["works_contract"],
    },

    # ══ Composition branch ════════════════════════════════════════════════════
    "composition": {
        "parent": "gst",
        "keywords": ["composition", "composition scheme", "section 10", "rule 7",
                     "composition dealer", "1% 5% 6%"],
        "related":  [],
    },

    # ══ Annual Return branch ══════════════════════════════════════════════════
    "annual_return": {
        "parent": "gst",
        "keywords": ["annual return", "gstr-9", "gstr-9c", "reconciliation statement",
                     "section 44", "rule 80"],
        "related":  ["gst_audit"],
    },
    "gst_audit": {
        "parent": "annual_return",
        "keywords": ["gst audit", "departmental audit", "section 65", "section 66",
                     "rule 101", "rule 102", "demand gst audit"],
        "related":  ["annual_return", "penalty_demand"],
    },

    # ══ Penalty / Demand branch ════════════════════════════════════════════════
    "penalty_demand": {
        "parent": "gst",
        "keywords": ["penalty", "demand", "section 73", "section 74", "show cause notice",
                     "adjudication", "interest", "section 50", "gstin"],
        "related":  ["gst_audit"],
    },

    # ══ E-commerce branch ══════════════════════════════════════════════════════
    "ecommerce": {
        "parent": "gst",
        "keywords": ["e-commerce", "tcs", "tax collected at source", "section 52",
                     "e-commerce operator", "section 9(5)", "notification 17/2021"],
        "related":  [],
    },

    # ══ Job Work branch ════════════════════════════════════════════════════════
    "job_work": {
        "parent": "gst",
        "keywords": ["job work", "section 19", "rule 45", "return of goods",
                     "goods for job work", "principal manufacturer"],
        "related":  [],
    },

    # ══ TDS under GST branch ══════════════════════════════════════════════════
    "tds_gst": {
        "parent": "gst",
        "keywords": ["tds gst", "tax deducted at source gst", "section 51", "rule 66",
                     "deductor", "gstr-7"],
        "related":  [],
    },

    # ══ Transitional Credit branch ════════════════════════════════════════════
    "transitional_credit": {
        "parent": "itc",
        "keywords": ["transitional credit", "tran-1", "tran-2", "section 140",
                     "pre-gst credit", "cenvat credit carryforward"],
        "related":  ["itc"],
    },

    # ══ Supply branch ══════════════════════════════════════════════════════════
    "supply": {
        "parent": "gst",
        "keywords": ["supply", "section 7", "composite supply", "mixed supply",
                     "time of supply", "section 12 cgst", "section 13 cgst"],
        "related":  ["gst_rate"],
    },
}


# ── Build FLAT_EXPANSION map at import time ───────────────────────────────────
# flat_expansion[trigger_term] = list of additional search terms to add
# Built by traversing parents and siblings.

def _build_flat_expansion() -> dict[str, list[str]]:
    """
    For each concept node, the expanded keyword set is:
        own keywords + parent keywords (½ weight) + related concept keywords (½ weight)

    This is distilled into: trigger_keyword → [extra_keywords]
    """
    expansion: dict[str, list[str]] = {}

    for slug, node in GST_TOPIC_ONTOLOGY.items():
        own_kws = node["keywords"]

        # Collect parent keywords
        parent_kws: list[str] = []
        p = node.get("parent")
        if p and p in GST_TOPIC_ONTOLOGY:
            parent_kws = GST_TOPIC_ONTOLOGY[p]["keywords"]

        # Collect related node keywords (one level deep)
        related_kws: list[str] = []
        for rel_slug in node.get("related", []):
            if rel_slug in GST_TOPIC_ONTOLOGY:
                related_kws.extend(GST_TOPIC_ONTOLOGY[rel_slug]["keywords"])

        # Everything the ontology knows about this concept
        all_extras = list(dict.fromkeys(parent_kws + related_kws))

        # Register each own keyword as a trigger
        for kw in own_kws:
            existing_extras = expansion.get(kw, [])
            for ex in all_extras:
                if ex not in own_kws and ex not in existing_extras:
                    existing_extras.append(ex)
            expansion[kw] = existing_extras

    return expansion


_FLAT_EXPANSION: dict[str, list[str]] = _build_flat_expansion()


# ── Public API ────────────────────────────────────────────────────────────────

def expand_query_with_ontology(query: str) -> tuple[str, list[str]]:
    """
    Takes a raw query and returns (expanded_query, added_terms).

    Expansion is additive: the original query is never modified,
    only supplementary terms are appended.  Total additions are
    capped at EXPANSION_CAP.

    Example:
        "ISD mechanism for head office" →
        added_terms = ["cross charge", "distinct person", "input tax credit",
                       "circular 199", "section 20", "rule 39"]
    """
    query_lower = query.lower()
    added: list[str] = []
    added_set: set[str] = set()

    # Check each trigger keyword
    for trigger, extras in _FLAT_EXPANSION.items():
        if trigger in query_lower:
            for ex in extras:
                if ex not in query_lower and ex not in added_set:
                    added.append(ex)
                    added_set.add(ex)
                    if len(added) >= EXPANSION_CAP:
                        break
        if len(added) >= EXPANSION_CAP:
            break

    if added:
        expanded = query + " " + " ".join(added)
    else:
        expanded = query

    return expanded, added


def get_concept_path(term: str) -> list[str]:
    """
    Returns the ontology path from root to the concept containing `term`.
    E.g. get_concept_path("isd") → ["gst", "itc", "cross_charge", "isd"]

    Returns empty list if term not found.
    """
    term_lower = term.lower()
    for slug, node in GST_TOPIC_ONTOLOGY.items():
        if any(term_lower in kw for kw in node["keywords"]):
            path = [slug]
            p = node.get("parent")
            while p and p in GST_TOPIC_ONTOLOGY:
                path.insert(0, p)
                p = GST_TOPIC_ONTOLOGY[p].get("parent")
            return path
    return []
