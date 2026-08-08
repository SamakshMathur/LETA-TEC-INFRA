"""
GST Governing-Authority Taxonomy
=================================
Maps GST topics to their governing authorities (sections, rules, circulars).

Instead of asking "which chunk is most similar?" this module answers
"which statutory provisions, rules, and CBIC circulars GOVERN this topic?"

A practitioner answering a cross-charge question doesn't start with a
semantic search — they go straight to Section 25(4)/(5), Rule 28, Rule 39,
Section 20, and Circular 199.  This taxonomy encodes that expertise so the
retriever does the same thing.

Design principles:
  - Multiple topics can match a single query (ITC on works contract → both)
  - Keywords are checked by substring, not whole-word (conservative matching)
  - The taxonomy is additive: more keyword hits = higher confidence
  - authority_bonus_multiplier: per-topic authority type weight adjustments
    so that for rate queries notifications outrank acts, not the other way around

JSON Registry Layer (Priority 12 — Continuous Authority Learning):
  At startup, this module checks for data/authority_registry.json.
  If found, JSON entries are MERGED over the Python base registry so that the
  legal team can update, add, or override authority mappings without code changes.

  How to add a new circular from CBIC:
    1. Open  RAG/rag-backend/data/authority_registry.json
    2. Find the relevant topic (or add a new topic key)
    3. Add "CIRCULAR_<number>" to the "circulars" array
    4. Commit — takes effect on next server restart.  No Python change needed.
"""
from __future__ import annotations
import json
import math
import os
import re
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Taxonomy: topic → governing authorities
# Each entry:
#   keywords        : substrings matched against the lowercased query
#   sections        : provision-index keys (CGST_SEC_N / IGST_SEC_N / CGST_RUL_N)
#   circulars       : circular-index keys  (CIRCULAR_N)
#   expected_cats   : set of document categories that MUST appear in final output
#   authority_adj   : adjustments to source_priority() multiplier by category
#                     e.g. {"notification": 1.5} → notifications get 1.5× bonus
# ─────────────────────────────────────────────────────────────────────────────

GST_GOVERNING_AUTHORITIES: dict[str, dict] = {

    # ── Cross Charge / ISD ─────────────────────────────────────────────────
    "cross_charge": {
        "keywords": [
            "cross charge", "crosscharge", "distinct person", "head office",
            "branch office", "isd", "input service distributor", "common input",
            "common expenses", "shared services", "internally generated",
            "third party invoice", "common service", "ho branch", "head branch",
        ],
        "sections":  ["CGST_SEC_20", "CGST_SEC_25", "IGST_SEC_8"],
        "rules":     ["CGST_RUL_28", "CGST_RUL_39"],
        "circulars": ["CIRCULAR_199"],
        "expected_cats": {"statute", "circular"},
        "authority_adj": {"circular": 1.4, "statute": 1.1},
    },

    # ── ITC / Blocked Credit ───────────────────────────────────────────────
    "itc": {
        "keywords": [
            "input tax credit", "itc", "blocked credit", "section 17(5)",
            "section 16", "credit availment", "eligibility of credit",
            "credit reversal", "rule 42", "rule 43", "apportionment",
            "motor vehicle", "food beverage", "club", "health",
            "construction immovable", "works contract credit",
        ],
        "sections":  ["CGST_SEC_16", "CGST_SEC_17", "CGST_SEC_18"],
        "rules":     ["CGST_RUL_42", "CGST_RUL_43", "CGST_RUL_44"],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2, "circular": 1.1},
    },

    # ── Reverse Charge (RCM) ───────────────────────────────────────────────
    "rcm": {
        "keywords": [
            "reverse charge", "rcm", "section 9(3)", "section 9(4)",
            "reverse charge mechanism", "recipient pays", "gta",
            "goods transport", "legal service", "director",
            "advocate", "sponsorship", "import of service", "oidar",
        ],
        "sections":  ["CGST_SEC_9", "IGST_SEC_5"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute", "notification"},
        "authority_adj": {"notification": 1.4, "statute": 1.1},
    },

    # ── Export / Zero-Rated / LUT ──────────────────────────────────────────
    "export": {
        "keywords": [
            "export", "zero rated", "lut", "letter of undertaking",
            "igst refund", "export of service", "export of goods",
            "foreign exchange", "deemed export", "merchant export",
            "sez supply", "zero-rated supply",
        ],
        "sections":  ["IGST_SEC_16", "CGST_SEC_54"],
        "rules":     ["CGST_RUL_89", "CGST_RUL_96"],
        "circulars": [],
        "expected_cats": {"statute", "notification", "circular"},
        "authority_adj": {"notification": 1.3, "circular": 1.2},
    },

    # ── Works Contract / Construction ──────────────────────────────────────
    "works_contract": {
        "keywords": [
            "works contract", "construction", "immovable property",
            "schedule ii entry 6", "composite supply of works",
            "civil structure", "contractor", "subcontractor",
            "original works", "repair maintenance", "schedule ii",
        ],
        "sections":  ["CGST_SEC_17", "CGST_SEC_7"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.3},
    },

    # ── Place of Supply ────────────────────────────────────────────────────
    "place_of_supply": {
        "keywords": [
            "place of supply", "pos", "section 12", "section 13 igst",
            "intermediary", "inter-state", "intra-state", "location of supplier",
            "location of recipient", "b2c", "oidar", "online information",
        ],
        "sections":  ["IGST_SEC_12", "IGST_SEC_13"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Registration / Distinct Person / Aggregate Turnover ───────────────
    "registration": {
        "keywords": [
            "registration", "gstin", "section 22", "section 24", "section 25",
            "aggregate turnover", "threshold limit", "compulsory registration",
            "voluntary registration", "cancellation", "suspension",
        ],
        "sections":  ["CGST_SEC_22", "CGST_SEC_23", "CGST_SEC_24", "CGST_SEC_25"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Refund ─────────────────────────────────────────────────────────────
    "refund": {
        "keywords": [
            "refund", "section 54", "unutilised itc", "inverted duty",
            "excess payment", "refund application", "zero rated refund",
            "refund of igst", "rule 89", "refund claim", "rfd-01",
        ],
        "sections":  ["CGST_SEC_54", "CGST_SEC_55"],
        "rules":     ["CGST_RUL_89", "CGST_RUL_92", "CGST_RUL_96"],
        "circulars": [],
        "expected_cats": {"statute", "circular"},
        "authority_adj": {"circular": 1.3, "statute": 1.1},
    },

    # ── GST Rate / Classification / HSN ───────────────────────────────────
    "gst_rate": {
        "keywords": [
            "rate", "hsn", "sac", "nil rated", "exempt", "exemption",
            "12%", "18%", "28%", "5%", "gst rate", "rate applicable",
            "rate notification", "rate of tax", "taxable value",
            "classification", "hsn code", "tariff heading",
        ],
        "sections":  [],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"notification"},
        "authority_adj": {"notification": 1.6, "statute": 0.8},
    },

    # ── Time of Supply ─────────────────────────────────────────────────────
    "time_of_supply": {
        "keywords": [
            "time of supply", "section 12 cgst", "section 13 cgst",
            "invoice date", "date of payment", "advance", "advance receipt",
            "point of taxation", "continuous supply", "date of completion",
        ],
        "sections":  ["CGST_SEC_12", "CGST_SEC_13"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Supply / Schedule I II III ─────────────────────────────────────────
    "supply": {
        "keywords": [
            "schedule i", "schedule ii", "schedule iii", "deemed supply",
            "without consideration", "gift", "section 7", "definition of supply",
            "composite supply", "mixed supply", "taxable supply",
            "non-taxable supply",
        ],
        "sections":  ["CGST_SEC_7", "CGST_SEC_8"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.3},
    },

    # ── Valuation ──────────────────────────────────────────────────────────
    "valuation": {
        "keywords": [
            "valuation", "transaction value", "rule 27", "rule 28", "rule 29",
            "related party", "open market value", "omv", "second proviso",
            "deemed value", "section 15", "inclusions exclusions",
        ],
        "sections":  ["CGST_SEC_15"],
        "rules":     ["CGST_RUL_27", "CGST_RUL_28", "CGST_RUL_29", "CGST_RUL_30"],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Composition Scheme ─────────────────────────────────────────────────
    "composition": {
        "keywords": [
            "composition", "composition scheme", "section 10",
            "composite dealer", "gstr-4", "composition levy",
            "restaurant", "small trader composition",
        ],
        "sections":  ["CGST_SEC_10"],
        "rules":     ["CGST_RUL_7"],
        "circulars": [],
        "expected_cats": {"statute", "notification"},
        "authority_adj": {"notification": 1.3},
    },

    # ── Annual Return / Reconciliation ────────────────────────────────────
    "annual_return": {
        "keywords": [
            "annual return", "gstr-9", "gstr-9c", "reconciliation",
            "section 44", "self-certified", "turnover reconciliation",
            "itc reconciliation", "form gstr-9",
        ],
        "sections":  ["CGST_SEC_44"],
        "rules":     ["CGST_RUL_80"],
        "circulars": [],
        "expected_cats": {"statute", "circular"},
        "authority_adj": {"circular": 1.2},
    },

    # ── Penalty / Demand / SCN ─────────────────────────────────────────────
    "penalty_demand": {
        "keywords": [
            "penalty", "show cause", "section 73", "section 74",
            "demand notice", "scn", "adjudication", "fraud",
            "wilful misstatement", "section 122", "section 125",
            "interest section 50",
        ],
        "sections":  ["CGST_SEC_73", "CGST_SEC_74", "CGST_SEC_50", "CGST_SEC_122"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Import of Services / OIDAR ─────────────────────────────────────────
    "import_services": {
        "keywords": [
            "import of service", "import of goods", "oidar",
            "online information database", "netflix", "google cloud",
            "aws", "cross border", "non-taxable territory",
        ],
        "sections":  ["IGST_SEC_2", "IGST_SEC_5", "IGST_SEC_14"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute", "notification"},
        "authority_adj": {"notification": 1.3},
    },

    # ── E-Commerce / TCS ──────────────────────────────────────────────────
    "ecommerce": {
        "keywords": [
            "ecommerce", "e-commerce", "tcs", "tax collected at source",
            "section 52", "electronic commerce operator", "eco",
            "swiggy", "zomato", "amazon seller", "online marketplace",
        ],
        "sections":  ["CGST_SEC_52"],
        "rules":     ["CGST_RUL_67"],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Job Work ───────────────────────────────────────────────────────────
    "job_work": {
        "keywords": [
            "job work", "section 143", "principal", "job worker",
            "inputs sent for job work", "capital goods job work",
            "moulds dies jigs", "waste scrap job work",
        ],
        "sections":  ["CGST_SEC_143", "CGST_SEC_19"],
        "rules":     ["CGST_RUL_45"],
        "circulars": [],
        "expected_cats": {"statute", "circular"},
        "authority_adj": {"circular": 1.2},
    },

    # ── TDS under GST ─────────────────────────────────────────────────────
    "tds_gst": {
        "keywords": [
            "tds", "tax deducted at source", "section 51", "gst tds",
            "government department", "deductor", "gstr-7",
            "tds deduction", "tds certificate",
        ],
        "sections":  ["CGST_SEC_51"],
        "rules":     ["CGST_RUL_66"],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── SEZ / Special Economic Zone ────────────────────────────────────────
    "sez": {
        "keywords": [
            "sez", "special economic zone", "sez developer", "sez unit",
            "supply to sez", "supply from sez", "zero rated sez",
            "sez approval", "letter of approval",
        ],
        "sections":  ["IGST_SEC_16"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute", "notification"},
        "authority_adj": {"notification": 1.3},
    },

    # ── Intermediary Services ─────────────────────────────────────────────
    "intermediary": {
        "keywords": [
            "intermediary", "section 2(13) igst", "commission agent",
            "broker", "intermediary services", "facilitation", "marketing",
            "middle man", "place of supply intermediary",
        ],
        "sections":  ["IGST_SEC_2", "IGST_SEC_13"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute"},
        "authority_adj": {"statute": 1.2},
    },

    # ── Real Estate / Affordable Housing ──────────────────────────────────
    "real_estate": {
        "keywords": [
            "real estate", "residential apartment", "affordable housing",
            "under construction", "flat", "developer", "promoter",
            "construction service", "cara", "rrep",
        ],
        "sections":  ["CGST_SEC_7", "CGST_SEC_17"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute", "notification"},
        "authority_adj": {"notification": 1.4, "circular": 1.2},
    },

    # ── Transitional Credits ───────────────────────────────────────────────
    "transitional_credit": {
        "keywords": [
            "transitional credit", "tran-1", "tran-2", "trans credit",
            "section 140", "closing stock", "pre-gst", "pre gst",
            "central excise credit", "vat credit",
        ],
        "sections":  ["CGST_SEC_140"],
        "rules":     ["CGST_RUL_117"],
        "circulars": [],
        "expected_cats": {"statute", "judgment"},
        "authority_adj": {"judgment": 1.3},
    },

    # ── GST Audit ─────────────────────────────────────────────────────────
    "gst_audit": {
        "keywords": [
            "gst audit", "section 65", "section 66", "audit officer",
            "audit report", "gstr-9c", "special audit", "chartered accountant audit",
        ],
        "sections":  ["CGST_SEC_65", "CGST_SEC_66"],
        "rules":     [],
        "circulars": [],
        "expected_cats": {"statute", "circular"},
        "authority_adj": {"circular": 1.2},
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Priority 12 — JSON Registry Merge (Continuous Authority Learning)
# ─────────────────────────────────────────────────────────────────────────────
# Looks for data/authority_registry.json relative to this module's package root.
# If found, its entries are merged INTO GST_GOVERNING_AUTHORITIES so that the
# legal team's edits take effect without code changes.
#
# Merge semantics:
#   • JSON topic key exists in Python dict → JSON values WIN (overrides Python)
#   • JSON topic key is NEW → added to the taxonomy
#   • Within a topic: each list field (sections/rules/circulars/keywords) is
#     merged (union) with the Python base so edits are additive by default.
#   • expected_cats and authority_adj are fully replaced by the JSON version
#     when present.
# ─────────────────────────────────────────────────────────────────────────────

def _load_registry_json() -> dict:
    """
    Resolves the path to data/authority_registry.json relative to the
    project root (two levels above this file's package: app/retrieval/...).
    Returns the parsed JSON or {} on any error.
    """
    try:
        # rag-backend/app/retrieval/authority_taxonomy.py  →  rag-backend/
        _this_dir   = os.path.dirname(os.path.abspath(__file__))
        _pkg_root   = os.path.dirname(os.path.dirname(_this_dir))   # rag-backend/
        _reg_path   = os.path.join(_pkg_root, "data", "authority_registry.json")
        if not os.path.isfile(_reg_path):
            return {}
        with open(_reg_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        # Strip meta key before returning
        raw.pop("_meta", None)
        logger.info(f"Loaded authority_registry.json with {len(raw)} topic entries")
        return raw
    except Exception as exc:
        logger.warning(f"Could not load authority_registry.json: {exc}")
        return {}


def _merge_registry(base: dict, overrides: dict) -> None:
    """
    Merges `overrides` (JSON registry) into `base` (Python taxonomy) in-place.
    List fields are unioned; expected_cats and authority_adj are replaced.
    """
    for topic, jcfg in overrides.items():
        if topic not in base:
            # Brand-new topic — convert expected_cats list → set
            base[topic] = {
                "keywords":      jcfg.get("keywords",      []),
                "sections":      jcfg.get("sections",      []),
                "rules":         jcfg.get("rules",         []),
                "circulars":     jcfg.get("circulars",     []),
                "expected_cats": set(jcfg.get("expected_cats", ["statute"])),
                "authority_adj": jcfg.get("authority_adj", {}),
            }
            logger.debug(f"Registry: added new topic '{topic}'")
        else:
            pcfg = base[topic]
            # Union list fields (preserve ordering, deduplicate)
            for field in ("keywords", "sections", "rules", "circulars"):
                existing = pcfg.get(field, [])
                for item in jcfg.get(field, []):
                    if item not in existing:
                        existing.append(item)
                pcfg[field] = existing
            # Replace set/dict fields when JSON provides them
            if "expected_cats" in jcfg:
                pcfg["expected_cats"] = set(jcfg["expected_cats"])
            if "authority_adj" in jcfg:
                pcfg["authority_adj"] = {
                    cat: max(pcfg.get("authority_adj", {}).get(cat, 1.0), w)
                    for cat, w in jcfg["authority_adj"].items()
                }
            logger.debug(f"Registry: updated topic '{topic}' from JSON")


# Apply overrides at module load — zero runtime cost after this
_registry_overrides = _load_registry_json()
if _registry_overrides:
    _merge_registry(GST_GOVERNING_AUTHORITIES, _registry_overrides)
    logger.info(f"Authority taxonomy now has {len(GST_GOVERNING_AUTHORITIES)} topics after JSON merge")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def classify_query_authority(query: str) -> dict:
    """
    Classifies a query into its governing GST authority taxonomy.

    Returns:
        {
            "topics":         list[str]   — matched taxonomy topics, highest-hit first
            "sections":       list[str]   — provision-index keys to pre-pin
            "rules":          list[str]   — rule provision-index keys to pre-pin
            "circulars":      list[str]   — circular-index keys to pre-pin
            "expected_cats":  set[str]    — document categories required in output
            "authority_adj":  dict        — per-category source_priority multipliers
            "confidence":     int         — keyword hit count for best topic
        }

    Multiple topics are merged additively — a query about "ITC on works
    contract" matches both 'itc' and 'works_contract' and collects all their
    governing authorities into one result.
    """
    q = query.lower()
    matched: list[tuple[int, str, dict]] = []

    for topic, cfg in GST_GOVERNING_AUTHORITIES.items():
        hits = sum(1 for kw in cfg["keywords"] if kw in q)
        if hits > 0:
            matched.append((hits, topic, cfg))

    # Sort by hit count descending; take top 2 to avoid over-pinning
    matched.sort(key=lambda x: -x[0])
    top_matches = matched[:2]

    sections:  list[str] = []
    rules:     list[str] = []
    circulars: list[str] = []
    exp_cats:  set[str]  = {"statute"}
    adj_map:   dict[str, float] = {}

    for _, _, cfg in top_matches:
        for s in cfg.get("sections", []):
            if s not in sections:
                sections.append(s)
        for r in cfg.get("rules", []):
            if r not in rules:
                rules.append(r)
        for c in cfg.get("circulars", []):
            if c not in circulars:
                circulars.append(c)
        exp_cats.update(cfg.get("expected_cats", set()))
        for cat, mult in cfg.get("authority_adj", {}).items():
            # Merge: take the max multiplier when two topics disagree
            adj_map[cat] = max(adj_map.get(cat, 1.0), mult)

    return {
        "topics":        [t for _, t, _ in top_matches],
        "sections":      sections,
        "rules":         rules,
        "circulars":     circulars,
        "expected_cats": exp_cats,
        "authority_adj": adj_map,
        "confidence":    top_matches[0][0] if top_matches else 0,
    }


# ─── Circular filename patterns (mirrors retriever._circular_index logic) ─────
_CIR_NUM_RE = re.compile(
    r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
    r'|cir[-_.](?:cgst[-_.])?'
    r'|cir(?=[0-9])'
    r'|circularno[-_.])'
    r'(\d{2,3})',
    re.IGNORECASE,
)
_CIR_LEADING_RE = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)


def verify_mandatory_coverage(chunks: list, taxonomy: dict) -> dict:
    """
    Verifies that EVERY mandatory authority predicted by the taxonomy is
    actually present in the retrieved chunks.

    This is the difference between:
      "retrieval found relevant chunks"       (probabilistic — what we had before)
      "retrieval verified governing authorities"  (deterministic — what we need)

    For cross-charge: confirms Section 25, Section 20, Rule 28, Rule 39, and
    Circular 199 are each individually confirmed present — not just "a circular".

    Returns:
        {
            "coverage_pct":       int     — 0–100
            "found":              list    — confirmed mandatory authorities
            "missing_sections":   list    — provision keys not found in any chunk
            "missing_rules":      list    — rule keys not found in any chunk
            "missing_circulars":  list    — circular keys not found in any chunk
            "missing":            list    — all missing (sections + rules + circulars)
            "total_mandatory":    int
        }
    """
    mandatory_sections  = taxonomy.get("sections",  [])
    mandatory_rules     = taxonomy.get("rules",     [])
    mandatory_circulars = taxonomy.get("circulars", [])
    total_mandatory = len(mandatory_sections) + len(mandatory_rules) + len(mandatory_circulars)

    if total_mandatory == 0:
        return {
            "coverage_pct": 100,
            "found": [],
            "missing_sections": [],
            "missing_rules": [],
            "missing_circulars": [],
            "missing": [],
            "total_mandatory": 0,
        }

    # ── Collect what's present in retrieved chunks ─────────────────────────
    present_provisions: set[str] = set()
    present_circulars:  set[str] = set()

    for chunk in chunks:
        meta = chunk.get("metadata", {})

        # Provision/citation keys (e.g. CGST_SEC_25, CGST_RUL_28)
        for p in meta.get("provisions", []) + meta.get("citations", []):
            if p:
                present_provisions.add(p)

        # Circular number from filename
        rel  = (chunk.get("rel_path") or meta.get("rel_path", "")).replace("\\", "/")
        fname = rel.split("/")[-1]
        m = _CIR_NUM_RE.search(fname) or _CIR_LEADING_RE.match(fname)
        if m:
            present_circulars.add(f"CIRCULAR_{m.group(1)}")

    # ── Check each mandatory authority ─────────────────────────────────────
    # For sections/rules, check the provision key AND a fallback numeric match.
    # CGST_SEC_25 present if it's in any chunk's provisions OR if any provision
    # key starts with "CGST_SEC_25" / "IGST_SEC_25" (sub-clause variants).
    def _provision_present(key: str) -> bool:
        if key in present_provisions:
            return True
        # Fuzzy: CGST_SEC_25 matches CGST_SEC_25_4, CGST_SEC_25_5 etc.
        prefix = key + "_"
        return any(p.startswith(prefix) for p in present_provisions)

    missing_sections  = [s for s in mandatory_sections  if not _provision_present(s)]
    missing_rules     = [r for r in mandatory_rules     if not _provision_present(r)]
    missing_circulars = [c for c in mandatory_circulars if c not in present_circulars]

    missing = missing_sections + missing_rules + missing_circulars
    found   = (
        [s for s in mandatory_sections  if _provision_present(s)] +
        [r for r in mandatory_rules     if _provision_present(r)] +
        [c for c in mandatory_circulars if c in present_circulars]
    )
    coverage_pct = round(100 * len(found) / total_mandatory) if total_mandatory else 100

    logger.info(
        f"Mandatory coverage: {coverage_pct}% | "
        f"found={found} | missing={missing}"
    )
    return {
        "coverage_pct":      coverage_pct,
        "found":             found,
        "missing_sections":  missing_sections,
        "missing_rules":     missing_rules,
        "missing_circulars": missing_circulars,
        "missing":           missing,
        "total_mandatory":   total_mandatory,
    }


def authority_bonus(rel_path: str, taxonomy_result: dict, base_priority: int) -> float:
    """
    Computes the authority bonus for a chunk given its path and the query taxonomy.

    Instead of a fixed 0.03 per authority point, applies a per-category
    multiplier from the taxonomy so that (for example) notifications get a
    larger bonus for rate queries, and circulars get a larger bonus for
    cross-charge advisory queries.

    base_priority: output of source_priority(rel_path) — 1-5 scale
    """
    adj = taxonomy_result.get("authority_adj", {})
    path = rel_path.lower().replace("\\", "/")

    # Determine the rough category from path
    if any(f in path for f in ("/notification", "/notifications")):
        cat = "notification"
    elif any(f in path for f in ("/circular", "/circulars")):
        cat = "circular"
    elif any(f in path for f in ("high court", "supreme court", "/aar", "other app")):
        cat = "judgment"
    elif any(f in path for f in ("/act", "/cgst", "/igst", "/rules", "/rule")):
        cat = "statute"
    else:
        cat = "other"

    multiplier = adj.get(cat, 1.0)
    return base_priority * 0.03 * multiplier
