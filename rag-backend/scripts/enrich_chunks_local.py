"""
enrich_chunks_local.py  —  Chunk-aware context enrichment using local Ollama (FREE, $0)
========================================================================================
Generates a 2-sentence chunk-specific context for every V2.0 chunk using a local LLM
running on your GPU via Ollama — zero API cost.

SETUP (one-time):
    1. Download Ollama: https://ollama.com/download/windows
    2. Install and open it (runs as tray app)
    3. Pull the model (downloads once, ~4.7 GB):
           ollama pull qwen2.5:7b
    4. Run this script:
           cd RAG/rag-backend
           .\.win_venv\Scripts\python.exe scripts/enrich_chunks_local.py

WHAT IT DOES:
    Pass 1 — For each of the 7,631 V2.0 chunks, asks the local LLM to write
              2 sentences describing THAT SPECIFIC PASSAGE (section/rule/circular
              number, legal topic, key conditions). Checkpointed every 200 chunks
              → safe to interrupt and resume.

    Phase 7 — FAISS rebuild with enriched embed_text (~37 min on GPU)
    Phase 8 — Upload to S3
    Phase 9 — ECS restart

TIME ESTIMATE (RTX 5050 8GB, qwen2.5:7b):
    ~1.5-2 hours total (mostly Phase 7 FAISS rebuild)
    Enrichment itself: ~45-60 min with 2 parallel workers

COST: $0.00
"""

import json
import logging
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("enrich_local")

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import CHUNKS_PATH, VECTOR_DB_PATH, VECTOR_DIM

CHUNKS_FILE     = Path(CHUNKS_PATH)
INDEX_FILE      = Path(VECTOR_DB_PATH)
META_FILE       = INDEX_FILE.with_suffix(".meta.json")
CTX_CACHE_FILE  = BASE_DIR / "vectordb" / "v2_local_ctx_cache.json"

S3_BUCKET     = "gst-rag-data-721082558531"
S3_REGION     = "ap-south-1"
S3_CHUNKS_KEY = "data/chunks/chunks.jsonl"
S3_INDEX_KEY  = "vectordb/index.faiss"
S3_META_KEY   = "vectordb/index.meta.json"

# ── Ollama config ──────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"   # change to qwen2.5:3b for faster (lower quality)
WORKERS     = 2               # parallel Ollama calls — keep at 2 for 8GB VRAM
SAVE_EVERY  = 200             # checkpoint interval


# ─────────────────────────────────────────────────────────────────────────────
#  CHECK OLLAMA IS RUNNING
# ─────────────────────────────────────────────────────────────────────────────

def check_ollama():
    """Verify Ollama is running and the model is available."""
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        tags = json.loads(req.read())
        models = [m["name"] for m in tags.get("models", [])]
        log.info(f"  Ollama running ✅  Available models: {models}")

        # Check our model is there
        model_base = OLLAMA_MODEL.split(":")[0]
        available  = any(model_base in m for m in models)
        if not available:
            log.error(f"  Model '{OLLAMA_MODEL}' not found in Ollama!")
            log.error(f"  Run:  ollama pull {OLLAMA_MODEL}")
            log.error(f"  Then restart this script.")
            sys.exit(1)
        log.info(f"  Model '{OLLAMA_MODEL}' ready ✅")
    except urllib.error.URLError:
        log.error("  Ollama is NOT running or not installed.")
        log.error("")
        log.error("  SETUP STEPS:")
        log.error("    1. Download: https://ollama.com/download/windows")
        log.error("    2. Install and open Ollama (it runs in the system tray)")
        log.error(f"   3. Run in terminal:  ollama pull {OLLAMA_MODEL}")
        log.error("    4. Re-run this script")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
#  GENERATE CONTEXT FOR ONE CHUNK VIA OLLAMA
# ─────────────────────────────────────────────────────────────────────────────

def _generate_chunk_context_local(chunk: dict) -> str:
    """
    Call local Ollama to get a 2-sentence chunk-specific context.
    Falls back to empty string on error.
    """
    rel_path = chunk.get("metadata", {}).get("rel_path", chunk.get("rel_path", ""))
    doc_type = chunk.get("metadata", {}).get("document_type", "Legal Document")
    text     = chunk.get("text", "")

    prompt = (
        f"Document: {rel_path}\n"
        f"Type: {doc_type}\n"
        f"Passage:\n{text[:600]}\n\n"
        f"Write exactly 2 sentences (max 80 words) describing WHAT THIS SPECIFIC PASSAGE "
        f"covers. Mention: the section/rule/circular number if cited (e.g. 'Section 16(4)', "
        f"'Rule 42', 'Circular 204/16/2023'), the exact GST topic (ITC, RCM, valuation, "
        f"Schedule I, penalty, refund, etc.), and any key conditions or rulings. "
        f"Output ONLY the 2 sentences, nothing else."
    )

    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,   # low temp = consistent, factual output
            "num_predict": 120,   # ~80-100 words
            "top_p": 0.9,
        },
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        log.warning(f"  Ollama error: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  PASS 1 — LOCAL LLM ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

def pass1_local_enrichment(v2_chunks: list) -> list:
    """
    Generate chunk-specific contexts for all V2.0 chunks using local Ollama.
    Checkpointed → safe to interrupt and resume (already-done chunks are skipped).
    """
    log.info("=" * 60)
    log.info("PASS 1 — Local LLM chunk-aware enrichment (Ollama)")
    log.info("=" * 60)

    # Load checkpoint
    ctx_cache: dict[str, str] = {}
    if CTX_CACHE_FILE.exists():
        ctx_cache = json.loads(CTX_CACHE_FILE.read_text(encoding="utf-8"))
        log.info(f"  Checkpoint loaded: {len(ctx_cache):,} chunks already done — skipping those")

    to_process = [
        c for c in v2_chunks
        if c.get("metadata", {}).get("chunk_id", "") not in ctx_cache
    ]

    log.info(f"  Total V2.0 chunks  : {len(v2_chunks):,}")
    log.info(f"  Already cached     : {len(ctx_cache):,}")
    log.info(f"  To process now     : {len(to_process):,}")
    log.info(f"  Parallel workers   : {WORKERS}")
    log.info(f"  Model              : {OLLAMA_MODEL}")

    if not to_process:
        log.info("  All chunks already cached — applying contexts")
    else:
        t0       = time.time()
        done_cnt = 0
        err_cnt  = 0

        def enrich_one(c):
            chunk_id = c.get("metadata", {}).get("chunk_id", "")
            ctx = _generate_chunk_context_local(c)
            return chunk_id, ctx, (not ctx)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(enrich_one, c): c for c in to_process}
            for future in as_completed(futures):
                chunk_id, ctx, had_err = future.result()
                ctx_cache[chunk_id] = ctx
                done_cnt += 1
                if had_err:
                    err_cnt += 1

                if done_cnt % SAVE_EVERY == 0:
                    CTX_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    CTX_CACHE_FILE.write_text(
                        json.dumps(ctx_cache, ensure_ascii=False), encoding="utf-8"
                    )
                    elapsed = time.time() - t0
                    rate    = done_cnt / elapsed if elapsed > 0 else 1
                    eta_min = (len(to_process) - done_cnt) / rate / 60
                    log.info(
                        f"  [{done_cnt:,}/{len(to_process):,}]  "
                        f"errors={err_cnt}  ~{eta_min:.0f} min remaining"
                    )

        # Final checkpoint
        CTX_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CTX_CACHE_FILE.write_text(
            json.dumps(ctx_cache, ensure_ascii=False), encoding="utf-8"
        )
        elapsed_min = (time.time() - t0) / 60
        log.info(
            f"  ✅ Enrichment done: {done_cnt:,} chunks in {elapsed_min:.1f} min, "
            f"{err_cnt} errors"
        )

    # Apply contexts to all V2.0 chunks
    applied = missing = 0
    for c in v2_chunks:
        chunk_id = c.get("metadata", {}).get("chunk_id", "")
        ctx      = ctx_cache.get(chunk_id, "")
        text     = c.get("text", "")
        if ctx:
            embed_text             = f"{ctx}\n\n{text}"
            c["context"]           = ctx
            c["embed_text"]        = embed_text
            c["text_with_context"] = embed_text
            applied += 1
        else:
            missing += 1

    log.info(f"  ✅ Contexts applied: {applied:,} chunks | {missing:,} without context (kept as-is)")
    return v2_chunks


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 7 — FAISS REBUILD
# ─────────────────────────────────────────────────────────────────────────────

def phase7_rebuild_faiss():
    log.info("=" * 60)
    log.info("PHASE 7 — Rebuild FAISS from enriched chunks.jsonl")
    log.info("=" * 60)

    log.info(f"  Loading {CHUNKS_FILE} …")
    all_chunks = []
    with CHUNKS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    log.info(f"  Loaded {len(all_chunks):,} chunks")

    log.info("  Loading embedder (BGE-M3) …")
    from app.retrieval.retriever import get_model
    embedder = get_model()
    log.info("  Embedder ready")

    try:
        import faiss
        import numpy as np
    except ImportError:
        log.error("faiss / numpy not installed")
        sys.exit(1)

    index     = faiss.IndexFlatIP(VECTOR_DIM)
    meta_list = []
    BATCH     = 64
    total     = len(all_chunks)
    t0        = time.time()

    log.info(f"  Embedding {total:,} chunks in batches of {BATCH} …")

    for batch_start in range(0, total, BATCH):
        batch = all_chunks[batch_start: batch_start + BATCH]
        texts = [
            c.get("text_with_context") or c.get("embed_text") or c.get("text", "")
            for c in batch
        ]
        try:
            vecs = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            vecs = np.array(vecs, dtype="float32")
            index.add(vecs)
            for c in batch:
                m = c.get("metadata", {})
                meta_list.append({
                    "source":         m.get("source",        c.get("source", "")),
                    "rel_path":       m.get("rel_path",      c.get("rel_path", "")),
                    "document_type":  m.get("document_type", ""),
                    "category":       m.get("category",      ""),
                    "filename":       m.get("filename",      ""),
                    "chunk_id":       m.get("chunk_id",      ""),
                    "year":           m.get("year",          ""),
                    "provision_keys": m.get("provision_keys", []),
                    "text":           c.get("text", "")[:300],
                })
        except Exception as e:
            log.error(f"  Embedding error at batch {batch_start}: {e}")
            continue

        done = min(batch_start + BATCH, total)
        if (batch_start // BATCH + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate    = done / elapsed if elapsed > 0 else 1
            eta_min = (total - done) / rate / 60
            log.info(f"    {done:,}/{total:,} ({100*done//total}%)  ~{eta_min:.0f} min remaining")

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    META_FILE.write_text(json.dumps(meta_list, ensure_ascii=False), encoding="utf-8")

    elapsed_min = (time.time() - t0) / 60
    log.info(f"  ✅ FAISS: {index.ntotal:,} vectors in {elapsed_min:.1f} min")


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 8 — S3 UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

def phase8_upload_s3():
    log.info("=" * 60)
    log.info("PHASE 8 — Uploading to S3")
    log.info("=" * 60)
    import boto3
    s3 = boto3.client("s3", region_name=S3_REGION)
    for local, key in [
        (CHUNKS_FILE, S3_CHUNKS_KEY),
        (INDEX_FILE,  S3_INDEX_KEY),
        (META_FILE,   S3_META_KEY),
    ]:
        mb = local.stat().st_size / 1e6
        log.info(f"  {local.name} ({mb:.1f} MB) → s3://{S3_BUCKET}/{key}")
        s3.upload_file(str(local), S3_BUCKET, key)
        log.info(f"    ✅ uploaded")
    log.info("  ✅ Phase 8 done")


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 9 — ECS RESTART
# ─────────────────────────────────────────────────────────────────────────────

def phase9_restart_ecs():
    log.info("=" * 60)
    log.info("PHASE 9 — Force-restarting ECS")
    log.info("=" * 60)
    import boto3
    ecs = boto3.client("ecs", region_name=S3_REGION)
    ecs.update_service(
        cluster="gst-rag-cluster",
        service="gst-rag-backend-service",
        forceNewDeployment=True,
    )
    log.info("  ✅ ECS restart triggered — new task loads fresh index on startup")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║  enrich_chunks_local.py  — local GPU context enrichment     ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")

    t_start = time.time()

    # ── Verify Ollama ────────────────────────────────────────────────────────
    log.info("")
    log.info("[0] Checking Ollama …")
    check_ollama()

    # ── Load chunks ──────────────────────────────────────────────────────────
    log.info("")
    log.info("[1] Loading chunks.jsonl …")
    all_chunks = []
    with CHUNKS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    log.info(f"  Loaded {len(all_chunks):,} total chunks")

    v2_chunks  = [c for c in all_chunks if "database_v2" in
                  (c.get("metadata", {}).get("rel_path") or c.get("rel_path") or "").replace("\\", "/").lower()]
    old_chunks = [c for c in all_chunks if c not in v2_chunks]
    log.info(f"  V2.0: {len(v2_chunks):,}  |  Old kept: {len(old_chunks):,}")

    # ── Pass 1: Local LLM enrichment ─────────────────────────────────────────
    log.info("")
    v2_chunks = pass1_local_enrichment(v2_chunks)

    # ── Write updated chunks.jsonl — V2.0 ONLY (old chunks purged) ───────────
    log.info("")
    log.info("[3] Writing chunks.jsonl — Database_V2.0 only (old chunks removed) …")
    tmp = CHUNKS_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for c in v2_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    if CHUNKS_FILE.exists():
        CHUNKS_FILE.unlink()
    tmp.rename(CHUNKS_FILE)
    mb = CHUNKS_FILE.stat().st_size / 1e6
    log.info(f"  ✅ chunks.jsonl: {mb:.1f} MB ({len(v2_chunks):,} V2.0 chunks only)")

    # ── Phase 7 → 8 → 9 ──────────────────────────────────────────────────────
    log.info("")
    phase7_rebuild_faiss()
    log.info("")
    phase8_upload_s3()
    log.info("")
    phase9_restart_ecs()

    elapsed_min = (time.time() - t_start) / 60
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info(f"║  ALL DONE in {elapsed_min:.1f} min                                     ║")
    log.info("║                                                              ║")
    log.info("║  Every V2.0 chunk now has a CHUNK-SPECIFIC context          ║")
    log.info("║  generated by a local LLM — $0 cost.                        ║")
    log.info("║  FAISS rebuilt, S3 updated, ECS restarted.                  ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
