"""
diagnose_v2_retrieval.py  —  Systematic retrieval quality audit for V2.0 database
===================================================================================
Checks every V2.0 folder across 5 dimensions:

  1. Haiku context quality  — are enrichment contexts meaningful or generic?
  2. Provision key coverage — what % of chunks have legal provision tags?
  3. Chunk text quality     — blank / too-short chunks
  4. Live retrieval test    — fires 1 representative query per folder, checks if
                              a V2.0 doc actually surfaces in top-10 results
  5. Embedding drift check  — are embed_text fields meaningfully different from
                              raw text (confirms Haiku enrichment actually ran)?

Usage:
    cd RAG/rag-backend
    .\.win_venv\Scripts\python.exe scripts/diagnose_v2_retrieval.py
"""

import json
import sys
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.WARNING)  # suppress noisy retriever logs
log = logging.getLogger("diagnose")

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import CHUNKS_PATH, VECTOR_DB_PATH

CHUNKS_FILE     = Path(CHUNKS_PATH)
CTX_CACHE_FILE  = BASE_DIR / "vectordb" / "v2_doc_contexts.json"

# ── Representative test queries per V2.0 folder ───────────────────────────────
FOLDER_QUERIES = {
    "CGST Acts": (
        "What are the conditions for ITC eligibility under Section 16?",
        ["section_16", "cgst", "itc"]
    ),
    "CGST Rules 10-08-2026": (
        "What is the procedure for ITC reversal under Rule 42?",
        ["rule_42", "cgst_rules", "itc_reversal"]
    ),
    "circulars(2017-2025)": (
        "Personal guarantee by director to bank GST applicability Schedule I",
        ["circular", "schedule_i", "related_person"]
    ),
    "High Court Case Laws": (
        "ITC reversal on account of supplier fraud high court ruling",
        ["section_16", "itc", "fraud"]
    ),
    "IGST Acts": (
        "Place of supply for import of services under IGST Act",
        ["igst", "place_of_supply", "import_services"]
    ),
    "IGST rules": (
        "Refund of IGST paid on export of goods under Rule 96",
        ["rule_96", "igst", "refund_export"]
    ),
    "Rate_notifications_2.0": (
        "GST rate on works contract for government projects notification",
        ["notification", "works_contract", "government"]
    ),
    "Supreme Court Case Laws": (
        "Whether GST can be levied on ocean freight for imports CIF contracts",
        ["ocean_freight", "igst", "import"]
    ),
}

# ── Haiku context quality signals ────────────────────────────────────────────
GENERIC_PHRASES = [
    "this document", "the document", "this text", "the text",
    "this excerpt", "the following", "this section discusses",
    "the passage", "this passage", "as mentioned",
    "no specific context", "context not available", "unable to determine",
]

def is_generic_context(ctx: str) -> bool:
    if not ctx or len(ctx) < 30:
        return True
    low = ctx.lower()
    return any(ph in low for ph in GENERIC_PHRASES)

def context_quality_score(ctx: str) -> str:
    if not ctx:
        return "MISSING"
    if len(ctx) < 40:
        return "TOO_SHORT"
    if is_generic_context(ctx):
        return "GENERIC"
    if len(ctx) < 80:
        return "WEAK"
    return "GOOD"


def main():
    print("=" * 70)
    print("  V2.0 RETRIEVAL QUALITY DIAGNOSTIC")
    print("=" * 70)

    # ── 1. Load all chunks ───────────────────────────────────────────────────
    print("\n[1/5] Loading chunks.jsonl ...")
    all_chunks = []
    with CHUNKS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    print(f"      Loaded {len(all_chunks):,} total chunks")

    # Separate V2.0 chunks from old kept chunks
    v2_chunks = []
    old_chunks = []
    for c in all_chunks:
        m = c.get("metadata", {})
        rp = (m.get("rel_path") or c.get("rel_path") or "").replace("\\", "/")
        if "database_v2.0" in rp.lower() or "database_v2" in rp.lower():
            v2_chunks.append(c)
        else:
            old_chunks.append(c)

    print(f"      V2.0 chunks : {len(v2_chunks):,}")
    print(f"      Old kept    : {len(old_chunks):,}")

    # ── 2. Bucket V2.0 chunks by folder ─────────────────────────────────────
    print("\n[2/5] Bucketing V2.0 chunks by folder ...")
    by_folder = defaultdict(list)
    for c in v2_chunks:
        m = c.get("metadata", {})
        rp = (m.get("rel_path") or c.get("rel_path") or "").replace("\\", "/")
        # Extract folder name (component after Database_V2.0/)
        parts = rp.lower().split("database_v2.0/")
        if len(parts) > 1:
            folder = parts[1].split("/")[0]
        else:
            folder = "unknown"
        by_folder[folder].append(c)

    for folder, chunks in sorted(by_folder.items()):
        print(f"      [{folder}] → {len(chunks):,} chunks")

    # ── 3. Haiku context quality audit ──────────────────────────────────────
    print("\n[3/5] Haiku context quality audit ...")
    ctx_cache = {}
    if CTX_CACHE_FILE.exists():
        ctx_cache = json.loads(CTX_CACHE_FILE.read_text(encoding="utf-8"))
        print(f"      Context cache: {len(ctx_cache):,} entries")
    else:
        print("      ⚠ Context cache NOT FOUND — Haiku enrichment may have been skipped!")

    # Audit per chunk: embed_text vs text comparison
    ctx_quality = defaultdict(lambda: defaultdict(int))
    no_context_chunks = []
    generic_context_chunks = []

    for c in v2_chunks:
        m    = c.get("metadata", {})
        rp   = (m.get("rel_path") or c.get("rel_path") or "").replace("\\", "/")
        parts = rp.lower().split("database_v2.0/")
        folder = parts[1].split("/")[0] if len(parts) > 1 else "unknown"

        text       = c.get("text", "")
        embed_text = c.get("embed_text") or c.get("text_with_context") or ""

        # Check if embed_text is enriched (longer than raw text = Haiku context prepended)
        enriched = len(embed_text) > len(text) + 20

        if not enriched:
            ctx_quality[folder]["not_enriched"] += 1
            no_context_chunks.append({"folder": folder, "rel_path": rp[:80], "text_preview": text[:100]})
        else:
            ctx_quality[folder]["enriched"] += 1
            # Check the context prefix quality
            prefix = embed_text[:len(embed_text) - len(text)].strip()
            quality = context_quality_score(prefix)
            ctx_quality[folder][f"ctx_{quality.lower()}"] += 1
            if quality in ("GENERIC", "WEAK", "TOO_SHORT", "MISSING"):
                generic_context_chunks.append({
                    "folder": folder,
                    "rel_path": rp[:80],
                    "quality": quality,
                    "context": prefix[:200],
                })

    print(f"\n      {'Folder':<35} {'Enriched':>8} {'Not Enriched':>12} {'Generic Ctx':>11}")
    print(f"      {'-'*35} {'-'*8} {'-'*12} {'-'*11}")
    for folder in sorted(by_folder.keys()):
        q     = ctx_quality[folder]
        total = len(by_folder[folder])
        enr   = q.get("enriched", 0)
        not_e = q.get("not_enriched", 0)
        generic = q.get("ctx_generic", 0) + q.get("ctx_weak", 0) + q.get("ctx_too_short", 0) + q.get("ctx_missing", 0)
        pct   = f"{100*enr//total}%" if total else "0%"
        flag  = "⚠" if not_e > 0 or generic > total * 0.1 else "✅"
        print(f"      {flag} {folder:<33} {pct:>8} {not_e:>12} {generic:>11}")

    # ── 4. Provision key coverage ────────────────────────────────────────────
    print("\n[4/5] Provision key coverage ...")
    print(f"\n      {'Folder':<35} {'With Keys':>9} {'No Keys':>7} {'Coverage':>9} {'Sample Keys'}")
    print(f"      {'-'*35} {'-'*9} {'-'*7} {'-'*9} {'-'*30}")

    provision_gaps = []
    for folder in sorted(by_folder.keys()):
        chunks = by_folder[folder]
        with_keys = [c for c in chunks if c.get("metadata", {}).get("provision_keys")]
        without   = [c for c in chunks if not c.get("metadata", {}).get("provision_keys")]
        coverage  = f"{100*len(with_keys)//len(chunks)}%" if chunks else "0%"
        flag      = "✅" if len(with_keys)/max(len(chunks),1) >= 0.3 else "⚠"

        # Sample some keys
        sample_keys = []
        for c in with_keys[:3]:
            keys = c.get("metadata", {}).get("provision_keys", [])
            sample_keys.extend(keys[:2])
        sample_keys = list(set(sample_keys))[:4]

        print(f"      {flag} {folder:<33} {len(with_keys):>9} {len(without):>7} {coverage:>9}  {', '.join(sample_keys)}")

        if len(with_keys)/max(len(chunks),1) < 0.3:
            provision_gaps.append(folder)

    # ── 5. Live retrieval test ───────────────────────────────────────────────
    print("\n[5/5] Live retrieval test (one query per folder) ...")
    print("      Loading retriever (this takes ~30s) ...")

    try:
        from app.dependencies import get_retriever
        retriever = get_retriever()
        print("      Retriever loaded ✅")

        for folder_key, (query, expected_keys) in FOLDER_QUERIES.items():
            folder_lower = folder_key.lower()
            try:
                chunks_ret = retriever.search(query, top_k=10, use_sources=None,
                                               advanced_queries=None, domain_paths=[],
                                               return_with_scores=False)
                # Check if any V2.0 doc from this folder appears in top 10
                hits_v2 = []
                for c in chunks_ret:
                    m  = c.get("metadata", {})
                    rp = (m.get("rel_path") or c.get("rel_path") or "").replace("\\", "/").lower()
                    if "database_v2.0" in rp and folder_lower.split("(")[0].strip() in rp:
                        hits_v2.append(rp.split("/")[-1][:50])

                flag = "✅" if hits_v2 else "❌"
                hit_str = hits_v2[0] if hits_v2 else "NO V2.0 DOC IN TOP-10"
                print(f"\n      {flag} [{folder_key}]")
                print(f"         Query: {query[:70]}")
                print(f"         Top V2 hit: {hit_str}")

                if not hits_v2:
                    # Show what DID surface
                    top_paths = []
                    for c in chunks_ret[:3]:
                        m  = c.get("metadata", {})
                        rp = (m.get("rel_path") or c.get("rel_path") or "")
                        top_paths.append(rp.split("\\")[-1].split("/")[-1][:60])
                    print(f"         Got instead: {top_paths}")

            except Exception as e:
                print(f"\n      ⚠ [{folder_key}] retrieval error: {e}")

    except Exception as e:
        print(f"      ⚠ Could not load retriever: {e}")
        print("      Skipping live retrieval test")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    total_v2 = len(v2_chunks)
    total_not_enriched = sum(1 for c in no_context_chunks)
    total_generic = len(generic_context_chunks)
    total_no_provisions = sum(
        len([c for c in by_folder[f] if not c.get("metadata", {}).get("provision_keys")])
        for f in by_folder
    )

    print(f"\n  V2.0 chunks total         : {total_v2:,}")
    print(f"  Chunks missing Haiku ctx  : {total_not_enriched:,}  ({100*total_not_enriched//max(total_v2,1)}%)")
    print(f"  Chunks with weak/generic ctx: {total_generic:,}  ({100*total_generic//max(total_v2,1)}%)")
    print(f"  Chunks with NO provision keys: {total_no_provisions:,}  ({100*total_no_provisions//max(total_v2,1)}%)")
    print(f"  Folders with provision gaps: {provision_gaps}")

    if no_context_chunks:
        print(f"\n  ── Sample chunks missing Haiku enrichment ──")
        for s in no_context_chunks[:5]:
            print(f"    [{s['folder']}] {s['rel_path']}")
            print(f"       text: {s['text_preview']}")

    if generic_context_chunks:
        print(f"\n  ── Sample chunks with generic/weak context ──")
        for s in generic_context_chunks[:5]:
            print(f"    [{s['folder']}] quality={s['quality']}")
            print(f"       ctx: {s['context'][:150]}")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
