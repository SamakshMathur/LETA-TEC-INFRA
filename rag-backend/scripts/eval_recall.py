"""
Recall@k evaluation — retrieval-specific quality metric.

Measures whether the right chunk is in the top-k retrieved BEFORE reranking
and BEFORE generation.  This is the metric that tells you whether the corpus
changes in the ingestion layer (chunking, enrichment, query prefix) actually
improve the retrieval pool — end-to-end answer quality is a noisier signal.

Gold set: data/gold_100.json
  Each entry may optionally carry a "gold_sources" field listing expected
  rel_paths or substring matches (e.g. "Section_17") that must appear in the
  top-k retrieved chunks for the question to count as a hit.

  If "gold_sources" is absent, the entry is skipped for Recall@k (it only
  contributes to the separate answer-quality regression run).

Usage:
    python scripts/eval_recall.py                 # Recall@5, @10, @20
    python scripts/eval_recall.py --k 5 10 20     # explicit k values
    python scripts/eval_recall.py --top-k 40      # retrieval pool size
    python scripts/eval_recall.py --out results/recall_$(date +%F).json

Outputs:
    - Per-question hit/miss table to stdout
    - Summary Recall@k for each k value
    - Optional JSON file for tracking over time
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

# Minimal env so config.py doesn't crash
os.environ.setdefault("ANTHROPIC_API_KEY",  "eval-placeholder")
os.environ.setdefault("MONGODB_URI",        "mongodb://localhost:27017/eval")
os.environ.setdefault("SECRET_KEY",         "eval-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",          "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET","eval-placeholder")
os.environ.setdefault("FAST2SMS_API_KEY",   "eval-placeholder")
os.environ.setdefault("RESEND_API_KEY",     "eval-placeholder")
os.environ.setdefault("RAZORPAY_KEY_ID",    "eval-placeholder")
os.environ.setdefault("RAZORPAY_KEY_SECRET","eval-placeholder")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET","eval-placeholder")

GOLD_FILE = BASE_DIR / "data" / "gold_100.json"


def _load_gold(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        entries = json.load(f)
    with_sources = [e for e in entries if e.get("gold_sources")]
    print(f"Gold set: {len(entries)} total entries, {len(with_sources)} with gold_sources (evaluable)")
    return with_sources


def _source_hit(chunks: list[dict], gold_sources: list[str]) -> bool:
    """
    Return True if any gold_source string is a substring of any retrieved
    chunk's rel_path.  Case-insensitive match — "section_17" matches
    "CGST_Act/Section_17(5).pdf".
    """
    for chunk in chunks:
        rel = (
            chunk.get("rel_path") or
            chunk.get("metadata", {}).get("rel_path") or
            chunk.get("source") or ""
        ).replace("\\", "/").lower()
        if any(gs.lower() in rel for gs in gold_sources):
            return True
    return False


def run_eval(k_values: list[int], top_k: int, out_path: Optional[Path]) -> None:
    from app.retrieval.retriever import Retriever

    print("Loading retriever (FAISS + BM25)...")
    retriever = Retriever()
    print(f"Index: {retriever.index.ntotal:,} vectors | chunks: {len(retriever.chunks):,}\n")

    gold = _load_gold(GOLD_FILE)
    if not gold:
        print("No evaluable gold entries found.  Add 'gold_sources' fields to gold_100.json.")
        return

    # Track hits at each k
    hits_at_k = {k: 0 for k in k_values}
    results = []

    for i, entry in enumerate(gold, 1):
        query   = entry["query"]
        sources = entry["gold_sources"]
        qid     = entry.get("id", f"Q{i}")
        cat     = entry.get("category", "—")

        t0 = time.monotonic()
        chunks = retriever.search(
            query=query,
            top_k=top_k,
            allowed_sources=[".pdf", ".docx", ".xlsx", ".xls"],
            advanced_queries=None,
            domain_paths=[],
            is_draft=False,
            skip_rerank=True,   # pre-rerank recall is what we're measuring
        )
        latency_ms = round((time.monotonic() - t0) * 1000)

        row: dict = {
            "id": qid, "category": cat, "query": query[:80],
            "gold_sources": sources,
            "latency_ms": latency_ms,
        }

        for k in sorted(k_values):
            hit = _source_hit(chunks[:k], sources)
            hits_at_k[k] += int(hit)
            row[f"hit@{k}"] = hit

        status = "✓" if row.get(f"hit@{max(k_values)}") else "✗"
        print(f"  [{i:3d}/{len(gold)}] {status} [{cat}] {query[:60]}…  ({latency_ms}ms)")
        results.append(row)

    # Summary
    n = len(gold)
    print(f"\n{'─'*60}")
    print(f"Recall@k over {n} evaluable questions:")
    summary = {}
    for k in sorted(k_values):
        r = hits_at_k[k] / n
        summary[f"recall@{k}"] = round(r, 4)
        bar = "█" * round(r * 40)
        print(f"  Recall@{k:2d}: {hits_at_k[k]:3d}/{n}  ({r:.1%})  {bar}")
    print()

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "top_k_pool": top_k,
            "n_evaluated": n,
            "summary": summary,
            "results": results,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Results saved → {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Recall@k evaluation for LETA retrieval")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20],
                        help="k values to evaluate (default: 5 10 20)")
    parser.add_argument("--top-k", type=int, default=40,
                        help="Size of retrieval pool (default: 40)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Optional path to write JSON results")
    args = parser.parse_args()

    run_eval(k_values=sorted(set(args.k)), top_k=args.top_k, out_path=args.out)


if __name__ == "__main__":
    main()
