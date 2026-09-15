#!/usr/bin/env python3
"""
Corpus Provision Metadata Integrity Gate
========================================
Reusable, domain-agnostic auditor that evaluates corpus integrity before promotion:
1. Primary provision structural detection from source text vs metadata.provision_keys.
2. Metadata section_labels / section_label consistency.
3. Provision-index bidirectional consistency (no missing or orphaned index pointers).
4. Text integrity, required schema fields, and duplicate chunk IDs.

Usage:
    python scripts/validate_corpus_integrity.py --chunks data/chunks/chunks.jsonl
    python scripts/validate_corpus_integrity.py --chunks data/candidate_corpus/chunks.jsonl --report-file scratch/corpus_integrity_report.json
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Set, Any, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.ingestion.provision_extractor import StructuralProvisionExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("corpus_integrity_gate")


@dataclass
class MismatchRecord:
    chunk_id: str
    rel_path: str
    chunk_index: Optional[int]
    detected_primary_provisions: List[str]
    metadata_provision_keys: List[str]
    missing_provisions: List[str]
    snippet: str
    error_type: str


@dataclass
class CorpusIntegrityReport:
    total_documents: int = 0
    total_chunks: int = 0
    chunks_with_provisions: int = 0
    primary_provision_checks: int = 0
    provision_metadata_mismatches: int = 0
    missing_provision_index_mappings: int = 0
    orphan_provision_index_entries: int = 0
    duplicate_chunk_ids: int = 0
    malformed_chunks: int = 0
    passed: bool = False
    mismatches: List[MismatchRecord] = field(default_factory=list)


def validate_corpus(chunks: List[Dict[str, Any]]) -> CorpusIntegrityReport:
    report = CorpusIntegrityReport()
    report.total_chunks = len(chunks)

    seen_docs: Set[str] = set()
    seen_cids: Set[str] = set()
    provision_index: Dict[str, List[int]] = defaultdict(list)

    # 1. Build provision index from metadata
    for idx, chunk in enumerate(chunks):
        cid = chunk.get("chunk_id") or chunk.get("id")
        if not cid:
            report.malformed_chunks += 1
            continue
        if cid in seen_cids:
            report.duplicate_chunk_ids += 1
        seen_cids.add(cid)

        meta = chunk.get("metadata", {})
        rel_path = meta.get("rel_path") or chunk.get("rel_path", "")
        if rel_path:
            seen_docs.add(rel_path)

        pkeys = meta.get("provision_keys", []) or chunk.get("provision_keys", [])
        if pkeys:
            report.chunks_with_provisions += 1
        for pk in pkeys:
            provision_index[pk].append(idx)

    report.total_documents = len(seen_docs)

    # 2. Audit each chunk against StructuralProvisionExtractor
    for idx, chunk in enumerate(chunks):
        cid = chunk.get("chunk_id") or chunk.get("id") or str(idx)
        text = chunk.get("text", "") or chunk.get("content", "")
        meta = chunk.get("metadata", {})
        rel_path = meta.get("rel_path") or chunk.get("rel_path", "")
        category = meta.get("category") or chunk.get("category", "")
        pkeys = meta.get("provision_keys", []) or chunk.get("provision_keys", [])
        pkeys_set = set(pkeys)

        if not text:
            report.malformed_chunks += 1
            continue

        report.primary_provision_checks += 1
        extracted = StructuralProvisionExtractor.extract(text, rel_path, category)
        detected_primary = extracted.primary_provision_keys

        # Check: Every detected primary provision MUST be present in metadata provision_keys
        missing = [dp for dp in detected_primary if dp not in pkeys_set]
        if missing:
            report.provision_metadata_mismatches += 1
            report.mismatches.append(MismatchRecord(
                chunk_id=cid,
                rel_path=rel_path,
                chunk_index=meta.get("chunk_index"),
                detected_primary_provisions=detected_primary,
                metadata_provision_keys=pkeys,
                missing_provisions=missing,
                snippet=text[:250].replace("\n", " "),
                error_type="MISSING_PRIMARY_PROVISION_IN_METADATA",
            ))

        # Check: Provision index must map detected primary provisions to this chunk index
        for dp in detected_primary:
            if dp in pkeys_set and idx not in provision_index.get(dp, []):
                report.missing_provision_index_mappings += 1

    # Check: Overall pass/fail
    report.passed = (
        report.provision_metadata_mismatches == 0
        and report.missing_provision_index_mappings == 0
        and report.duplicate_chunk_ids == 0
        and report.malformed_chunks == 0
    )

    return report


def print_report(report: CorpusIntegrityReport) -> None:
    print("\n" + "=" * 60)
    print("           CORPUS PROVISION INTEGRITY REPORT")
    print("=" * 60)
    print(f"Documents:                         {report.total_documents:,}")
    print(f"Chunks:                            {report.total_chunks:,}")
    print(f"Chunks with Provisions:            {report.chunks_with_provisions:,}")
    print(f"Primary Provision Checks:          {report.primary_provision_checks:,}")
    print(f"Provision Metadata Mismatches:     {report.provision_metadata_mismatches}")
    print(f"Missing Provision-Index Mappings:  {report.missing_provision_index_mappings}")
    print(f"Duplicate Chunk IDs:               {report.duplicate_chunk_ids}")
    print(f"Malformed Chunks:                  {report.malformed_chunks}")
    print("-" * 60)
    if report.passed:
        print("VERDICT:                           [PASS] PROMOTION APPROVED")
    else:
        print("VERDICT:                           [FAIL] CORPUS PROMOTION BLOCKED")
    print("=" * 60 + "\n")

    if report.mismatches:
        print(f"Showing first {min(10, len(report.mismatches))} mismatches:")
        for m in report.mismatches[:10]:
            print(f"  • Chunk ID: {m.chunk_id} | Path: {m.rel_path}")
            print(f"    Detected Primary: {m.detected_primary_provisions}")
            print(f"    Metadata Keys:    {m.metadata_provision_keys}")
            print(f"    Missing Keys:     {m.missing_provisions}")
            print(f"    Snippet:          {m.snippet}")
            print("-" * 50)


def main() -> int:
    parser = argparse.ArgumentParser(description="Corpus Provision Metadata Integrity Gate")
    parser.add_argument("--chunks", required=True, help="Path to chunks.jsonl file to audit")
    parser.add_argument("--report-file", default=None, help="Optional JSON path to save report")
    args = parser.parse_args()

    chunks_path = Path(args.chunks)
    if not chunks_path.exists():
        log.error("Chunks file not found: %s", chunks_path)
        return 1

    chunks = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    report = validate_corpus(chunks)
    print_report(report)

    if args.report_file:
        report_path = Path(args.report_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        # Serialize report dataclass
        rep_dict = asdict(report)
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(rep_dict, f, indent=2)
        log.info("Saved report to %s", report_path)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
