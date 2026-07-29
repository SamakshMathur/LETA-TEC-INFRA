"""
Ingest ALL missing documents from RAG_INFORMATION_DATABASE into FAISS and upload to S3.

Supports resume: if killed mid-run, restart and it picks up from the last checkpoint.

Run from rag-backend/ with:
  .\.venv_win\Scripts\python.exe scripts\ingest_all_to_s3.py

Files used for resume:
  vectordb/pending_chunks.jsonl   — extracted chunks waiting to be embedded
  vectordb/ingest_checkpoint.json — {batch_completed, total} saved every 20 batches
  vectordb/index.checkpoint.faiss — FAISS state at last checkpoint
  vectordb/index.checkpoint.meta.json
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

DB_ROOT     = BASE_DIR / "RAG_INFORMATION_DATABASE"
CHUNKS_FILE = BASE_DIR / "data" / "chunks" / "chunks.jsonl"
INDEX_FILE  = BASE_DIR / "vectordb" / "index.faiss"
META_FILE   = INDEX_FILE.with_suffix(".meta.json")

# Resume/checkpoint files
PENDING_FILE      = BASE_DIR / "vectordb" / "pending_chunks.jsonl"
CHECKPOINT_FILE   = BASE_DIR / "vectordb" / "ingest_checkpoint.json"
INDEX_CKPT        = BASE_DIR / "vectordb" / "index.checkpoint.faiss"
META_CKPT         = BASE_DIR / "vectordb" / "index.checkpoint.meta.json"

S3_BUCKET     = "gst-rag-data-721082558531"
S3_REGION     = "ap-south-1"
S3_CHUNKS_KEY = "data/chunks/chunks.jsonl"
S3_INDEX_KEY  = "vectordb/index.faiss"
S3_META_KEY   = "vectordb/index.meta.json"

CATEGORIES = [
    ("Notification",            "Notification", "notifications"),
    ("AAR",                     "AAR",          "aar"),
    ("High Court Case Laws",    "Case Law",     "highcourt"),
    ("Supreme Court Case Laws", "Case Law",     "supremecourt"),
    ("Responses",               "Response",     "responses"),
    ("Act",                     "Act",          "acts"),
    ("CGST",                    "CGST Act",     "cgst"),
    ("IGST",                    "IGST Act",     "igst"),
    ("Rules",                   "Rules",        "rules"),
    ("Forms",                   "Form",         "forms"),
    ("FAQs",                    "FAQ",          "faqs"),
    ("Brochures",               "Brochure",     "brochures"),
    ("ICAI",                    "ICAI",         "icai"),
    ("Export",                  "Export",       "export"),
    ("Circulars",               "Circular",     "circulars"),
]

SKIP_FOLDERS   = {"generated_reports", "Other APP Result"}
CHECKPOINT_EVERY = 20


# ── S3 ─────────────────────────────────────────────────────────────────────────

def download_from_s3():
    import boto3
    s3 = boto3.client("s3", region_name=S3_REGION)
    for local, key in [
        (CHUNKS_FILE, S3_CHUNKS_KEY),
        (INDEX_FILE,  S3_INDEX_KEY),
        (META_FILE,   S3_META_KEY),
    ]:
        local.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"  {key} → {local.name}")
        s3.download_file(S3_BUCKET, key, str(local))
        log.info(f"    {local.stat().st_size / 1e6:.1f} MB")


def upload_to_s3():
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


def restart_ecs():
    import boto3
    ecs = boto3.client("ecs", region_name=S3_REGION)
    svc = ecs.describe_services(cluster="gst-rag-cluster", services=["gst-rag-backend-service"])
    log.info(f"  Task def: {svc['services'][0]['taskDefinition']}")
    ecs.update_service(cluster="gst-rag-cluster", service="gst-rag-backend-service", forceNewDeployment=True)
    log.info("  ECS force-redeploy triggered.")


# ── Index helpers ──────────────────────────────────────────────────────────────

def get_indexed_sources() -> set:
    indexed = set()
    if not CHUNKS_FILE.exists():
        return indexed
    with CHUNKS_FILE.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                c = json.loads(line)
                src = (c.get("source") or c.get("rel_path") or
                       c.get("metadata", {}).get("source") or
                       c.get("metadata", {}).get("rel_path") or "")
                norm = src.replace("\\", "/").lower()
                if norm:
                    indexed.add(norm)
            except Exception:
                pass
    log.info(f"Existing indexed source paths: {len(indexed)}")
    return indexed


def load_meta(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace") as f:
        raw = f.read().strip()
    last = raw.rfind("]")
    if last != -1:
        raw = raw[:last + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning(f"{path.name} unparseable — using empty list")
        return []


# ── Checkpointing ──────────────────────────────────────────────────────────────

def save_checkpoint(batch_idx: int, total: int, index, meta_list: list):
    import faiss
    faiss.write_index(index, str(INDEX_CKPT))
    with META_CKPT.open("w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False)
    CHECKPOINT_FILE.write_text(json.dumps({
        "batch_completed": batch_idx,
        "total_chunks":    total,
        "saved_at":        time.time(),
    }))
    log.info(f"  [CHECKPOINT] Saved after batch {batch_idx} ({(batch_idx+1)*64}/{total} chunks done)")


def load_checkpoint():
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        return json.loads(CHECKPOINT_FILE.read_text())
    except Exception:
        return None


def cleanup_checkpoint():
    for f in [PENDING_FILE, CHECKPOINT_FILE, INDEX_CKPT, META_CKPT]:
        if f.exists():
            f.unlink()
    log.info("Checkpoint files cleaned up.")


# ── Per-file ingestion ─────────────────────────────────────────────────────────

def _extract_year(path: Path):
    for part in path.parts:
        if part.isdigit() and 2010 <= int(part) <= 2030:
            return part
    return None


def ingest_pdf(pdf_path: Path, document_type: str, category_key: str) -> list:
    import fitz
    import hashlib

    rel_path = str(pdf_path.relative_to(DB_ROOT)).replace("\\", "/")
    year     = _extract_year(pdf_path)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        log.warning(f"  Cannot open {pdf_path.name}: {e}")
        return []

    pages_text = [page.get_text().strip() for page in doc if page.get_text().strip()]
    doc.close()

    if not pages_text:
        log.warning(f"  No text: {pdf_path.name}")
        return []

    full_text = "\n\n".join(pages_text)
    WINDOW, STEP = 1500, 1300
    chunks = []
    for i, start in enumerate(range(0, max(1, len(full_text) - 200), STEP)):
        text = full_text[start: start + WINDOW].strip()
        if len(text) < 80:
            continue
        chunk_id = hashlib.md5(f"{rel_path}_{i}".encode()).hexdigest()[:16]
        meta = {
            "source": str(pdf_path), "rel_path": rel_path,
            "document_type": document_type, "category": category_key,
            "filename": pdf_path.name, "chunk_id": chunk_id,
        }
        if year:
            meta["year"] = year
        chunks.append({"chunk_id": chunk_id, "text": text,
                        "source": str(pdf_path), "rel_path": rel_path, "metadata": meta})
    return chunks


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_and_append_all(all_new_chunks: list, resume_from_batch: int = 0):
    import faiss
    from sentence_transformers import SentenceTransformer

    log.info("Loading BAAI/bge-large-en-v1.5 model...")
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    log.info("Model loaded.")

    # Load from checkpoint if resuming, else from S3-downloaded base
    if resume_from_batch > 0 and INDEX_CKPT.exists():
        log.info(f"Resuming from checkpoint (batch {resume_from_batch})...")
        index     = faiss.read_index(str(INDEX_CKPT))
        meta_list = load_meta(META_CKPT)
    else:
        index     = faiss.read_index(str(INDEX_FILE))
        meta_list = load_meta(META_FILE)

    log.info(f"FAISS base: {index.ntotal} vectors")

    BATCH = 64
    total = len(all_new_chunks)
    batches = (total + BATCH - 1) // BATCH
    total_added = 0

    for b_idx, start in enumerate(range(0, total, BATCH)):
        # Skip already-done batches when resuming
        if b_idx < resume_from_batch:
            continue

        batch = all_new_chunks[start: start + BATCH]
        texts = [c["text"] for c in batch]
        log.info(f"  Embedding batch {b_idx + 1}/{batches} ({len(texts)} chunks)...")

        embs = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        embs = embs.astype("float32")
        index.add(embs)
        meta_list.extend([c["metadata"] for c in batch])
        total_added += len(batch)

        # Checkpoint every N batches
        if (b_idx + 1) % CHECKPOINT_EVERY == 0:
            save_checkpoint(b_idx, total, index, meta_list)

    log.info(f"FAISS after: {index.ntotal} vectors (+{total_added})")
    faiss.write_index(index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False)
    log.info("FAISS index + meta saved locally.")
    return total_added


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 70)
    log.info("LETA FULL DATABASE INGESTION PIPELINE (with resume support)")
    log.info("=" * 70)

    checkpoint = load_checkpoint()
    resuming   = checkpoint is not None and PENDING_FILE.exists() and INDEX_CKPT.exists()

    if resuming:
        resume_from = checkpoint["batch_completed"] + 1
        log.info(f"\nRESUMING from batch {resume_from} (checkpoint saved at "
                 f"{time.strftime('%H:%M:%S', time.localtime(checkpoint['saved_at']))})")

        log.info("\n[SKIP] S3 download (using local checkpoint files)")
        log.info("\n[SKIP] PDF extraction (using pending_chunks.jsonl)")

        log.info(f"\nLoading {PENDING_FILE.name}...")
        all_new_chunks = []
        with PENDING_FILE.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    all_new_chunks.append(json.loads(line))
                except Exception:
                    pass
        log.info(f"Loaded {len(all_new_chunks)} pending chunks.")

    else:
        resume_from = 0

        # 1. Download fresh S3 base
        log.info("\n[1/5] Downloading latest S3 base files...")
        download_from_s3()

        # 2. Build indexed source set
        log.info("\n[2/5] Scanning existing index...")
        indexed = get_indexed_sources()

        # 3. Discover + extract all missing PDFs
        log.info("\n[3/5] Auditing all categories...")
        missing_by_cat: dict = defaultdict(list)
        grand_total_disk = 0

        for folder_name, doc_type, cat_key in CATEGORIES:
            cat_root = DB_ROOT / folder_name
            if not cat_root.exists():
                log.warning(f"  {folder_name}: NOT FOUND — skipping")
                continue
            all_pdfs = [
                p for p in cat_root.rglob("*.pdf")
                if p.is_file() and not any(sk in p.parts for sk in SKIP_FOLDERS)
            ]
            grand_total_disk += len(all_pdfs)
            missing = [p for p in sorted(all_pdfs)
                       if str(p).replace("\\", "/").lower() not in indexed]
            if missing:
                missing_by_cat[folder_name] = (missing, doc_type, cat_key)
            log.info(f"  {folder_name:<30} disk={len(all_pdfs):>4}  "
                     f"indexed={len(all_pdfs)-len(missing):>4}  MISSING={len(missing):>4}")

        total_missing = sum(len(v[0]) for v in missing_by_cat.values())
        log.info(f"\n  Disk total: {grand_total_disk} | Missing: {total_missing}")

        if total_missing == 0:
            log.info("All documents already indexed.")
            return

        log.info(f"\n[4/5] Extracting and chunking {total_missing} PDFs...")
        all_new_chunks = []
        grand_idx = 0
        for folder_name, (pdfs, doc_type, cat_key) in missing_by_cat.items():
            log.info(f"\n  === {folder_name} ({len(pdfs)} files) ===")
            for pdf in pdfs:
                grand_idx += 1
                log.info(f"  [{grand_idx}/{total_missing}] {pdf.relative_to(DB_ROOT)}")
                all_new_chunks.extend(ingest_pdf(pdf, doc_type, cat_key))

        log.info(f"\nTotal chunks extracted: {len(all_new_chunks)}")

        if not all_new_chunks:
            log.error("No chunks produced. Check PDFs.")
            return

        # Save pending chunks for resume capability
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PENDING_FILE.open("w", encoding="utf-8") as f:
            for c in all_new_chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        log.info(f"Pending chunks saved to {PENDING_FILE.name} (resume-safe)")

        # Append new chunks to chunks.jsonl
        log.info("\nAppending to chunks.jsonl...")
        CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CHUNKS_FILE.open("a", encoding="utf-8") as f:
            for c in all_new_chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        log.info(f"  Appended {len(all_new_chunks)} chunks.")

    # Embed + update FAISS (with checkpointing)
    log.info(f"\n[{'RESUME' if resuming else '5'}/5] Embedding {len(all_new_chunks)} chunks "
             f"({'resuming from' if resuming else 'starting at'} batch {resume_from})...")
    embed_and_append_all(all_new_chunks, resume_from_batch=resume_from)

    # Upload to S3
    log.info("\nUploading updated files to S3...")
    upload_to_s3()

    # Restart ECS
    log.info("\nRestarting ECS service...")
    restart_ecs()

    # Cleanup checkpoint files
    cleanup_checkpoint()

    log.info("\n" + "=" * 70)
    log.info(f"DONE — ECS restarting with complete knowledge base.")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
