"""
Full Contextual Rebuild Pipeline
==================================
Phase 1 — Ingest every file not yet in chunks.jsonl
Phase 2 — Enrich ALL chunks with a Haiku-generated context prefix (checkpointed)
Phase 3 — Re-embed every chunk (text_with_context) and rebuild FAISS from scratch
Phase 4 — Push updated index + chunks to S3

Run from rag-backend/:
    python scripts/full_contextual_rebuild.py

Estimated time  : 3-5 hours  (local embedding is the main bottleneck)
Estimated cost  : $12-18 USD  (Claude Haiku context generation for ~60K chunks)

The script is safe to interrupt and re-run — Phase 2 uses a checkpoint file
(data/chunks/enrich_checkpoint.json) so already-enriched documents are skipped.
"""

import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# ── Bootstrap imports ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("contextual_rebuild")

from app.config import (
    DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH, VECTOR_DIM,
    ANTHROPIC_API_KEY,
)

DB_ROOT        = Path(DATA_DIR)
CHUNKS_FILE    = Path(CHUNKS_PATH)
INDEX_FILE     = Path(VECTOR_DB_PATH)
META_FILE      = INDEX_FILE.with_suffix(".meta.json")
ENRICHED_FILE  = CHUNKS_FILE.parent / "chunks_enriched.jsonl"
CHECKPOINT     = CHUNKS_FILE.parent / "enrich_checkpoint.json"

_SUPPORTED_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls"}

# Files that are pure index/reference — skip ingestion
_SKIP_EXACT = {
    "Sections List.xlsx",
    "AAR/AAR Details.xlsx",
    "Circulars/Circular Details.xlsx",
    # Competitor app outputs — not GST law, would confuse the model
    "Other APP Result/CHATGPT_ITC on Bike_Wrong Answer.docx",
    "Other APP Result/GORK_ITC on Bike_Right Answer but wrong Logic.docx",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _all_db_files() -> list[str]:
    """All ingestible rel_paths in the DB folder (deduplicated, sorted)."""
    found = set()
    for root, _, files in os.walk(DB_ROOT):
        if "__MACOSX" in root:
            continue
        for f in files:
            if f.startswith(".") or f.startswith("._") or f.startswith("~$"):
                continue
            if Path(f).suffix.lower() not in _SUPPORTED_EXT:
                continue
            rel = str(Path(root, f).relative_to(DB_ROOT)).replace("\\", "/")
            if rel in _SKIP_EXACT:
                continue
            found.add(rel)
    return sorted(found)


def _ingested_rel_paths() -> set[str]:
    """rel_paths already recorded in chunks.jsonl."""
    seen: set[str] = set()
    if not CHUNKS_FILE.exists():
        return seen
    with CHUNKS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                c = json.loads(line)
                rp = (
                    c.get("rel_path")
                    or c.get("metadata", {}).get("rel_path", "")
                ).replace("\\", "/")
                if rp:
                    seen.add(rp)
            except Exception:
                pass
    return seen


def _load_checkpoint() -> set[str]:
    """Load set of already-enriched document rel_paths."""
    if CHECKPOINT.exists():
        try:
            with CHECKPOINT.open(encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_checkpoint(done: set[str]):
    with CHECKPOINT.open("w", encoding="utf-8") as f:
        json.dump(sorted(done), f)


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — INGEST MISSING FILES
# ═══════════════════════════════════════════════════════════════════════════════

def phase1_ingest():
    logger.info("━" * 60)
    logger.info("PHASE 1 — Ingest missing files")
    logger.info("━" * 60)

    all_files = _all_db_files()
    ingested  = _ingested_rel_paths()
    missing   = sorted(set(all_files) - ingested)

    logger.info(f"DB folder    : {len(all_files)} files")
    logger.info(f"Already done : {len(ingested)} files")
    logger.info(f"To ingest    : {len(missing)} files")

    if not missing:
        logger.info("All files already ingested — skipping Phase 1.")
        return

    # Import pipeline — suppress per-file S3 uploads (we do one at the end)
    from app.pipeline import incremental_ingest as _ii
    _orig_s3 = _ii._persist_to_s3
    _ii._persist_to_s3 = lambda: None   # monkeypatch for Phase 1

    try:
        ok = fail = 0
        for i, rel in enumerate(missing, 1):
            abs_path = DB_ROOT / rel.replace("/", os.sep)
            logger.info(f"  [{i:3d}/{len(missing)}] {rel}")
            try:
                result = _ii.ingest_file(abs_path, rel)
                status = result.get("status", "?")
                n      = result.get("chunks_added", 0)
                logger.info(f"             → {status}  ({n} chunks)")
                if status == "success":
                    ok += 1
                else:
                    logger.warning(f"             ⚠ non-success: {rel}")
                    fail += 1
            except Exception as e:
                logger.error(f"             ✗ FAILED: {e}")
                fail += 1
    finally:
        _ii._persist_to_s3 = _orig_s3  # restore

    logger.info(f"Phase 1 done — ✓ {ok}  ✗ {fail}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — CONTEXTUAL ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════

def phase2_enrich():
    logger.info("━" * 60)
    logger.info("PHASE 2 — Contextual enrichment (Haiku context prefixes)")
    logger.info("━" * 60)

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set — cannot run enrichment.")
        sys.exit(1)

    # Load all chunks
    logger.info("Loading chunks.jsonl …")
    all_chunks: list[dict] = []
    with CHUNKS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                all_chunks.append(json.loads(line))
            except Exception:
                pass
    logger.info(f"Loaded {len(all_chunks):,} chunks")

    # Group by document (rel_path)
    doc_map: dict[str, list[dict]] = defaultdict(list)
    for chunk in all_chunks:
        rp = (
            chunk.get("rel_path")
            or chunk.get("metadata", {}).get("rel_path", "")
        ).replace("\\", "/")
        doc_map[rp].append(chunk)

    all_docs = sorted(doc_map.keys())
    logger.info(f"Unique documents: {len(all_docs)}")

    # Estimate API cost
    avg_input_tokens = 900   # doc context ~500 + chunk ~300 + prompt ~100
    avg_output_tokens = 100
    haiku_in_price  = 0.80   # $/MTok
    haiku_out_price = 4.00   # $/MTok
    n = len(all_chunks)
    est_cost = (n * avg_input_tokens / 1_000_000 * haiku_in_price
                + n * avg_output_tokens / 1_000_000 * haiku_out_price)
    logger.info(f"Estimated API cost: ${est_cost:.1f}  ({n:,} chunks × Haiku)")
    logger.info("Starting enrichment — checkpoint saves after each document.")
    logger.info("")

    # Resume from checkpoint
    done_docs = _load_checkpoint()
    remaining = [d for d in all_docs if d not in done_docs]
    logger.info(f"Already enriched : {len(done_docs)} docs")
    logger.info(f"Remaining        : {len(remaining)} docs")

    from app.chunking.contextual_enricher import enrich_document_chunks

    # Open enriched output in append mode (safe to resume)
    enriched_all: list[dict] = []

    # If resuming, load already-enriched chunks from ENRICHED_FILE
    if ENRICHED_FILE.exists() and done_docs:
        logger.info("Resuming — loading previously enriched chunks …")
        with ENRICHED_FILE.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    enriched_all.append(json.loads(line))
                except Exception:
                    pass
        logger.info(f"Loaded {len(enriched_all):,} already-enriched chunks")

    total_docs    = len(all_docs)
    completed_idx = len(done_docs)

    for rel_path in remaining:
        completed_idx += 1
        doc_chunks = doc_map[rel_path]
        doc_type   = doc_chunks[0].get("metadata", {}).get("document_type", "document") if doc_chunks else "document"

        # Build document text from all chunks of this source
        doc_text = " ".join(c["text"] for c in doc_chunks)

        logger.info(f"  [{completed_idx:4d}/{total_docs}] {rel_path}  ({len(doc_chunks)} chunks)")

        try:
            enriched_doc = enrich_document_chunks(
                doc_chunks,
                document_text=doc_text,
                rel_path=rel_path,
                max_workers=8,
            )
            enriched_all.extend(enriched_doc)
            done_docs.add(rel_path)

            # Append newly enriched doc chunks to file
            with ENRICHED_FILE.open("a", encoding="utf-8") as fh:
                for ec in enriched_doc:
                    fh.write(json.dumps(ec, ensure_ascii=False) + "\n")

            # Save checkpoint after each document
            _save_checkpoint(done_docs)

        except Exception as e:
            logger.error(f"  ✗ Enrichment failed for {rel_path}: {e}")
            # Still add un-enriched chunks so nothing is lost
            for c in doc_chunks:
                c.setdefault("context", "")
                c.setdefault("text_with_context", c["text"])
            enriched_all.extend(doc_chunks)
            done_docs.add(rel_path)
            _save_checkpoint(done_docs)

    logger.info(f"Phase 2 done — {len(enriched_all):,} chunks enriched")
    return enriched_all


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — REBUILD FAISS
# ═══════════════════════════════════════════════════════════════════════════════

def phase3_rebuild_faiss(enriched_chunks: list[dict]):
    logger.info("━" * 60)
    logger.info("PHASE 3 — Rebuild FAISS index from enriched chunks")
    logger.info("━" * 60)

    import faiss
    import numpy as np
    from app.embeddings.embedder import embed_texts

    n = len(enriched_chunks)
    logger.info(f"Embedding {n:,} chunks with text_with_context …")

    # Use text_with_context for embedding; fall back to text
    texts = [c.get("text_with_context") or c.get("text", "") for c in enriched_chunks]

    # Embed in batches and show progress
    batch_size = 256
    all_embeddings = []
    t0 = time.time()

    for i in range(0, n, batch_size):
        batch = texts[i: i + batch_size]
        emb   = embed_texts(batch).astype("float32")
        all_embeddings.append(emb)
        elapsed = time.time() - t0
        done    = min(i + batch_size, n)
        pct     = done / n * 100
        eta     = (elapsed / done * (n - done)) if done > 0 else 0
        logger.info(f"  Embedded {done:6,}/{n:,}  ({pct:.1f}%)  ETA {eta/60:.1f} min")

    embeddings = np.vstack(all_embeddings).astype("float32")
    logger.info(f"Embeddings shape: {embeddings.shape}")

    # Build fresh inner-product index (cosine-equivalent on normalized vecs)
    logger.info("Building FAISS IndexFlatIP …")
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(embeddings)
    logger.info(f"Index total vectors: {index.ntotal:,}")

    # Build metadata list (one entry per vector, same order as embeddings)
    meta_list = []
    for c in enriched_chunks:
        m = dict(c.get("metadata", {}))
        m["chunk_id"]         = c.get("chunk_id", "")
        m["context"]          = c.get("context", "")
        meta_list.append(m)

    # Save
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False)
    logger.info(f"Saved → {INDEX_FILE}")
    logger.info(f"Saved → {META_FILE}")

    # Replace chunks.jsonl with enriched version (atomic-ish rename)
    logger.info("Replacing chunks.jsonl with enriched version …")
    backup = CHUNKS_FILE.with_suffix(".jsonl.bak")
    CHUNKS_FILE.rename(backup)
    ENRICHED_FILE.rename(CHUNKS_FILE)
    logger.info(f"chunks.jsonl updated  (backup at {backup.name})")

    # Clean up checkpoint
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()
    logger.info("Phase 3 done.")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 4 — S3 UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════

def phase4_upload_s3():
    logger.info("━" * 60)
    logger.info("PHASE 4 — Push to S3")
    logger.info("━" * 60)

    import os
    bucket = os.getenv("S3_DATA_BUCKET", "")
    if not bucket:
        logger.warning("S3_DATA_BUCKET not set — skipping S3 upload.")
        return

    import boto3
    region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    s3 = boto3.client("s3", region_name=region)

    uploads = [
        (INDEX_FILE,  "vectordb/index.faiss"),
        (META_FILE,   "vectordb/index.meta.json"),
        (CHUNKS_FILE, "data/chunks/chunks.jsonl"),
    ]
    for local, key in uploads:
        if local.exists():
            logger.info(f"  Uploading {local.name} → s3://{bucket}/{key}")
            s3.upload_file(str(local), bucket, key)
            logger.info(f"  ✓ {key}")

    logger.info("Phase 4 done — S3 upload complete.")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    t_start = time.time()
    logger.info("=" * 60)
    logger.info("LETA — Full Contextual Rebuild")
    logger.info("=" * 60)

    phase1_ingest()
    enriched = phase2_enrich()
    phase3_rebuild_faiss(enriched)
    phase4_upload_s3()

    elapsed = (time.time() - t_start) / 60
    logger.info("=" * 60)
    logger.info(f"ALL PHASES COMPLETE — Total time: {elapsed:.1f} minutes")
    logger.info("=" * 60)
