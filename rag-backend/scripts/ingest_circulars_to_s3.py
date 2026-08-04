"""
Ingest all year-subfolder circulars (2017-2025) into the FAISS index and upload to S3.

Run from rag-backend/ with:
  .\.venv_win\Scripts\python.exe scripts\ingest_circulars_to_s3.py

Steps:
  1. Download current chunks.jsonl + index.faiss from S3
  2. Find all year-subfolder circular PDFs not yet indexed
  3. Extract, chunk, embed, append
  4. Upload updated files back to S3
  5. Set FORCE_DATA_DOWNLOAD=1 on ECS task definition and force deploy
"""

import json
import logging
import os
import sys
from pathlib import Path
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Resolve paths ─────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR.parent                          # rag-backend/
sys.path.insert(0, str(BASE_DIR))

CIRCULARS_ROOT = BASE_DIR / "RAG_INFORMATION_DATABASE" / "Circulars" / "circulars"
CHUNKS_FILE    = BASE_DIR / "data" / "chunks" / "chunks.jsonl"
INDEX_FILE     = BASE_DIR / "vectordb" / "index.faiss"
META_FILE      = INDEX_FILE.with_suffix(".meta.json")

S3_BUCKET      = "gst-rag-data-721082558531"
S3_REGION      = "ap-south-1"
S3_CHUNKS_KEY  = "data/chunks/chunks.jsonl"
S3_INDEX_KEY   = "vectordb/index.faiss"
S3_META_KEY    = "vectordb/index.meta.json"


# ── Step 0: Download fresh S3 base files ─────────────────────────────────────

def download_from_s3():
    import boto3
    s3 = boto3.client("s3", region_name=S3_REGION)

    for local_path, s3_key in [
        (CHUNKS_FILE, S3_CHUNKS_KEY),
        (INDEX_FILE,  S3_INDEX_KEY),
        (META_FILE,   S3_META_KEY),
    ]:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"Downloading s3://{S3_BUCKET}/{s3_key} → {local_path}")
        s3.download_file(S3_BUCKET, s3_key, str(local_path))
        log.info(f"  Done: {local_path.stat().st_size / 1e6:.1f} MB")


# ── Step 1: Find already-indexed sources ─────────────────────────────────────

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
                src_norm = src.replace("\\", "/").lower()
                if src_norm:
                    indexed.add(src_norm)
            except Exception:
                pass
    log.info(f"Existing indexed sources: {len(indexed)}")
    return indexed


# ── Step 2: Collect missing PDFs ─────────────────────────────────────────────

def find_missing_pdfs(indexed: set):
    missing = []
    years = sorted([d.name for d in CIRCULARS_ROOT.iterdir() if d.is_dir()])
    log.info(f"Year folders found: {years}")

    for year_dir in sorted(CIRCULARS_ROOT.iterdir()):
        if not year_dir.is_dir():
            continue
        for pdf in sorted(year_dir.glob("*.pdf")):
            norm = str(pdf).replace("\\", "/").lower()
            if norm not in indexed:
                missing.append(pdf)

    counts = Counter(p.parent.name for p in missing)
    log.info(f"Missing PDFs by year: {dict(sorted(counts.items()))}")
    log.info(f"Total missing: {len(missing)}")
    return missing


# ── Step 3: Ingest each missing PDF ──────────────────────────────────────────

def ingest_pdf(pdf_path: Path) -> list:
    import fitz  # PyMuPDF

    rel_path = str(pdf_path.relative_to(BASE_DIR / "RAG_INFORMATION_DATABASE")).replace("\\", "/")
    year     = pdf_path.parent.name

    # Extract text
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        log.warning(f"  Cannot open {pdf_path.name}: {e}")
        return []

    pages_text = []
    for page in doc:
        t = page.get_text().strip()
        if t:
            pages_text.append(t)
    doc.close()

    if not pages_text:
        log.warning(f"  No text extracted from {pdf_path.name}")
        return []

    full_text = "\n\n".join(pages_text)

    # Simple chunking: 1500-char windows with 200-char overlap
    chunks = []
    step   = 1300
    window = 1500
    text_len = len(full_text)

    for i, start in enumerate(range(0, max(1, text_len - 200), step)):
        chunk_text = full_text[start: start + window].strip()
        if len(chunk_text) < 80:
            continue

        import hashlib
        chunk_id = hashlib.md5(f"{rel_path}_{i}".encode()).hexdigest()[:16]

        chunks.append({
            "chunk_id": chunk_id,
            "text":     chunk_text,
            "source":   str(pdf_path),
            "rel_path": f"Circulars/circulars/{year}/{pdf_path.name}",
            "metadata": {
                "source":        str(pdf_path),
                "rel_path":      f"Circulars/circulars/{year}/{pdf_path.name}",
                "document_type": "Circular",
                "year":          year,
                "filename":      pdf_path.name,
                "category":      "circulars",
                "chunk_id":      chunk_id,
            },
        })

    return chunks


# ── Step 4: Embed + append to FAISS ──────────────────────────────────────────

def embed_and_append(all_new_chunks: list):
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    log.info("Loading BAAI/bge-large-en-v1.5 model...")
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    log.info("Model loaded.")

    # Load existing index
    index = faiss.read_index(str(INDEX_FILE))
    log.info(f"Existing FAISS index: {index.ntotal} vectors")

    # Load existing meta — handle trailing garbage bytes
    with META_FILE.open(encoding="utf-8", errors="replace") as f:
        raw = f.read().strip()
    # Find the last valid closing bracket
    last_bracket = raw.rfind("]")
    if last_bracket != -1:
        raw = raw[: last_bracket + 1]
    try:
        meta_list = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("index.meta.json could not be parsed; starting with empty metadata list")
        meta_list = []

    # Process in batches of 64
    BATCH = 64
    total_added = 0
    for batch_start in range(0, len(all_new_chunks), BATCH):
        batch = all_new_chunks[batch_start: batch_start + BATCH]
        texts = [c["text"] for c in batch]

        log.info(f"  Embedding batch {batch_start // BATCH + 1} / {(len(all_new_chunks) + BATCH - 1) // BATCH} ({len(texts)} chunks)...")
        embs = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        embs = embs.astype("float32")

        index.add(embs)
        meta_list.extend([c["metadata"] for c in batch])
        total_added += len(batch)

    log.info(f"FAISS index after ingestion: {index.ntotal} vectors (+{total_added})")

    # Save
    faiss.write_index(index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False)
    log.info("FAISS index + meta saved locally.")


# ── Step 5: Append to chunks.jsonl ───────────────────────────────────────────

def append_to_chunks(all_new_chunks: list):
    with CHUNKS_FILE.open("a", encoding="utf-8") as f:
        for c in all_new_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    log.info(f"Appended {len(all_new_chunks)} chunks to {CHUNKS_FILE.name}")


# ── Step 6: Upload to S3 ─────────────────────────────────────────────────────

def upload_to_s3():
    import boto3
    s3 = boto3.client("s3", region_name=S3_REGION)

    for local_path, s3_key in [
        (CHUNKS_FILE, S3_CHUNKS_KEY),
        (INDEX_FILE,  S3_INDEX_KEY),
        (META_FILE,   S3_META_KEY),
    ]:
        size_mb = local_path.stat().st_size / 1e6
        log.info(f"Uploading {local_path.name} ({size_mb:.1f} MB) → s3://{S3_BUCKET}/{s3_key}")
        s3.upload_file(str(local_path), S3_BUCKET, s3_key)
        log.info(f"  Uploaded.")


# ── Step 7: Force ECS restart ─────────────────────────────────────────────────

def restart_ecs():
    import boto3
    ecs = boto3.client("ecs", region_name=S3_REGION)

    log.info("Forcing new ECS deployment with FORCE_DATA_DOWNLOAD=1...")
    # Get current task definition
    svc = ecs.describe_services(cluster="gst-rag-cluster", services=["gst-rag-backend-service"])
    task_def_arn = svc["services"][0]["taskDefinition"]
    log.info(f"Current task definition: {task_def_arn}")

    # Force new deployment (ECS will restart tasks and re-download S3 files)
    ecs.update_service(
        cluster="gst-rag-cluster",
        service="gst-rag-backend-service",
        forceNewDeployment=True,
    )
    log.info("ECS service force-redeployed. New tasks will download updated index from S3.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("CIRCULAR INGESTION PIPELINE")
    log.info("=" * 60)

    # 0. Download fresh S3 base
    log.info("\n[1/7] Downloading base files from S3...")
    download_from_s3()

    # 1. Find already indexed
    log.info("\n[2/7] Scanning existing index for circular sources...")
    indexed = get_indexed_sources()

    # 2. Find missing PDFs
    log.info("\n[3/7] Scanning year-subfolder circular PDFs...")
    missing_pdfs = find_missing_pdfs(indexed)

    if not missing_pdfs:
        log.info("All circulars already indexed. Nothing to do.")
        return

    # 3. Extract + chunk all missing PDFs
    log.info(f"\n[4/7] Extracting and chunking {len(missing_pdfs)} PDFs...")
    all_new_chunks = []
    for i, pdf in enumerate(missing_pdfs, 1):
        log.info(f"  [{i}/{len(missing_pdfs)}] {pdf.parent.name}/{pdf.name}")
        chunks = ingest_pdf(pdf)
        all_new_chunks.extend(chunks)

    log.info(f"Total new chunks: {len(all_new_chunks)}")

    if not all_new_chunks:
        log.error("No chunks extracted from any PDF. Check the PDFs.")
        return

    # 4. Append to chunks.jsonl
    log.info("\n[5/7] Appending to chunks.jsonl...")
    append_to_chunks(all_new_chunks)

    # 5. Embed + update FAISS
    log.info("\n[6/7] Embedding and updating FAISS index...")
    embed_and_append(all_new_chunks)

    # 6. Upload to S3
    log.info("\n[7/7] Uploading updated files to S3...")
    upload_to_s3()

    # 7. Restart ECS
    log.info("\nRestarting ECS service...")
    restart_ecs()

    log.info("\n" + "=" * 60)
    log.info("DONE — circulars indexed and ECS restarting.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
