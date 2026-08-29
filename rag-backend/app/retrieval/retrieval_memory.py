"""
Retrieval Memory  (Priority 9)
================================
Logs every query + retrieval outcome to an append-only JSONL file.
Provides a mining function that surfaces "if query mentions X, always retrieve Y" patterns
so they can be fed back into the authority registry.

Two components:

1. RetrievalLogger  — appends one JSON line per query (zero latency impact;
   writes are fire-and-forget via a background thread).

2. mine_retrieval_patterns()  — offline analysis script that reads the log
   and produces authority_registry ADDITIONS for topics that are consistently
   missing an authority that always appears when manually inspected.

Usage in retriever.py:
    from app.retrieval.retrieval_memory import RetrievalLogger
    _mem_logger = RetrievalLogger()

    # After coverage check, inside search() or supplement_and_rerank():
    _mem_logger.log(
        query        = query,
        topic        = _taxonomy.get("topics", []),
        retrieved    = [c.get("rel_path", "") for c in final_chunks[:15]],
        coverage_pct = _coverage_result.get("coverage_pct", 0),
        missing      = _coverage_result.get("missing", []),
    )
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from app.utils.time import utc_now
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Log file location ─────────────────────────────────────────────────────────
_DEFAULT_LOG = Path(__file__).resolve().parent.parent.parent / "data" / "retrieval_memory.jsonl"


class RetrievalLogger:
    """
    Append-only JSONL logger for retrieval outcomes.
    All writes happen on a daemon worker thread — zero latency impact on the
    main retrieval path.

    Log entry schema (one JSON object per line):
    {
        "ts":           "ISO-8601 UTC timestamp",
        "query":        "raw query string",
        "topics":       ["cross_charge", ...],       # taxonomy topic matches
        "retrieved":    ["circulars/199.../...", ...], # top-15 rel_paths
        "coverage_pct": 85,                          # mandatory coverage %
        "missing":      ["CGST_SEC_25", ...],        # authorities NOT found
        "duration_ms":  142                          # retrieval wall time (optional)
    }
    """

    def __init__(self, log_path: Path | str | None = None):
        self._path   = Path(log_path) if log_path else _DEFAULT_LOG
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock   = threading.Lock()
        self._queue  = []
        self._worker = threading.Thread(target=self._flush_loop, daemon=True)
        self._worker.start()
        logger.info(f"RetrievalLogger: logging to {self._path}")

    def log(
        self,
        query:        str,
        topics:       list[str],
        retrieved:    list[str],
        coverage_pct: int,
        missing:      list[str],
        duration_ms:  int = 0,
    ) -> None:
        """Enqueues a log entry (non-blocking)."""
        entry = {
            "ts":           utc_now().isoformat(),
            "query":        query,
            "topics":       topics,
            "retrieved":    retrieved[:20],  # cap to avoid bloat
            "coverage_pct": coverage_pct,
            "missing":      missing,
            "duration_ms":  duration_ms,
        }
        with self._lock:
            self._queue.append(entry)

    def _flush_loop(self) -> None:
        """Worker: drains the queue every 5 seconds."""
        import time
        while True:
            time.sleep(5)
            self._drain()

    def _drain(self) -> None:
        with self._lock:
            batch, self._queue = self._queue, []
        if not batch:
            return
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                for entry in batch:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning(f"RetrievalLogger flush failed: {exc}")


# ── Offline pattern miner ─────────────────────────────────────────────────────

def mine_retrieval_patterns(
    log_path: Path | str | None = None,
    min_occurrences: int = 5,
    min_miss_rate: float = 0.3,
    output_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Analyses the retrieval log to find patterns like:
      "For topic X, authority Y is missing in 40% of queries → add Y to registry"

    Args:
        log_path:        Path to retrieval_memory.jsonl (default: data/retrieval_memory.jsonl)
        min_occurrences: Minimum times a topic must appear to be included in report
        min_miss_rate:   Fraction of queries where an authority is missing to flag it
        output_path:     If set, writes JSON report to this path

    Returns:
        {
            "topic_stats": {
                "cross_charge": {
                    "count": 42,
                    "avg_coverage_pct": 67,
                    "frequent_missing": [
                        {"authority": "CGST_SEC_25", "miss_rate": 0.52, "count": 22}
                    ]
                }
            },
            "registry_additions": {
                "cross_charge": {
                    "sections": ["CGST_SEC_25"],    # should add to registry
                    "circulars": ["CIRCULAR_199"],
                }
            }
        }

    After running this, review the `registry_additions` section and apply them
    to data/authority_registry.json.  The legal team can also run this manually
    after observing patterns in production.
    """
    _log_path = Path(log_path) if log_path else _DEFAULT_LOG
    if not _log_path.exists():
        return {"error": f"Log file not found: {_log_path}", "topic_stats": {}, "registry_additions": {}}

    # Load log
    entries = []
    with open(_log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not entries:
        return {"error": "Log is empty", "topic_stats": {}, "registry_additions": {}}

    # Aggregate per topic
    topic_counts:    dict[str, int]             = defaultdict(int)
    topic_cov_sum:   dict[str, int]             = defaultdict(int)
    topic_miss:      dict[str, dict[str, int]]  = defaultdict(lambda: defaultdict(int))

    for entry in entries:
        for topic in entry.get("topics", ["unknown"]):
            topic_counts[topic] += 1
            topic_cov_sum[topic] += entry.get("coverage_pct", 100)
            for miss in entry.get("missing", []):
                topic_miss[topic][miss] += 1

    # Build stats
    topic_stats: dict[str, Any] = {}
    registry_additions: dict[str, Any] = {}

    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        if count < min_occurrences:
            continue

        avg_cov = round(topic_cov_sum[topic] / count)
        miss_items = topic_miss.get(topic, {})

        frequent_missing = [
            {
                "authority": auth,
                "miss_rate": round(n / count, 2),
                "count":     n,
            }
            for auth, n in sorted(miss_items.items(), key=lambda x: -x[1])
            if n / count >= min_miss_rate
        ]

        topic_stats[topic] = {
            "count":           count,
            "avg_coverage_pct": avg_cov,
            "frequent_missing": frequent_missing,
        }

        if frequent_missing:
            additions: dict[str, list[str]] = {"sections": [], "rules": [], "circulars": []}
            for item in frequent_missing:
                auth = item["authority"]
                if "_SEC_" in auth:
                    additions["sections"].append(auth)
                elif "_RUL_" in auth:
                    additions["rules"].append(auth)
                elif auth.startswith("CIRCULAR_"):
                    additions["circulars"].append(auth)
            if any(additions.values()):
                registry_additions[topic] = additions

    result = {
        "analysed":          len(entries),
        "first_entry":       entries[0]["ts"] if entries else None,
        "last_entry":        entries[-1]["ts"] if entries else None,
        "topic_stats":       topic_stats,
        "registry_additions": registry_additions,
    }

    if output_path:
        with open(Path(output_path), "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
        logger.info(f"Pattern mining report written to {output_path}")

    return result


if __name__ == "__main__":
    """
    Quick CLI:
        python -m app.retrieval.retrieval_memory
    """
    import sys
    _out = sys.argv[1] if len(sys.argv) > 1 else None
    report = mine_retrieval_patterns(output_path=_out)
    print(json.dumps(report, indent=2, ensure_ascii=False))
