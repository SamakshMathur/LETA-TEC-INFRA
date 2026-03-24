import json
import re
from pathlib import Path
from collections import Counter

CHUNKS_PATH = Path("data/chunks/chunks.jsonl")

def verify_precision():
    print("--- LETA 9.5/10 LEGAL PRECISION AUDIT ---")
    
    if not CHUNKS_PATH.exists():
        print("Error: chunks.jsonl not found.")
        return

    chunks = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
            
    total = len(chunks)
    print(f"Total Chunks: {total}")

    # Check 1: Unique IDs
    ids = [c["chunk_id"] for c in chunks]
    unique_ids = set(ids)
    is_unique = len(ids) == len(unique_ids)
    print(f"Check 1: Unique IDs -> {'PASSED' if is_unique else 'FAILED'}")
    if not is_unique:
        dupes = [k for k, v in Counter(ids).items() if v > 1]
        print(f"  Found {len(dupes)} duplicate IDs. Example: {dupes[0]}")

    # Check 2: OCR Corruption Detection
    broken_tokens = ["worl<s", "contracl", "I(one", "secfion", "regisfration"]
    found_broken = 0
    for c in chunks:
        if any(t in c["text"].lower() for t in broken_tokens):
            found_broken += 1
    
    print(f"Check 2: OCR Cleanup -> {'PASSED' if found_broken == 0 else 'WARNING'}")
    if found_broken > 0:
        print(f"  Still found {found_broken} chunks with corrupted tokens.")

    # Check 3: Minimum Text Quality (Alpha Ratio)
    low_quality = 0
    for c in chunks:
        alphas = sum(1 for char in c["text"] if char.isalpha())
        ratio = alphas / len(c["text"]) if len(c["text"]) > 0 else 0
        if ratio < 0.5: # 0.5 threshold for auditing
            low_quality += 1
            
    print(f"Check 3: Text Quality Gate -> {low_quality} chunks below 0.5 alpha ratio.")

    # Check 4: Metadata Completeness
    missing_meta = 0
    required_fields = ["topic", "document_type", "source", "law_type", "structural_part"]
    for c in chunks:
        meta = c["metadata"]
        if not all(field in meta for field in required_fields):
            missing_meta += 1
            
    print(f"Check 4: Metadata Completeness -> {total - missing_meta}/{total} compliant.")

    # Check 5: Structural Presence in Case Law
    caselaw_chunks = [c for c in chunks if c["metadata"]["document_type"] in ["Case Law", "Advance Ruling"]]
    structural_types = set([c["metadata"].get("structural_part") for c in caselaw_chunks])
    print(f"Check 5: Structural Coverage -> {len(structural_types)} parts detected: {list(structural_types)}")

    # Specific Audit: Provision-level Statute check
    statute_chunks = [c for c in chunks if c["metadata"]["document_type"] == "Statute"]
    if statute_chunks:
        example = statute_chunks[0]
        print(f"\nExample Statute Chunk: {example['chunk_id']}")
        print(f"  Metadata: {json.dumps(example['metadata'], indent=2)}")

if __name__ == "__main__":
    verify_precision()
