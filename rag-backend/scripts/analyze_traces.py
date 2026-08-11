#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LETA Trace Analyzer  (P1 diagnostic tool)
==========================================
Reads a saved JSONL trace file (from run_regression.py --save-traces)
and generates the full LETA Retrieval Diagnostic Report.

Usage:
    # Most recent trace file
    python scripts/analyze_traces.py

    # Specific file
    python scripts/analyze_traces.py --file data/regression/traces/run_20260810_184512.jsonl

    # With a different test suite
    python scripts/analyze_traces.py --suite data/regression/gst_regression_suite.json

    # Dump per-query breakdown
    python scripts/analyze_traces.py --per-query

    # Show ranking displacement table (gold rank at every stage)
    python scripts/analyze_traces.py --rank-table

    # Dump hard negatives with full doc paths
    python scripts/analyze_traces.py --hard-negatives

    # Write report to file
    python scripts/analyze_traces.py > reports/run_20260810.txt

Output:
    LETA RETRIEVAL DIAGNOSTIC REPORT (terminal)
    + optional per-query / rank-table / hard-negative sections

This tool operates purely on local JSONL files.
No Claude API calls. No network access. Cost: $0.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap ─────────────────────────────────────────────────────────────────
_script_dir  = Path(__file__).resolve().parent
_backend_dir = _script_dir.parent
sys.path.insert(0, str(_backend_dir))

_DEFAULT_SUITE = _backend_dir / "data" / "regression" / "gst_regression_suite.json"
_TRACE_DIR     = _backend_dir / "data" / "regression" / "traces"


# ── Load helpers ──────────────────────────────────────────────────────────────

def load_traces(path: Path) -> list:
    traces = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return traces


def load_suite(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("tests", [])


def latest_trace_file() -> Path:
    """Return the most recently created JSONL in the traces directory."""
    files = sorted(_TRACE_DIR.glob("run_*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No trace files found in {_TRACE_DIR}")
    return files[-1]


# ── Gold matching (mirrors run_regression.py) ─────────────────────────────────

def _auth_matches_chunk(auth: str, rel_path: str, text_preview: str,
                        provisions: list = None) -> bool:
    """Mirrors run_regression.py._auth_matches_chunk — keep in sync."""
    rel  = rel_path.replace("\\", "/").lower()
    text = (text_preview or "").lower()
    pts  = auth.upper().split("_")
    if not pts:
        return False
    prefix = pts[0]

    if prefix == "CIRCULAR" and len(pts) >= 2:
        num = pts[1]
        return "circular" in rel and num in rel

    if prefix == "NOTIFICATION" and len(pts) >= 2:
        num = pts[1]
        return "notification" in rel and num in rel

    if prefix in ("CGST", "IGST", "UTGST", "CESS") and len(pts) >= 3:
        act_key = prefix.lower()
        subtype = pts[1]

        if subtype == "SEC":
            sec = pts[2]
            # P2.5: metadata provision key match (definitive)
            if provisions and (auth in provisions or any(
                p.startswith(auth + "_") for p in provisions
            )):
                right_act = (act_key in rel) or ("icai" in rel)
                if right_act:
                    return True
            right_doc = (act_key in rel) and ("act" in rel or "cgst" in rel or "igst" in rel)
            mentions   = (
                f"section {sec}" in text
                or f"section{sec}" in text
                or f"s. {sec}" in text
                or f"s.{sec}" in text
                or text.startswith(f"{sec} ")
                or f"\n{sec}." in text
            )
            return right_doc and mentions

        if subtype == "RUL":
            rule = pts[2]
            if provisions and (auth in provisions or any(
                p.startswith(auth + "_") for p in provisions
            )):
                return True
            return "rule" in rel and (rule in rel or f"rule {rule}" in text)

        if subtype == "SCHEDULE":
            return "schedule" in rel and act_key in rel

    return False


def _gold_chunk_ids(required_authorities: list, all_chunks: list) -> set:
    gold = set()
    for auth in required_authorities:
        for chunk in all_chunks:
            if _auth_matches_chunk(auth,
                                   chunk.get("rel_path", ""),
                                   chunk.get("text_preview", ""),
                                   chunk.get("provisions", [])):
                gold.add(chunk["chunk_id"])
    return gold


# ── Stage analysis ────────────────────────────────────────────────────────────

_STAGE_ORDER = [
    "faiss", "bm25", "tfidf", "rrf",
    "after_crossencoder", "after_legalreranker", "post_mmr", "final",
]

_STAGE_LABEL = {
    "faiss":               "FAISS",
    "bm25":                "BM25",
    "tfidf":               "TF-IDF",
    "rrf":                 "RRF",
    "after_crossencoder":  "CrossEncoder",
    "after_legalreranker": "LegalReranker",
    "post_mmr":            "MMR",
    "final":               "Authority Fill",
}


def _survival_map(stages: dict, gold_ids: set) -> dict:
    out = {}
    for stage in _STAGE_ORDER:
        if stage not in stages:
            continue
        ids_at = {e["chunk_id"] for e in stages[stage]}
        out[stage] = bool(ids_at & gold_ids)
    return out


def _first_failure(survival: dict) -> str:
    for stage in _STAGE_ORDER:
        if stage in survival and not survival[stage]:
            return stage
    return "generation"


def _best_rank_at(stages: dict, stage: str, gold_ids: set):
    snap  = stages.get(stage, [])
    ranks = [e["rank"] for e in snap if e["chunk_id"] in gold_ids]
    return min(ranks) if ranks else None


# ── Per-query analysis ────────────────────────────────────────────────────────

def analyze_query(trace: dict, test: dict) -> dict:
    """Full breakdown for one trace+test pair."""
    req_auths    = test.get("required_authorities", [])
    all_chunks   = trace.get("all_chunks", [])
    stages       = trace.get("stages", {})

    gold_ids     = _gold_chunk_ids(req_auths, all_chunks)
    survival     = _survival_map(stages, gold_ids) if gold_ids else {}
    ff           = _first_failure(survival) if gold_ids else "no_gold_match"

    # Rank at every stage
    ranks = {}
    for s in _STAGE_ORDER:
        r = _best_rank_at(stages, s, gold_ids)
        ranks[s] = (r + 1) if r is not None else None   # 1-indexed

    # Documents that beat gold in final (hard negatives)
    wrong_docs = []
    if gold_ids and not survival.get("final", True):
        doc_map = {c["chunk_id"]: c.get("document_id", "") for c in all_chunks}
        for entry in stages.get("final", []):
            doc_id = doc_map.get(entry["chunk_id"], "")
            if doc_id:
                wrong_docs.append(doc_id)

    return {
        "test_id":      test["id"],
        "query_id":     trace.get("query_id", ""),
        "query":        trace.get("query", "")[:80],
        "topic":        test.get("topic") or "unknown",
        "req_auths":    req_auths,
        "gold_matched": len(gold_ids),
        "first_failure":ff,
        "survival":     survival,
        "ranks":        ranks,
        "wrong_docs":   wrong_docs,
        "verdict":      trace.get("answer", {}).get("verdict", "?"),
    }


# ── Report generation ─────────────────────────────────────────────────────────

def generate_report(
    analyses: list,
    total_tests: int,
    traces: list,
    *,
    show_per_query: bool = False,
    show_rank_table: bool = False,
    show_hard_negatives: bool = False,
) -> str:
    W  = 62
    hr = "=" * W
    lr = "-" * W

    def _pct(n, d): return f"{round(100*n/d):3d}%" if d else "  -"
    def _bar(n, mx=8): return "#" * min(n, mx)

    n = len(analyses)

    # Aggregate counters
    ff_counts:       dict = defaultdict(int)
    survival_counts: dict = defaultdict(int)
    recall_at = {1: 0, 5: 0, 10: 0}
    mrr_total  = 0.0
    mrr_n      = 0
    hard_neg:        dict = defaultdict(int)
    topic_total:     dict = defaultdict(int)
    topic_fail:      dict = defaultdict(int)
    rank_sums:       dict = defaultdict(float)
    rank_count:      dict = defaultdict(int)

    for a in analyses:
        topic_total[a["topic"]] += 1
        if a.get("verdict") in ("fail", "partial", "error"):
            topic_fail[a["topic"]] += 1

        ff = a["first_failure"]
        ff_counts[ff] += 1

        for stage, survived in a["survival"].items():
            if survived:
                survival_counts[stage] += 1

        faiss_rank = a["ranks"].get("faiss")
        if faiss_rank is not None:
            mrr_total += 1.0 / faiss_rank
            mrr_n     += 1
            for k in [1, 5, 10]:
                if faiss_rank <= k:
                    recall_at[k] += 1

        for stage, r in a["ranks"].items():
            if r is not None:
                rank_sums[stage]  += r
                rank_count[stage] += 1

        for doc in a["wrong_docs"]:
            hard_neg[doc] += 1

    lines = [
        "",
        hr,
        "  LETA RETRIEVAL DIAGNOSTIC REPORT",
        lr,
        f"  Run date  : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"  Queries   : {total_tests} total  |  {n} with traces",
        "",
        "  DOCUMENT RECALL  (FAISS stage)",
        "  " + lr,
    ]
    for k in [1, 5, 10]:
        lines.append(f"  Recall@{k:<4}  {_pct(recall_at[k], n)}  ({recall_at[k]}/{n})")
    mrr = round(mrr_total / mrr_n, 3) if mrr_n else 0.0
    lines.append(f"  MRR         {mrr:.3f}")

    lines += ["", "  FIRST FAILURE STAGE", "  " + lr]
    max_ff = max(ff_counts.values(), default=1)
    for stage in _STAGE_ORDER + ["generation", "no_gold_match", "no_trace"]:
        cnt = ff_counts.get(stage, 0)
        if cnt == 0:
            continue
        label = _STAGE_LABEL.get(stage, stage.replace("_", " ").title())
        lines.append(f"  {label:<22}  {cnt:3d}  {_bar(cnt, max_ff)}")

    lines += ["", "  GOLD SURVIVAL PER STAGE  (avg rank of gold chunk)", "  " + lr]
    for stage in _STAGE_ORDER:
        ns  = survival_counts.get(stage, 0)
        pct = round(100 * ns / n) if n else 0
        avg = (round(rank_sums[stage] / rank_count[stage], 1)
               if rank_count.get(stage) else "-")
        label = _STAGE_LABEL.get(stage, stage)
        lines.append(
            f"  {label:<22}  {ns:3d}/{n}  ({pct:3d}%)  avg-rank={avg}"
        )

    lines += ["", "  FAILURE BY QUERY TOPIC", "  " + lr]
    for topic in sorted(topic_total.keys()):
        tot  = topic_total[topic]
        fail = topic_fail.get(topic, 0)
        pct  = _pct(fail, tot)
        lines.append(
            f"  {topic:<26}  {pct} fail  ({fail}/{tot})  {_bar(fail, tot)}"
        )

    lines += ["", "  TOP HARD NEGATIVES", "  " + lr]
    if hard_neg:
        top = sorted(hard_neg.items(), key=lambda x: -x[1])[:12]
        for i, (doc, cnt) in enumerate(top, 1):
            lines.append(f"  {i:2d}. {doc[:52]:<54} x{cnt}")
    else:
        lines.append("  (none)")

    lines += ["", hr, "", "  DECISION GUIDE", "  " + lr]
    lines.append("  FAISS miss        -> embedding quality / document not indexed")
    lines.append("  CrossEncoder drop -> reranker model wrong signal for GST law")
    lines.append("  LegalReranker drop-> authority boost mis-calibrated")
    lines.append("  MMR drop          -> diversity threshold too aggressive")
    lines.append("  Gold in final, wrong answer -> prompt / synthesis issue")
    lines.append(hr)

    # ── Per-query breakdown ────────────────────────────────────────────────────
    if show_per_query:
        lines += ["", "  PER-QUERY BREAKDOWN", "  " + lr]
        for a in sorted(analyses, key=lambda x: x["first_failure"]):
            survival_str = " -> ".join(
                f"{_STAGE_LABEL.get(s, s)}={'Y' if v else 'N'}"
                for s, v in a["survival"].items()
            )
            lines.append(f"  [{a['test_id']}] {a['query'][:60]}")
            lines.append(f"         first_failure={a['first_failure']}  gold_chunks={a['gold_matched']}")
            lines.append(f"         {survival_str}")
            if a["wrong_docs"]:
                lines.append(f"         hard_negs: {', '.join(a['wrong_docs'][:4])}")

    # ── Rank displacement table ────────────────────────────────────────────────
    if show_rank_table:
        lines += ["", "  GOLD RANK DISPLACEMENT BY STAGE (avg rank, lower=better)", "  " + lr]
        header = "  Query ID            " + "  ".join(
            f"{_STAGE_LABEL.get(s, s)[:6]:>6}" for s in _STAGE_ORDER
        )
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))
        for a in analyses:
            row = f"  {a['test_id']:<20}"
            for s in _STAGE_ORDER:
                r = a["ranks"].get(s)
                row += f"  {str(r) if r is not None else '-':>6}"
            lines.append(row)

    # ── Full hard negatives with rel_path ─────────────────────────────────────
    if show_hard_negatives and hard_neg:
        # Build doc_id -> rel_path mapping from all trace chunks
        doc_rel: dict = {}
        for trace in traces:
            for chunk in trace.get("all_chunks", []):
                did = chunk.get("document_id", "")
                if did and did not in doc_rel:
                    doc_rel[did] = chunk.get("rel_path", "")

        lines += ["", "  HARD NEGATIVES WITH PATHS", "  " + lr]
        for doc, cnt in sorted(hard_neg.items(), key=lambda x: -x[1]):
            path = doc_rel.get(doc, "unknown")
            lines.append(f"  x{cnt:3d}  {doc}")
            lines.append(f"        {path}")

    lines.append("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyze LETA retrieval trace JSONL and produce diagnostic report."
    )
    parser.add_argument("--file",  type=str,
                        help="Path to JSONL trace file (default: most recent in traces/)")
    parser.add_argument("--suite", type=str, default=str(_DEFAULT_SUITE),
                        help="Path to regression suite JSON")
    parser.add_argument("--per-query",       action="store_true",
                        help="Append per-query breakdown to report")
    parser.add_argument("--rank-table",      action="store_true",
                        help="Append gold rank displacement table")
    parser.add_argument("--hard-negatives",  action="store_true",
                        help="Append hard negatives with full rel_paths")
    args = parser.parse_args()

    # Load traces
    if args.file:
        trace_path = Path(args.file)
    else:
        trace_path = latest_trace_file()
    print(f"Loading traces from: {trace_path}", file=sys.stderr)

    traces = load_traces(trace_path)
    print(f"  {len(traces)} traces loaded", file=sys.stderr)

    # Load suite
    suite_path = Path(args.suite)
    if not suite_path.exists():
        print(f"ERROR: suite not found: {suite_path}", file=sys.stderr)
        sys.exit(2)
    tests = load_suite(suite_path)
    tests_by_id = {t["id"]: t for t in tests}
    print(f"  {len(tests)} test cases loaded", file=sys.stderr)

    # Match traces to tests by query string (since REG runner stores query)
    # Also match by query_id suffix patterns if available
    tests_by_query = {t["query"]: t for t in tests}

    analyses = []
    for trace in traces:
        query   = trace.get("query", "")
        test    = tests_by_query.get(query)
        if test is None:
            # Fallback: try substring match
            for t in tests:
                if t["query"][:50] == query[:50]:
                    test = t
                    break
        if test is None:
            continue
        analyses.append(analyze_query(trace, test))

    print(f"  {len(analyses)} traces matched to test cases", file=sys.stderr)

    if not analyses:
        print("ERROR: No traces matched test cases. Check that the suite matches the run.", file=sys.stderr)
        sys.exit(1)

    report = generate_report(
        analyses,
        total_tests=len(tests),
        traces=traces,
        show_per_query=args.per_query,
        show_rank_table=args.rank_table,
        show_hard_negatives=args.hard_negatives,
    )
    print(report)


if __name__ == "__main__":
    main()
