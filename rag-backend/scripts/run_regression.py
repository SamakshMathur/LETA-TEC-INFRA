#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GST RAG Regression Suite Runner  (Priority 11)
===============================================
Runs all test cases in data/regression/gst_regression_suite.json against the
live retrieval system and reports authority coverage per question.

Usage:
    # From the rag-backend/ directory — baseline run, no Claude API calls
    python scripts/run_regression.py

    # Full pipeline with trace capture — still $0, no Claude calls
    python scripts/run_regression.py --save-traces

    # Fast retrieval only (skip CrossEncoder/LegalReranker/MMR) — partial traces
    python scripts/run_regression.py --save-traces --retrieval-only

    # Run only high-priority tests
    python scripts/run_regression.py --priority high

    # Run a single test by ID
    python scripts/run_regression.py --id CC-001

    # Output results as JSON
    python scripts/run_regression.py --json > results.json

    # Set a minimum coverage threshold (default 70) to fail the run
    python scripts/run_regression.py --min-coverage 80

Cost note:
    This script calls retriever.search() / supplement_and_rerank() directly,
    NOT the /ask HTTP endpoint. Claude (Haiku/Sonnet) is never invoked.
    Running all 60 queries costs $0.00 in API tokens.

    To collect full end-to-end traces (including LLM answer quality), hit the
    live /ask endpoint instead — that costs ~$0.35/query with Sonnet.

What it checks per test case:
    1. required_cats        — are all required document categories present in top-15?
    2. required_authorities — are the specific provision/circular keys present?
    3. required_keywords    — do the retrieved chunks' text contain these terms?

Output:
    Pass / Partial / Fail per test, with aggregate stats at the end.
    Exit code 0 if pass rate ≥ min-coverage threshold, else 1.
    Traces (if --save-traces) → data/regression/traces/run_YYYYMMDD_HHMMSS.jsonl

Run this before every production deployment:
    python scripts/run_regression.py --priority high --min-coverage 80
    # If exit code = 1, investigate before deploying.
"""
import argparse
import json
import os
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap: add rag-backend to sys.path ───────────────────────────────────
_script_dir  = Path(__file__).resolve().parent
_backend_dir = _script_dir.parent
sys.path.insert(0, str(_backend_dir))


def _bootstrap_env():
    """Load environment variables from .env if present (dev only)."""
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

def load_test_suite(suite_path: Path) -> list[dict]:
    with open(suite_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tests", [])


# ── Result evaluation ─────────────────────────────────────────────────────────

_CIR_NUM_RE = re.compile(
    r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
    r'|cir[-_.](?:cgst[-_.])?'
    r'|cir(?=[0-9])'
    r'|circularno[-_.])'
    r'(\d{2,3})',
    re.IGNORECASE,
)
_CIR_LEADING_RE = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)


def _chunk_category(chunk: dict) -> str:
    """Infer document category from rel_path."""
    meta = chunk.get("metadata", {})
    rel  = (chunk.get("rel_path") or meta.get("rel_path", "")).replace("\\", "/").lower()
    if any(f in rel for f in ("/notification", "/notifications")):
        return "notification"
    if any(f in rel for f in ("/circular", "/circulars")):
        return "circular"
    if any(f in rel for f in ("high court", "supreme court", "/aar", "other app")):
        return "case_law"
    if any(f in rel for f in ("/act", "/cgst", "/igst", "/rules", "/rule")):
        return "statute"
    return "other"


def _circular_key(rel_path: str) -> str | None:
    fname = rel_path.replace("\\", "/").split("/")[-1]
    m = _CIR_NUM_RE.search(fname) or _CIR_LEADING_RE.match(fname)
    return f"CIRCULAR_{m.group(1)}" if m else None


def evaluate_result(test: dict, chunks: list[dict]) -> dict:
    """
    Evaluates a list of retrieved chunks against the test case's expectations.

    Returns:
        {
            "verdict":      "pass" | "partial" | "fail"
            "cats_found":   list[str]
            "cats_missing": list[str]
            "auths_found":  list[str]
            "auths_missing":list[str]
            "kw_found":     list[str]
            "kw_missing":   list[str]
            "coverage_pct": int
        }
    """
    req_cats   = set(test.get("required_cats",        []))
    req_auths  = list(test.get("required_authorities", []))
    req_kws    = list(test.get("required_keywords",    []))

    # Collect what's in the retrieved pool
    present_cats:   set[str] = set()
    present_provs:  set[str] = set()
    present_circs:  set[str] = set()
    all_text = ""

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        present_cats.add(_chunk_category(chunk))
        for p in meta.get("provisions", []) + meta.get("citations", []):
            if p:
                present_provs.add(p)
        rel = (chunk.get("rel_path") or meta.get("rel_path", ""))
        ck = _circular_key(rel)
        if ck:
            present_circs.add(ck)
        all_text += " " + (chunk.get("content") or chunk.get("text") or "").lower()

    # Category check
    cats_missing = sorted(req_cats - present_cats)
    cats_found   = sorted(req_cats & present_cats)

    # Authority check
    auths_found:   list[str] = []
    auths_missing: list[str] = []
    for auth in req_auths:
        if auth in present_circs:
            auths_found.append(auth)
        elif auth in present_provs or any(p.startswith(auth + "_") for p in present_provs):
            auths_found.append(auth)
        else:
            auths_missing.append(auth)

    # Keyword check (in chunk text)
    kw_found:   list[str] = [kw for kw in req_kws if kw.lower() in all_text]
    kw_missing: list[str] = [kw for kw in req_kws if kw.lower() not in all_text]

    # Coverage calculation
    total = len(req_cats) + len(req_auths) + len(req_kws)
    found = len(cats_found) + len(auths_found) + len(kw_found)
    coverage_pct = round(100 * found / total) if total else 100

    # Verdict
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


# ── Terminal colours ──────────────────────────────────────────────────────────

_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

def _colour(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


# ── Trace helpers ─────────────────────────────────────────────────────────────

def _make_query_id() -> str:
    """Generate a LETA-style query_id for the regression run."""
    import uuid
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rand = uuid.uuid4().hex[:6].upper()
    return f"LETA-{ts}-{rand}-REG"


# ── Main runner ───────────────────────────────────────────────────────────────

def run_tests(
    tests: list[dict],
    retriever,
    priority_filter: str | None,
    id_filter: str | None,
    top_k: int = 15,
    save_traces: bool = False,
    retrieval_only: bool = False,
    trace_dir: Path | None = None,
) -> list[dict]:
    results    = []
    all_traces = []

    # Import trace machinery (optional — if not available, silently skip)
    RetrievalTrace = None
    if save_traces:
        try:
            from app.retrieval.retrieval_trace import RetrievalTrace as _RT
            RetrievalTrace = _RT
        except ImportError:
            print(_colour("  ⚠ retrieval_trace not importable — traces will be skipped", _YELLOW))
            save_traces = False

    filtered = [
        t for t in tests
        if (priority_filter is None or t.get("priority") == priority_filter)
        and (id_filter is None or t.get("id") == id_filter)
    ]

    mode_label = "retrieval-only" if retrieval_only else "full-pipeline"
    trace_note = " + trace capture" if save_traces else ""
    print(f"\n{_colour('GST RAG Regression Suite', _BOLD)}")
    print(f"Running {len(filtered)} tests  [top_k={top_k}] [{mode_label}{trace_note}]  [cost: $0.00]")
    print("─" * 70)

    for i, test in enumerate(filtered, 1):
        tid   = test["id"]
        query = test["query"]
        prio  = test.get("priority", "medium")

        # Create a fresh trace for this query
        trace = None
        query_id = _make_query_id()
        if save_traces and RetrievalTrace is not None:
            try:
                trace = RetrievalTrace(query_id=query_id, query=query)
                trace.record_preprocessing(
                    original_query=query,
                    refined_query=query,       # regression runner doesn't refine
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
                # Fast path: FAISS + BM25 + TF-IDF + RRF only
                chunks = retriever.search(query, top_k=top_k, trace=trace)
            else:
                # Full pipeline: search → supplement_and_rerank (CrossEnc + MMR + injection)
                fast_chunks = retriever.search(query, top_k=top_k * 2, trace=trace)
                try:
                    chunks = retriever.supplement_and_rerank(
                        fast_chunks,
                        [],          # no advanced_queries in regression mode
                        query,
                        top_k,
                        trace,
                    )
                except TypeError:
                    # supplement_and_rerank signature may not accept trace yet
                    chunks = retriever.supplement_and_rerank(fast_chunks, [], query, top_k)

        except Exception as exc:
            print(f"  [{i:3d}/{len(filtered)}] {tid:14s}  ERROR: {exc}")
            results.append({
                "id": tid, "query": query, "priority": prio,
                "verdict": "error", "error": str(exc),
                "duration_ms": 0,
                "query_id": query_id,
            })
            continue

        dur_ms  = round((time.perf_counter() - t0) * 1000)
        eval_r  = evaluate_result(test, chunks)
        verdict = eval_r["verdict"]

        # Finalize trace
        if trace is not None:
            try:
                trace.finalize(chunks, answer_meta={
                    "query_id":    query_id,
                    "mode":        "regression",
                    "retrieval_only": retrieval_only,
                    "verdict":     verdict,
                    "coverage_pct": eval_r["coverage_pct"],
                })
                all_traces.append(trace.to_debug_dict())
            except Exception:
                pass

        colour = _GREEN if verdict == "pass" else _YELLOW if verdict == "partial" else _RED
        label  = verdict.upper().ljust(7)
        print(
            f"  [{i:3d}/{len(filtered)}] {tid:14s}  "
            f"{_colour(label, colour)}  "
            f"cov={eval_r['coverage_pct']:3d}%  {dur_ms:5d}ms  "
            f"{query[:55]}"
        )
        if verdict != "pass":
            if eval_r["cats_missing"]:
                print(f"              ⚠ cats missing:  {eval_r['cats_missing']}")
            if eval_r["auths_missing"]:
                print(f"              ⚠ auths missing: {eval_r['auths_missing']}")
            if eval_r["kw_missing"]:
                print(f"              ⚠ kw missing:    {eval_r['kw_missing']}")

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

    # Save traces to JSONL
    if save_traces and all_traces and trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        run_ts    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path  = trace_dir / f"run_{run_ts}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for t in all_traces:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        print(f"\n  [traces] Saved {len(all_traces)} traces -> {out_path}")

    return results


def print_summary(results: list[dict], min_coverage: int) -> bool:
    """Prints aggregate stats. Returns True if pass rate meets min_coverage."""
    total   = len(results)
    passes  = sum(1 for r in results if r["verdict"] == "pass")
    partials= sum(1 for r in results if r["verdict"] == "partial")
    fails   = sum(1 for r in results if r["verdict"] in ("fail", "error"))
    pass_pct= round(100 * passes / total) if total else 0
    avg_cov = round(sum(r.get("coverage_pct", 0) for r in results) / total) if total else 0
    avg_ms  = round(sum(r.get("duration_ms", 0) for r in results) / total) if total else 0

    print("\n" + "═" * 70)
    print(f"  {_colour('RESULTS', _BOLD)}")
    print(f"  Total    : {total}")
    print(f"  Pass     : {_colour(str(passes), _GREEN)}")
    print(f"  Partial  : {_colour(str(partials), _YELLOW)}")
    print(f"  Fail     : {_colour(str(fails), _RED)}")
    print(f"  Pass rate: {pass_pct}%  (threshold: {min_coverage}%)")
    print(f"  Avg cov  : {avg_cov}%")
    print(f"  Avg ms   : {avg_ms}ms / query")
    print("═" * 70)

    ok = pass_pct >= min_coverage
    if ok:
        print(_colour(f"  ✓ REGRESSION SUITE PASSED (pass rate {pass_pct}% ≥ {min_coverage}%)", _GREEN))
    else:
        print(_colour(f"  ✗ REGRESSION SUITE FAILED (pass rate {pass_pct}% < {min_coverage}%)", _RED))
        high_fails = [r for r in results if r.get("priority") == "high" and r["verdict"] in ("fail", "error")]
        if high_fails:
            print(f"\n  {_colour('High-priority failures:', _RED)}")
            for r in high_fails:
                print(f"    {r['id']:14s}  {r['query'][:60]}")
    print()
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Run the GST RAG regression suite against the live retriever. "
                    "No Claude API calls — cost is always $0.00."
    )
    parser.add_argument("--priority",     choices=["high", "medium", "low"],
                        help="Filter tests by priority (default: all)")
    parser.add_argument("--id",           type=str,  help="Run a single test by ID")
    parser.add_argument("--min-coverage", type=int,  default=70,
                        help="Minimum pass-rate %% to exit 0 (default: 70)")
    parser.add_argument("--top-k",        type=int,  default=15,
                        help="Chunks to retrieve per query (default: 15)")
    parser.add_argument("--json",         action="store_true",
                        help="Output raw JSON results to stdout (instead of coloured table)")
    parser.add_argument("--suite",        type=str,
                        default=str(_backend_dir / "data" / "regression" / "gst_regression_suite.json"),
                        help="Path to test suite JSON file")

    # Trace collection flags
    parser.add_argument(
        "--save-traces",
        action="store_true",
        help=(
            "Record a RetrievalTrace per query and save to "
            "data/regression/traces/run_YYYYMMDD_HHMMSS.jsonl. "
            "Still costs $0 — no LLM calls."
        ),
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help=(
            "Skip supplement_and_rerank() (no CrossEncoder / LegalReranker / MMR). "
            "Faster and lower memory. Produces partial traces (FAISS/BM25/TF-IDF/RRF only). "
            "Use when you only want to check raw retrieval, not full reranking."
        ),
    )

    args = parser.parse_args()

    # Load test suite
    suite_path = Path(args.suite)
    if not suite_path.exists():
        print(f"ERROR: test suite not found at {suite_path}", file=sys.stderr)
        sys.exit(2)
    tests = load_test_suite(suite_path)
    print(f"Loaded {len(tests)} tests from {suite_path.name}")

    # Initialise retriever
    print("Initialising retriever (may take 30–90s for sub-index builds)…")
    try:
        from app.retrieval.retriever import Retriever
        retriever = Retriever()
    except Exception as exc:
        print(f"ERROR: Could not initialise Retriever: {exc}", file=sys.stderr)
        raise

    trace_dir = _backend_dir / "data" / "regression" / "traces"

    # Run
    results = run_tests(
        tests,
        retriever,
        priority_filter=args.priority,
        id_filter=args.id,
        top_k=args.top_k,
        save_traces=args.save_traces,
        retrieval_only=args.retrieval_only,
        trace_dir=trace_dir,
    )

    # Output
    if args.json:
        output = {
            "run_at":           datetime.now(timezone.utc).isoformat(),
            "suite":            str(suite_path),
            "save_traces":      args.save_traces,
            "retrieval_only":   args.retrieval_only,
            "api_cost_usd":     0.00,
            "results":          results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        ok = print_summary(results, args.min_coverage)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
