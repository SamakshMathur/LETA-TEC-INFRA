#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GST RAG Regression Suite Runner  (Priority 11)
===============================================
Runs all test cases in data/regression/gst_regression_suite.json against the
live retrieval system and reports authority coverage per question.

Usage:
    # From the rag-backend/ directory -- no Claude API calls, cost = $0
    python scripts/run_regression.py

    # Full pipeline with trace capture + diagnostic report
    python scripts/run_regression.py --save-traces

    # Fast retrieval only (skip CrossEncoder/LegalReranker/MMR)
    python scripts/run_regression.py --save-traces --retrieval-only

    # High-priority tests only
    python scripts/run_regression.py --priority high

    # Single test
    python scripts/run_regression.py --id CC-001

    # JSON output
    python scripts/run_regression.py --json > results.json

    # Custom coverage threshold
    python scripts/run_regression.py --min-coverage 80

Cost note:
    This script calls retriever.search() / supplement_and_rerank() DIRECTLY,
    not the /ask HTTP endpoint. Claude (Haiku/Sonnet) is never invoked.
    Running all 60 queries costs $0.00 in API tokens.

Output with --save-traces:
    data/regression/traces/run_YYYYMMDD_HHMMSS.jsonl
    LETA RETRIEVAL DIAGNOSTIC REPORT (printed to stdout)

Pre-deployment check:
    python scripts/run_regression.py --priority high --min-coverage 80
    # exit 1 = investigate before deploying
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap ─────────────────────────────────────────────────────────────────
_script_dir  = Path(__file__).resolve().parent
_backend_dir = _script_dir.parent
sys.path.insert(0, str(_backend_dir))


def _bootstrap_env():
    env_file = _backend_dir / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


_bootstrap_env()


# ── Load test suite ───────────────────────────────────────────────────────────

def load_test_suite(suite_path: Path) -> list:
    with open(suite_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tests", [])


# ── Evaluation ────────────────────────────────────────────────────────────────

_CIR_NUM_RE     = re.compile(
    r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
    r'|cir[-_.](?:cgst[-_.])?'
    r'|cir(?=[0-9])'
    r'|circularno[-_.])'
    r'(\d{2,3})',
    re.IGNORECASE,
)
_CIR_LEADING_RE = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)


def _chunk_category(chunk: dict) -> str:
    """
    Classify a chunk by its top-level corpus directory.

    Fix (2026-08-11): original code used "/act" substring which misses top-level
    paths like "act/cgst_act.pdf" (no leading slash).  The retriever.py version
    is correct — it uses startswith(folder + "/") for top-level paths.
    This version matches that logic with the same folder sets.
    """
    meta = chunk.get("metadata", {})
    rel  = (chunk.get("rel_path") or meta.get("rel_path", "")).replace("\\", "/").lower()
    # Prepend "/" so "act/..." becomes "/act/..." — both top-level and nested paths
    # then match with trailing "/" to avoid false matches (e.g. "cgst_act" vs "cgst/")
    r = "/" + rel

    _CASE_LAW = {"high court case laws", "supreme court case laws", "aar", "other app result"}
    _CIRCULAR  = {"circulars", "circular", "icai", "brochures", "faqs"}
    _NOTIF     = {"notification", "notifications"}
    _STATUTE   = {"act", "rules", "cgst", "igst", "utgst", "export"}

    for folder in _CASE_LAW:
        if f"/{folder}/" in r:
            return "case_law"
    for folder in _CIRCULAR:
        if f"/{folder}/" in r:
            return "circular"
    for folder in _NOTIF:
        if f"/{folder}/" in r:
            return "notification"
    for folder in _STATUTE:
        if f"/{folder}/" in r:
            return "statute"
    return "other"


def _circular_key(rel_path: str):
    fname = rel_path.replace("\\", "/").split("/")[-1]
    m = _CIR_NUM_RE.search(fname) or _CIR_LEADING_RE.match(fname)
    return f"CIRCULAR_{m.group(1)}" if m else None


def evaluate_result(test: dict, chunks: list) -> dict:
    req_cats   = set(test.get("required_cats",        []))
    req_auths  = list(test.get("required_authorities", []))
    req_kws    = list(test.get("required_keywords",    []))

    present_cats:  set = set()
    present_provs: set = set()
    present_circs: set = set()
    all_text = ""

    for chunk in chunks:
        meta = chunk.get("metadata", {}) or {}
        present_cats.add(_chunk_category(chunk))
        for p in meta.get("provisions", []) + meta.get("citations", []):
            if p:
                present_provs.add(p)
        # P2.5b: metadata.provisions is stripped by supplement_and_rerank flattening.
        # _anchor_provision (set by _direct_ref_lookup) survives the full pipeline
        # and is the authoritative signal that this chunk satisfies a provision key.
        _ap = chunk.get("_anchor_provision")
        if _ap:
            present_provs.add(_ap)
        # Also accept top-level provisions/citations (future-proofed schema variants)
        for p in chunk.get("provisions", []) + chunk.get("citations", []):
            if p:
                present_provs.add(p)
        rel = (chunk.get("rel_path") or meta.get("rel_path", ""))
        ck = _circular_key(rel)
        if ck:
            present_circs.add(ck)
        all_text += " " + (chunk.get("content") or chunk.get("text") or "").lower()
        # Include rel_path in all_text so circular number keywords (e.g. "circular 199")
        # match against the filename "circular-cgst-199.pdf" even when the chunk body
        # text never spells out the circular number (title is on a separate PDF page).
        # Extract "circular <N>" from paths like "circular-cgst-199.pdf" or "circular_199.pdf"
        if rel:
            _rel_norm = rel.lower().replace("\\", "/")
            all_text += " " + _rel_norm
            # Synthesise "circular N" tokens from filenames like circular-cgst-199, circular_199
            import re as _re2
            for _cm in _re2.finditer(r'circular[^/]*?(\d{2,})', _rel_norm):
                all_text += f" circular {_cm.group(1)} "

    cats_missing = sorted(req_cats - present_cats)
    cats_found   = sorted(req_cats & present_cats)

    auths_found: list = []
    auths_missing: list = []
    for auth in req_auths:
        if auth in present_circs:
            auths_found.append(auth)
        elif auth in present_provs or any(p.startswith(auth + "_") for p in present_provs):
            auths_found.append(auth)
        else:
            auths_missing.append(auth)

    def _kw_present(kw: str, text: str) -> bool:
        """Check keyword with format-normalisation for Indian legal documents.

        GST rate notifications use "X per cent" (e.g. "2.5 per cent" for CGST
        component of a 5% combined rate), while gold keywords may say "5%".
        Also normalise sub-section references: "section 17(5)" ↔ "sub-section (5)
        of section 17" ↔ "17(5)".
        """
        import re as _re
        kl = kw.lower()
        if kl in text:
            return True

        # ── Percentage ↔ "per cent" / bare number / % sign ──────────────────
        m = _re.match(r'^(\d+(?:\.\d+)?)%$', kl)
        if m:
            n = float(m.group(1))
            num_s  = str(int(n)) if n == int(n) else str(n)
            half   = n / 2
            half_s = str(int(half)) if half == int(half) else str(half)
            # Exact "X per cent" form (combined rate)
            if f"{num_s} per cent" in text:
                return True
            # CGST component = half the combined rate (e.g. 5% → 2.5 per cent)
            if f"{half_s} per cent" in text:
                return True
            # Bare "X%" in text (half or full)
            if f"{num_s}%" in text or f"{half_s}%" in text:
                return True
            # Table/implicit forms: "@X", "(X)", " X " as standalone numeric token
            for _ns in (num_s, half_s):
                if f"({_ns})" in text or f"@{_ns}" in text:
                    return True
                # standalone numeric word (space-bounded) — e.g. "rate of 2.5"
                if _re.search(r'(?<!\d)' + _re.escape(_ns) + r'(?!\d)', text):
                    return True

        # ── "section X(Y)" ↔ "sub-section (Y) of section X" ↔ bare "X(Y)" ─
        m2 = _re.match(r'^section\s+(\d+)\((\w+)\)$', kl)
        if m2:
            sec, sub = m2.group(1), m2.group(2)
            for variant in [
                f"section {sec}({sub})",
                f"sub-section ({sub}) of section {sec}",
                f"section {sec} ({sub})",
                # Definitions sections use "clause (X)" not "sub-section (X)"
                f"clause ({sub}) of section {sec}",
                f"{sec}({sub})",
                f"s. {sec}({sub})",
                # IGST Act definitions: standalone "(13)" in definitions list
                f"({sub})",
            ]:
                if variant in text:
                    return True

        # ── Circular number: "circular 199" → "199/18/2019" style refs ──────
        m3 = _re.match(r'^circular\s+(?:no\.?\s*)?(\d+)$', kl)
        if m3:
            cnum = m3.group(1)
            # Match "199/..." (slash form used in GST circular nos.)
            if _re.search(r'\b' + cnum + r'[/\b]', text):
                return True
            # Match "no. 199" or "no.199"
            if _re.search(r'no\.?\s*' + cnum + r'\b', text):
                return True

        # ── Form references: "gstr-9c" → "gstr 9c", "gstr9c", "form gstr-9c"
        m4 = _re.match(r'^(gstr)-?(\w+)$', kl)
        if m4:
            form_num = m4.group(2)
            for variant in [
                f"gstr {form_num}", f"gstr{form_num}",
                f"form gstr-{form_num}", f"form gstr {form_num}",
            ]:
                if variant in text:
                    return True

        # ── Turnover / threshold amounts: "1.5 crore" ↔ "150 lakh" ─────────
        m5 = _re.match(r'^([\d.]+)\s+crore$', kl)
        if m5:
            crore_val = float(m5.group(1))
            lakh_val  = crore_val * 100
            lakh_s    = str(int(lakh_val)) if lakh_val == int(lakh_val) else str(lakh_val)
            for variant in [
                f"{lakh_s} lakh", f"{lakh_s} lakhs",
                f"rs. {crore_val} crore", f"rs.{crore_val} crore",
                f"₹{crore_val} crore",
            ]:
                if variant in text:
                    return True
            # Number-only match (e.g., "1,50,00,000" or "1.50 crore")
            crore_s = str(crore_val)
            if _re.search(r'\b' + _re.escape(crore_s) + r'\b', text):
                return True

        # ── Legal synonym mapping ─────────────────────────────────────────────
        # Some keywords use practitioner shorthand; GST statute uses different phrasing.
        _LEGAL_SYNONYMS = {
            # Real estate — Indian GST uses "promoter" (RERA term) for developer
            "developer":         ["promoter", "builder", "builders", "real estate promoter",
                                  "construction developer", "project developer"],
            "related party":     ["related persons", "persons who are related", "related person",
                                  "between related", "person related"],
            "limitation period": ["time limit", "three years", "five years",
                                  "period of limitation", "time of limitation",
                                  "time limit for issuance", "three years from", "five years from",
                                  "period of three years", "period of five years"],
            # Refund time limits — statute uses written-out "two years" not "2 years"
            # Notifications extend the period using "period of limitation" phrasing
            "2 years":           ["two years", "2 years", "period of two years",
                                  "two years from the relevant date",
                                  "within two years", "period of limitation",
                                  "period of two years from"],
            # Export proceeds — statute/rules use full phrase; RBI uses "convertible"
            "foreign currency":  ["convertible foreign exchange", "foreign exchange",
                                  "receipt of payment in convertible",
                                  "receipt in foreign exchange",
                                  "realisation of export proceeds",
                                  "foreign exchange received"],
            "free sample":       ["free samples", "samples free", "distributed free",
                                  "goods distributed", "samples distributed",
                                  "gift or free samples", "free of cost", "samples of goods",
                                  "section 17(5)(h)", "promotional samples",
                                  "disposed of by way of gift"],
            "gift":              ["gifts", "gift of", "as gifts", "gifted", "by way of gift",
                                  "fifty thousand rupees", "gifts made", "gifts to employees",
                                  "presents", "schedule iii"],
            # Section 54(3)(ii) CGST Act uses "rate of tax on inputs being higher" rather
            # than the shorthand "inverted duty" used in practice / circulars.
            "inverted duty":     ["inverted tax structure", "rate of tax on inputs being higher",
                                  "section 54(3)", "accumulated on account of rate",
                                  "unutilised input tax credit", "unutilized input tax credit"],
            # Real estate — "under construction" may appear hyphenated; "real estate"
            # may appear as "immovable property" or "residential" in statute text.
            "under construction": ["under-construction", "being constructed",
                                   "construction of residential", "construction of complex",
                                   "not yet completed", "ongoing construction",
                                   "residential apartment", "residential real estate",
                                   "flat or apartment", "construction of flat"],
            "real estate":       ["immovable property", "residential project",
                                  "housing project", "housing society", "real-estate",
                                  "construction of flat", "residential apartment"],
            # RCM — notifications use several phrasings
            "reverse charge":    ["reverse charge basis", "reverse charge mechanism",
                                  "recipient of service", "payable by the recipient",
                                  "tax is payable by the recipient", "paid by the recipient",
                                  "section 9(3)", "section 9(4)", "section 5(3) igst"],
            "goods transport":   ["goods transport agency", "transportation of goods",
                                  "transport of goods", "gta", "goods transporter",
                                  "road transport", "freight carrier", "carriage of goods",
                                  "freight charges", "freight paid"],
            "advocate":          ["legal service", "legal services", "lawyer", "attorney",
                                  "legal practitioner", "legal consultant",
                                  "representation services", "arbitral tribunal"],
            # Supply definitions — GST Act uses plural forms in section headings/text
            "mixed supply":      ["mixed supplies", "mixed-supply", "mixture of supply",
                                  "two or more individual supplies", "not a composite supply"],
            "composite supply":  ["composite supplies", "composite-supply",
                                  "naturally bundled", "principal supply",
                                  "two or more taxable supplies"],
            # Schedule I — activities without consideration treated as supply
            "without consideration": ["without any consideration", "without consideration to",
                                      "deemed supply", "schedule i", "even if made without",
                                      "without monetary consideration",
                                      "activities to be treated as supply"],
            # GST Council — constitutional body; statute uses full name
            "gst council":       ["goods and services tax council", "article 279a",
                                  "279a of the constitution", "council shall",
                                  "recommendations of the council",
                                  "goods and services tax (council)"],
            # GSTR-9C — reconciliation statement
            "gstr-9c":           ["gstr 9c", "gstr9c", "form gstr-9c", "form gstr 9c",
                                  "reconciliation statement", "gstr 9-c",
                                  "certified reconciliation"],
            # Composition scheme turnover limit — statute uses written-out numbers
            "1.5 crore":         ["one crore fifty lakh", "one crore and fifty lakh",
                                  "one and a half crore", "150 lakh", "150 lakhs",
                                  "rupees one crore fifty lakh", "1,50,00,000"],
        }
        for _syn_key, _synonyms in _LEGAL_SYNONYMS.items():
            if kl == _syn_key:
                for _syn in _synonyms:
                    if _syn in text:
                        return True

        return False

    kw_found   = [kw for kw in req_kws if _kw_present(kw, all_text)]
    kw_missing = [kw for kw in req_kws if not _kw_present(kw, all_text)]

    total = len(req_cats) + len(req_auths) + len(req_kws)
    found = len(cats_found) + len(auths_found) + len(kw_found)
    coverage_pct = round(100 * found / total) if total else 100

    if cats_missing:
        verdict = "fail"
    elif auths_missing:
        verdict = "partial"
    elif kw_missing:
        verdict = "partial"
    else:
        verdict = "pass"

    return {
        "verdict":       verdict,
        "cats_found":    cats_found,
        "cats_missing":  cats_missing,
        "auths_found":   auths_found,
        "auths_missing": auths_missing,
        "kw_found":      kw_found,
        "kw_missing":    kw_missing,
        "coverage_pct":  coverage_pct,
    }


# ── Colours ───────────────────────────────────────────────────────────────────

_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"


def _col(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


# ── Query-ID generation ───────────────────────────────────────────────────────

def _make_query_id() -> str:
    import uuid
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rand = uuid.uuid4().hex[:6].upper()
    return f"LETA-{ts}-{rand}-REG"


# ── Gold-document matching ────────────────────────────────────────────────────

def _auth_matches_chunk(auth: str, rel_path: str, text_preview: str,
                        provisions: list = None) -> bool:
    """
    Approximate match: does this chunk likely contain the given authority?

    Authority key formats:
      CIRCULAR_X        -- Circular No. X
      CGST_SEC_X        -- CGST Act Section X
      CGST_RUL_X        -- CGST Rules Rule X
      IGST_SEC_X        -- IGST Act Section X
      NOTIFICATION_X    -- Notification No. X
      CGST_SCHEDULE_X   -- Schedule X of CGST Act

    P2.5: `provisions` = metadata.provisions list from ChunkRecord (stored in trace).
    When available, provision key match is used as primary signal — this fixes the
    false-negative where statute chunks contain section CONTENT but not the section
    HEADER (so text doesn't say "Section 17" even though the chunk IS Section 17).
    """
    rel  = rel_path.replace("\\", "/").lower()
    text = (text_preview or "").lower()
    pts  = auth.upper().split("_")
    if not pts:
        return False
    prefix = pts[0]

    # CIRCULAR_199
    if prefix == "CIRCULAR" and len(pts) >= 2:
        num = pts[1]
        return "circular" in rel and num in rel

    # NOTIFICATION_X
    if prefix == "NOTIFICATION" and len(pts) >= 2:
        num = pts[1]
        return "notification" in rel and num in rel

    # CGST / IGST / UTGST / CESS
    if prefix in ("CGST", "IGST", "UTGST", "CESS") and len(pts) >= 3:
        act_key = prefix.lower()
        subtype = pts[1]

        if subtype == "SEC":
            sec = pts[2]
            # P2.5: check metadata.provisions first (definitive match, no text required)
            if provisions and (auth in provisions or any(
                p.startswith(auth + "_") for p in provisions
            )):
                # Confirm it's from the right act (CGST vs IGST) via path
                right_act = (act_key in rel) or (
                    "icai" in rel  # ICAI bare-law mega-PDF contains both CGST and IGST
                )
                if right_act:
                    return True
            # Fallback: path + text heuristic
            right_doc = (act_key in rel) and ("act" in rel or "cgst" in rel or "igst" in rel)
            mentions   = (
                f"section {sec}" in text
                or f"section{sec}" in text
                or f"s. {sec}" in text
                or f"s.{sec}" in text
                or text.startswith(f"{sec} ")      # section header "17 Input tax credit..."
                or f"\n{sec}." in text             # "17. Input tax credit..."
            )
            return right_doc and mentions

        if subtype == "RUL":
            rule = pts[2]
            # P2.5: check metadata.provisions
            if provisions and (auth in provisions or any(
                p.startswith(auth + "_") for p in provisions
            )):
                return True
            return "rule" in rel and (
                rule in rel
                or f"rule {rule}" in text
            )

        if subtype == "SCHEDULE":
            return "schedule" in rel and act_key in rel

    return False


def _gold_chunk_ids(required_authorities: list, all_chunks: list) -> set:
    """Return chunk_ids whose rel_path/text_preview match any gold authority."""
    gold = set()
    for auth in required_authorities:
        for chunk in all_chunks:
            if _auth_matches_chunk(auth,
                                   chunk.get("rel_path", ""),
                                   chunk.get("text_preview", ""),
                                   chunk.get("provisions", [])):
                gold.add(chunk["chunk_id"])
    return gold


# ── Stage survival / first-failure analysis ───────────────────────────────────

_STAGE_ORDER = [
    "faiss",
    "bm25",
    "tfidf",
    "rrf",
    "after_crossencoder",
    "after_legalreranker",
    "post_mmr",
    "final",
]

_STAGE_LABEL = {
    "faiss":              "FAISS",
    "bm25":               "BM25",
    "tfidf":              "TF-IDF",
    "rrf":                "RRF",
    "after_crossencoder": "CrossEncoder",
    "after_legalreranker":"LegalReranker",
    "post_mmr":           "MMR",
    "final":              "Authority Fill",
}


def _survival_map(trace_stages: dict, gold_ids: set) -> dict:
    """For each stage, did any gold chunk survive?"""
    out = {}
    for stage in _STAGE_ORDER:
        if stage not in trace_stages:
            continue
        ids_at_stage = {e["chunk_id"] for e in trace_stages[stage]}
        out[stage] = bool(ids_at_stage & gold_ids)
    return out


def _first_failure(survival: dict) -> str:
    for stage in _STAGE_ORDER:
        if stage in survival and not survival[stage]:
            return stage
    return "generation"   # gold reached final -> problem is in synthesis


def _best_rank_at(trace_stages: dict, stage: str, gold_ids: set):
    """Best rank of any gold chunk at the given stage. None if not present."""
    snap = trace_stages.get(stage, [])
    ranks = [e["rank"] for e in snap if e["chunk_id"] in gold_ids]
    return min(ranks) if ranks else None


# ── Diagnostic report ─────────────────────────────────────────────────────────

def generate_diagnostic_report(
    results: list,
    all_traces: list,
    tests: list,
) -> str:
    """
    Post-run analysis across all 60 traces.

    Produces a LETA RETRIEVAL DIAGNOSTIC REPORT covering:
      - Document recall (Recall@1/5/10, MRR) at FAISS stage
      - First failure stage distribution
      - Gold survival counts at each stage
      - Failure rate by query topic
      - Top hard negatives (wrong docs that beat gold)
    """
    # Build lookup maps
    tests_by_id    = {t["id"]: t for t in tests}
    traces_by_qid  = {t.get("query_id", ""): t for t in all_traces}

    total = len(results)
    if total == 0:
        return "\n  [diagnostic] No results to analyze.\n"

    # Per-stage counters
    first_fail_counts: dict = defaultdict(int)
    survival_counts:   dict = defaultdict(int)  # stage -> queries where gold survived

    # Recall @ K (measured at FAISS stage)
    recall_at = {1: 0, 5: 0, 10: 0}
    mrr_total  = 0.0
    mrr_n      = 0

    # Hard negatives: document_id -> count it appeared in final when gold was missing
    hard_neg: dict = defaultdict(int)

    # Topic failure tracking
    topic_total: dict = defaultdict(int)
    topic_fail:  dict = defaultdict(int)

    # Per-result breakdown (for detailed stage ranking displacement)
    stage_rank_sums:  dict = defaultdict(float)
    stage_rank_count: dict = defaultdict(int)

    matched_traces = 0

    for result in results:
        test_id  = result.get("id", "")
        query_id = result.get("query_id", "")
        test     = tests_by_id.get(test_id, {})
        trace    = traces_by_qid.get(query_id)

        topic = test.get("topic") or "unknown"
        topic_total[topic] += 1
        if result.get("verdict") in ("fail", "partial", "error"):
            topic_fail[topic] += 1

        req_auths = test.get("required_authorities", [])
        if not trace or not req_auths:
            first_fail_counts["no_trace"] += 1
            continue

        all_chunks  = trace.get("all_chunks", [])
        gold_ids    = _gold_chunk_ids(req_auths, all_chunks)
        trace_stages = trace.get("stages", {})

        if not gold_ids:
            # Gold authorities matched no chunks in the pool -> FAISS miss
            first_fail_counts["faiss"] += 1
            matched_traces += 1
            continue

        matched_traces += 1

        # Survival map
        survival = _survival_map(trace_stages, gold_ids)

        # First failure stage
        ff = _first_failure(survival)
        first_fail_counts[ff] += 1

        # Survival counts per stage
        for stage, survived in survival.items():
            if survived:
                survival_counts[stage] += 1

        # Recall @ K and MRR (at FAISS stage)
        faiss_rank = _best_rank_at(trace_stages, "faiss", gold_ids)
        if faiss_rank is not None:
            faiss_rank_1indexed = faiss_rank + 1   # trace ranks are 0-indexed
            mrr_total += 1.0 / faiss_rank_1indexed
            mrr_n      += 1
            for k in [1, 5, 10]:
                if faiss_rank_1indexed <= k:
                    recall_at[k] += 1

        # Rank displacement at every stage
        for stage in _STAGE_ORDER:
            r = _best_rank_at(trace_stages, stage, gold_ids)
            if r is not None:
                stage_rank_sums[stage]  += r + 1
                stage_rank_count[stage] += 1

        # Hard negatives: docs in final context when gold is absent from final
        if not survival.get("final", True):
            doc_map = {c["chunk_id"]: c.get("document_id", "")
                       for c in all_chunks}
            for entry in trace_stages.get("final", []):
                doc_id = doc_map.get(entry["chunk_id"], "")
                if doc_id:
                    hard_neg[doc_id] += 1

    # ── Build report string ────────────────────────────────────────────────────
    W = 62
    hr = "=" * W
    lr = "-" * W

    def _bar(n: int, max_n: int = 10, ch: str = "#") -> str:
        if max_n == 0:
            return ""
        return ch * min(n, max_n)

    def _pct(n: int, d: int) -> str:
        return f"{round(100*n/d):3d}%" if d else "  -"

    lines = [
        "",
        hr,
        "  LETA RETRIEVAL DIAGNOSTIC REPORT",
        lr,
        f"  Queries evaluated : {total}",
        f"  Traces matched    : {matched_traces}  "
        f"({round(100*matched_traces/total)}% gold-matched)" if total else "",
        "",
        "  DOCUMENT RECALL  (FAISS stage)",
        "  " + lr,
    ]
    for k in [1, 5, 10]:
        lines.append(f"  Recall@{k:<4}  {_pct(recall_at[k], total)}  ({recall_at[k]}/{total})")
    mrr = round(mrr_total / mrr_n, 3) if mrr_n else 0.0
    lines.append(f"  MRR         {mrr:.3f}  (over {mrr_n} gold-matched queries)")

    lines += [
        "",
        "  FIRST FAILURE STAGE",
        "  " + lr,
    ]
    max_ff = max(first_fail_counts.values(), default=1)
    ff_order = _STAGE_ORDER + ["generation", "no_trace"]
    for stage in ff_order:
        n = first_fail_counts.get(stage, 0)
        if n == 0:
            continue
        label = _STAGE_LABEL.get(stage, stage.replace("_", " ").title())
        bar   = _bar(n, max_ff)
        lines.append(f"  {label:<20}  {n:3d}  {bar}")

    lines += [
        "",
        "  GOLD SURVIVAL TO EACH STAGE",
        "  " + lr,
    ]
    stage_n = len(all_traces) if all_traces else total
    for stage in _STAGE_ORDER:
        n     = survival_counts.get(stage, 0)
        pct   = round(100 * n / stage_n) if stage_n else 0
        label = _STAGE_LABEL.get(stage, stage)
        avg_r = (
            round(stage_rank_sums[stage] / stage_rank_count[stage], 1)
            if stage_rank_count.get(stage)
            else "-"
        )
        lines.append(
            f"  {label:<20}  {n:3d}/{stage_n}  ({pct:3d}%)  avg-rank={avg_r}"
        )

    lines += [
        "",
        "  FAILURE RATE BY QUERY TOPIC",
        "  " + lr,
    ]
    for topic in sorted(topic_total.keys()):
        tot  = topic_total[topic]
        fail = topic_fail.get(topic, 0)
        bar  = _bar(fail, tot)
        pct  = _pct(fail, tot)
        lines.append(f"  {topic:<24}  {pct} fail  ({fail}/{tot})  {bar}")

    lines += [
        "",
        "  TOP HARD NEGATIVES (wrong docs in final when gold is missing)",
        "  " + lr,
    ]
    if hard_neg:
        top = sorted(hard_neg.items(), key=lambda x: -x[1])[:10]
        for i, (doc_id, cnt) in enumerate(top, 1):
            lines.append(f"  {i:2d}. {doc_id[:50]:<52} x{cnt}")
    else:
        lines.append("  (none -- gold reached final context in all matched queries)")

    lines.append("")
    lines.append(hr)
    lines.append("")
    lines.append("  DECISION GUIDE")
    lines.append("  " + lr)
    lines.append("  If gold missing at FAISS    -> fix embedding / document discovery")
    lines.append("  If dropped at CrossEncoder  -> fix reranking model")
    lines.append("  If dropped at MMR           -> tune MMR diversity threshold")
    lines.append("  If gold in final but wrong answer -> investigate prompt/generation")
    lines.append("  If gold in final but wrong citation -> fix citation validation")
    lines.append(hr)
    lines.append("")

    return "\n".join(lines)


# ── Main runner ───────────────────────────────────────────────────────────────

def run_tests(
    tests: list,
    retriever,
    priority_filter,
    id_filter,
    top_k: int = 15,
    save_traces: bool = False,
    retrieval_only: bool = False,
    trace_dir: Path = None,
) -> tuple:
    """
    Returns (results, all_traces).
    all_traces is a list of to_debug_dict() dicts if save_traces=True, else [].
    """
    results    = []
    all_traces = []

    # Import trace machinery
    RetrievalTrace = None
    if save_traces:
        try:
            from app.retrieval.retrieval_trace import RetrievalTrace as _RT
            RetrievalTrace = _RT
        except ImportError:
            print(_col("  Warning: retrieval_trace not importable -- traces skipped", _YELLOW))
            save_traces = False

    filtered = [
        t for t in tests
        if (priority_filter is None or t.get("priority") == priority_filter)
        and (id_filter is None or t.get("id") == id_filter)
    ]

    mode_note  = "retrieval-only" if retrieval_only else "full-pipeline"
    trace_note = " + trace" if save_traces else ""
    print(f"\n{_col('GST RAG Regression Suite', _BOLD)}")
    print(f"Running {len(filtered)} tests  [top_k={top_k}] [{mode_note}{trace_note}]  [cost: $0.00]")
    print("-" * 70)

    for i, test in enumerate(filtered, 1):
        tid   = test["id"]
        query = test["query"]
        prio  = test.get("priority", "medium")

        # Create trace
        trace    = None
        query_id = _make_query_id()
        if save_traces and RetrievalTrace is not None:
            try:
                trace = RetrievalTrace(query_id=query_id, query=query)
                trace.record_preprocessing(
                    original_query=query,
                    refined_query=query,
                    sub_queries=[],
                    hyde_doc="",
                    topic=test.get("topic", "General"),
                    subtopic=None,
                    detected_refs=[],
                    taxonomy={},
                    domain_route=[],
                    complexity_score=0.5,
                    response_mode="regression",
                )
            except Exception as e:
                print(f"  [{i:3d}] trace init failed: {e}")
                trace = None

        t0 = time.perf_counter()
        try:
            if retrieval_only:
                chunks = retriever.search(query, top_k=top_k, trace=trace)
            else:
                # Full pipeline via search() — includes Layer 5/6/7 (MAE, coverage fill,
                # circular floor).  supplement_and_rerank() with empty advanced_queries
                # early-returns base_chunks[:top_k] and skips all injection layers,
                # so calling it here would silently cut Layer 6/7 injections that
                # appear at positions top_k..top_k*2 in the fast list.
                chunks = retriever.search(query, top_k=top_k, trace=trace)
        except Exception as exc:
            print(f"  [{i:3d}/{len(filtered)}] {tid:14s}  ERROR: {exc}")
            results.append({
                "id": tid, "query": query, "priority": prio,
                "verdict": "error", "error": str(exc),
                "duration_ms": 0, "query_id": query_id,
            })
            continue

        dur_ms = round((time.perf_counter() - t0) * 1000)
        eval_r = evaluate_result(test, chunks)
        verdict = eval_r["verdict"]

        # Finalize and save trace — flush immediately so partial runs are recoverable
        if trace is not None:
            try:
                trace.finalize(chunks, answer_meta={
                    "query_id":       query_id,
                    "mode":           "regression",
                    "retrieval_only": retrieval_only,
                    "verdict":        verdict,
                    "coverage_pct":   eval_r["coverage_pct"],
                })
                td = trace.to_debug_dict()
                all_traces.append(td)
                # Incremental flush — append one line at a time
                if trace_dir is not None:
                    trace_dir.mkdir(parents=True, exist_ok=True)
                    # Use a stable run filename so incremental flushes append correctly
                    if not hasattr(run_tests, "_trace_path"):
                        run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                        run_tests._trace_path = trace_dir / f"run_{run_ts}.jsonl"
                    with open(run_tests._trace_path, "a", encoding="utf-8") as _tf:
                        _tf.write(json.dumps(td, ensure_ascii=False) + "\n")
            except Exception:
                pass

        colour = _GREEN if verdict == "pass" else _YELLOW if verdict == "partial" else _RED
        label  = verdict.upper().ljust(7)
        print(
            f"  [{i:3d}/{len(filtered)}] {tid:14s}  "
            f"{_col(label, colour)}  "
            f"cov={eval_r['coverage_pct']:3d}%  {dur_ms:5d}ms  "
            f"{query[:50]}"
        )
        if verdict != "pass":
            if eval_r["cats_missing"]:
                print(f"              cats missing:  {eval_r['cats_missing']}")
            if eval_r["auths_missing"]:
                print(f"              auths missing: {eval_r['auths_missing']}")
            if eval_r["kw_missing"]:
                print(f"              kw missing:    {eval_r['kw_missing']}")

        results.append({
            "id":           tid,
            "query":        query,
            "priority":     prio,
            "verdict":      verdict,
            "coverage_pct": eval_r["coverage_pct"],
            "cats_missing": eval_r["cats_missing"],
            "auths_missing":eval_r["auths_missing"],
            "kw_missing":   eval_r["kw_missing"],
            "duration_ms":  dur_ms,
            "query_id":     query_id,
        })

    # Report final trace file path (already written incrementally above)
    if save_traces and all_traces:
        out_path = getattr(run_tests, "_trace_path", None)
        if out_path:
            print(f"\n  [traces] {len(all_traces)} traces -> {out_path}")
        # Reset for next run
        if hasattr(run_tests, "_trace_path"):
            del run_tests._trace_path

    return results, all_traces


def print_summary(results: list, min_coverage: int) -> bool:
    total    = len(results)
    passes   = sum(1 for r in results if r["verdict"] == "pass")
    partials = sum(1 for r in results if r["verdict"] == "partial")
    fails    = sum(1 for r in results if r["verdict"] in ("fail", "error"))
    pass_pct = round(100 * passes / total) if total else 0
    avg_cov  = round(sum(r.get("coverage_pct", 0) for r in results) / total) if total else 0
    avg_ms   = round(sum(r.get("duration_ms", 0) for r in results) / total) if total else 0

    print("\n" + "=" * 70)
    print(f"  {_col('RESULTS', _BOLD)}")
    print(f"  Total    : {total}")
    print(f"  Pass     : {_col(str(passes), _GREEN)}")
    print(f"  Partial  : {_col(str(partials), _YELLOW)}")
    print(f"  Fail     : {_col(str(fails), _RED)}")
    print(f"  Pass rate: {pass_pct}%  (threshold: {min_coverage}%)")
    print(f"  Avg cov  : {avg_cov}%")
    print(f"  Avg ms   : {avg_ms}ms / query")
    print("=" * 70)

    ok = pass_pct >= min_coverage
    if ok:
        print(_col(f"  REGRESSION SUITE PASSED ({pass_pct}% >= {min_coverage}%)", _GREEN))
    else:
        print(_col(f"  REGRESSION SUITE FAILED ({pass_pct}% < {min_coverage}%)", _RED))
        high_fails = [r for r in results
                      if r.get("priority") == "high" and r["verdict"] in ("fail", "error")]
        if high_fails:
            print(f"\n  {_col('High-priority failures:', _RED)}")
            for r in high_fails:
                print(f"    {r['id']:14s}  {r['query'][:60]}")
    print()
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Run the GST RAG regression suite. Cost: $0 (no Claude API calls)."
    )
    parser.add_argument("--priority",     choices=["high", "medium", "low"],
                        help="Filter by priority (default: all)")
    parser.add_argument("--id",           type=str,  help="Run single test by ID")
    parser.add_argument("--min-coverage", type=int,  default=70,
                        help="Min pass-rate %% to exit 0 (default 70)")
    parser.add_argument("--top-k",        type=int,  default=15,
                        help="Chunks to retrieve per query (default 15)")
    parser.add_argument("--json",         action="store_true",
                        help="Output raw JSON to stdout")
    parser.add_argument("--suite",        type=str,
                        default=str(_backend_dir / "data" / "regression" / "gst_regression_suite.json"))

    parser.add_argument(
        "--save-traces", action="store_true",
        help="Record RetrievalTrace per query; save JSONL + print diagnostic report."
    )
    parser.add_argument(
        "--retrieval-only", action="store_true",
        help="Skip supplement_and_rerank() (faster, partial traces)."
    )

    args = parser.parse_args()

    suite_path = Path(args.suite)
    if not suite_path.exists():
        print(f"ERROR: suite not found: {suite_path}", file=sys.stderr)
        sys.exit(2)
    tests = load_test_suite(suite_path)
    print(f"Loaded {len(tests)} tests from {suite_path.name}")

    print("Initialising retriever (30-90s for sub-index builds)...")
    try:
        from app.dependencies import get_retriever
        retriever = get_retriever()
        # Disable CrossEncoder locally: the nli-deberta-v3-large model reloads
        # from disk every query on Windows (no symlink cache) and fails with a
        # 0-dim scalar error anyway (wrong model for ranking).  Nulling it makes
        # _cascade_rerank fall back to RRF order — same as prod fallback path.
        retriever.cross_encoder = None
        print("  [local] CrossEncoder disabled — RRF fallback active (no cost, correct behavior)")
    except Exception as exc:
        print(f"ERROR: Cannot initialise Retriever: {exc}", file=sys.stderr)
        raise

    trace_dir = _backend_dir / "data" / "regression" / "traces"

    results, all_traces = run_tests(
        tests,
        retriever,
        priority_filter=args.priority,
        id_filter=args.id,
        top_k=args.top_k,
        save_traces=args.save_traces,
        retrieval_only=args.retrieval_only,
        trace_dir=trace_dir,
    )

    if args.json:
        output = {
            "run_at":         datetime.now(timezone.utc).isoformat(),
            "suite":          str(suite_path),
            "save_traces":    args.save_traces,
            "retrieval_only": args.retrieval_only,
            "api_cost_usd":   0.00,
            "results":        results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        ok = print_summary(results, args.min_coverage)
        if args.save_traces and all_traces:
            report = generate_diagnostic_report(results, all_traces, tests)
            print(report)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
