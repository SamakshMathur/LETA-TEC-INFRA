"""
Ingest 22 remaining files (Excel indices + Response Templates) into FAISS.
Skips only the two competitor output docs (wrong answer / wrong logic).
After ingestion, uploads updated FAISS + chunks.jsonl to S3 and restarts ECS.

Run from: RAG/rag-backend/
    python scripts/ingest_22_and_push.py

Time estimate: 15-30 min depending on CPU speed.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# ── Windows long-path helpers ─────────────────────────────────────────────────
_WIN = sys.platform == "win32"

def _ext_path(p: Path) -> str:
    """
    Return an extended-length path string safe to pass to open() and Python
    libraries on Windows.  Paths >= 256 chars exceed the default MAX_PATH (260)
    so we prepend the \\?\\ prefix which bypasses that limit.

    Verified: python-docx (via zipfile) accepts this prefix on Windows.
    No-op on non-Windows or for short paths.
    """
    s = str(p.resolve())
    if _WIN and len(s) >= 256:
        return "\\\\?\\\\" + s  # \\?\\ + absolute path
    return s

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_22")

from app.config import DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH, VECTOR_DIM

DB_ROOT     = Path(DATA_DIR)
CHUNKS_FILE = Path(CHUNKS_PATH)
INDEX_FILE  = Path(VECTOR_DB_PATH)
META_FILE   = INDEX_FILE.with_suffix(".meta.json")

_SUPPORTED_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls"}

# Only skip the two competitor output files that contain wrong legal answers.
# Excel index files ARE included — they contain real GST content.
_SKIP_EXACT = {
    "Other APP Result/CHATGPT_ITC on Bike_Wrong Answer.docx",
    "Other APP Result/GORK_ITC on Bike_Right Answer but wrong Logic.docx",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _all_db_files() -> list:
    """Return all ingestible rel_paths in the DB folder."""
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


def _ingested_rel_paths() -> set:
    """rel_paths already in chunks.jsonl."""
    seen = set()
    if not CHUNKS_FILE.exists():
        return seen
    with CHUNKS_FILE.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                c = json.loads(line)
                rp = (
                    c.get("rel_path") or c.get("metadata", {}).get("rel_path", "")
                ).replace("\\", "/")
                if rp:
                    seen.add(rp)
            except Exception:
                pass
    return seen


# ── Extraction + chunking (mirrors incremental_ingest pipeline) ───────────────

def _extract_pages(file_path: Path, rel_path: str) -> list:
    from app.ingestion.legal_parser import LegalParser
    from app.ingestion.pdf_text import extract_text_from_pdf
    from app.ingestion.docx_reader import extract_text_from_docx
    from app.ingestion.excel_reader import extract_text_from_excel

    ext = file_path.suffix.lower()
    cls_info = LegalParser.classify_folder(rel_path)

    # On Windows, paths ≥ 256 chars exceed MAX_PATH and fail with FileNotFoundError.
    # Prepending \\?\\ bypasses the limit (verified working with python-docx/zipfile).
    safe_path = _ext_path(file_path)

    try:
        if ext == ".pdf":
            pages = extract_text_from_pdf(safe_path)
        elif ext == ".docx":
            pages = extract_text_from_docx(safe_path)
        elif ext in (".xlsx", ".xls"):
            pages = extract_text_from_excel(safe_path)
        else:
            logger.warning(f"Unsupported ext {ext} — skipping")
            return []

        for p in pages:
            p["metadata"] = p.get("metadata", {})
            p["metadata"].update(cls_info)
            p["metadata"]["rel_path"] = rel_path
            p["metadata"]["source"]   = str(file_path)

        # Drop empty pages
        return [p for p in pages if p.get("text", "").strip()]

    except Exception as e:
        logger.error(f"Extract failed [{rel_path}]: {e}")
        return []


def _chunk_pages(pages: list) -> list:
    import re
    from app.ingestion.legal_parser import LegalParser

    if not pages:
        return []

    full_text  = "\n".join(p["text"] for p in pages)
    first_meta = pages[0]["metadata"]
    doc_type   = first_meta.get("document_type", "Other")
    chunks_data = LegalParser.structural_split(full_text, doc_type)

    chunks = []
    for idx, chunk_obj in enumerate(chunks_data):
        text      = chunk_obj["text"].strip()
        structure = chunk_obj["structure"]
        if not text:
            continue

        raw_citations        = LegalParser.extract_citations(text, normalize=False)
        normalized_citations = LegalParser.extract_citations(text, normalize=True)
        topic                = LegalParser.classify_topic(text)
        primary_provisions   = [c for c in normalized_citations if "SEC" in c or "RUL" in c]

        raw_section_nums = [
            re.search(r"\d+", c).group()
            for c in normalized_citations
            if "SEC" in c and re.search(r"\d+", c)
        ]
        law_type = "general"
        if any(s in LegalParser.SUBSTANTIVE_SECTIONS for s in raw_section_nums):
            law_type = "substantive"
        elif any(s in LegalParser.PROCEDURAL_SECTIONS for s in raw_section_nums):
            law_type = "procedural"

        full_meta = {
            **first_meta,
            "topic":       topic,
            "law_type":    law_type,
            "citations":   normalized_citations,
            "raw_citations": raw_citations,
            "provisions":  primary_provisions,
            "section_type": structure,
        }
        chunk_id = LegalParser.generate_chunk_id(full_meta, structure, text, idx)
        chunks.append({
            "chunk_id": chunk_id,
            "text":     text,
            "metadata": full_meta,
            "source":   first_meta.get("source", ""),
            "rel_path": first_meta.get("rel_path", ""),
        })
    return chunks


def _embed_and_append(chunks: list) -> int:
    """Embed chunks and append to FAISS + meta file."""
    if not chunks:
        return 0

    import faiss
    from app.embeddings.embedder import embed_texts

    texts      = [c["text"] for c in chunks]
    embeddings = embed_texts(texts).astype("float32")

    if INDEX_FILE.exists():
        index = faiss.read_index(str(INDEX_FILE))
    else:
        index = faiss.IndexFlatIP(VECTOR_DIM)

    existing_meta = []
    if META_FILE.exists():
        with META_FILE.open(encoding="utf-8") as f:
            existing_meta = json.load(f)

    index.add(embeddings)
    new_meta = [{**c.get("metadata", {}), "chunk_id": c["chunk_id"]} for c in chunks]
    existing_meta.extend(new_meta)

    faiss.write_index(index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(existing_meta, f, ensure_ascii=False)

    return index.ntotal


# ── S3 upload ─────────────────────────────────────────────────────────────────

def upload_to_s3():
    bucket = os.getenv("S3_DATA_BUCKET", "gst-rag-data-721082558531")
    region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    logger.info(f"Uploading to s3://{bucket} ...")

    import boto3
    s3 = boto3.client("s3", region_name=region)

    uploads = [
        (INDEX_FILE,  "vectordb/index.faiss"),
        (META_FILE,   "vectordb/index.meta.json"),
        (CHUNKS_FILE, "data/chunks/chunks.jsonl"),
    ]
    for local, key in uploads:
        if local.exists():
            logger.info(f"  Uploading {local.name}  ({local.stat().st_size/1024/1024:.1f} MB) ...")
            s3.upload_file(str(local), bucket, key)
            logger.info(f"  uploaded OK  -> s3://{bucket}/{key}")
    logger.info("S3 upload done.")


# ── ECS restart ───────────────────────────────────────────────────────────────

def restart_ecs():
    import boto3
    region  = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    cluster = "gst-rag-cluster"
    service = "gst-rag-backend-service"
    logger.info(f"Triggering ECS force-new-deployment ({cluster}/{service}) ...")
    client = boto3.client("ecs", region_name=region)
    resp = client.update_service(
        cluster=cluster,
        service=service,
        forceNewDeployment=True,
    )
    svc_name = resp["service"]["serviceName"]
    logger.info(f"  ECS restart triggered for service: {svc_name}")
    logger.info("  New task will download fresh FAISS from S3 on startup.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()
    logger.info("=" * 60)
    logger.info("LETA — Ingest 22 remaining files")
    logger.info("=" * 60)

    all_files = _all_db_files()
    ingested  = _ingested_rel_paths()
    missing   = sorted(set(all_files) - ingested)

    logger.info(f"DB folder   : {len(all_files)} ingestible files")
    logger.info(f"Already done: {len(ingested)} files")
    logger.info(f"To ingest   : {len(missing)} files")
    logger.info("")

    if not missing:
        logger.info("All files already ingested — nothing to do.")
        return

    # Show the list up front
    for i, rel in enumerate(missing, 1):
        logger.info(f"  [{i:2d}] {rel}")
    logger.info("")

    ok = fail = skipped = 0
    total_chunks = 0

    for i, rel in enumerate(missing, 1):
        abs_path = DB_ROOT / rel.replace("/", os.sep)
        logger.info(f"── [{i:2d}/{len(missing)}] {rel}")

        pages = _extract_pages(abs_path, rel)
        if not pages:
            logger.warning(f"     No text extracted — skipping")
            skipped += 1
            continue

        chunks = _chunk_pages(pages)
        if not chunks:
            logger.warning(f"     No chunks generated — skipping")
            skipped += 1
            continue

        # Append to chunks.jsonl
        CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CHUNKS_FILE.open("a", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")

        # Embed and update FAISS
        try:
            total_vectors = _embed_and_append(chunks)
            total_chunks += len(chunks)
            logger.info(f"     {len(chunks)} chunks  |  FAISS total: {total_vectors:,}")
            ok += 1
        except Exception as e:
            logger.error(f"     Embedding failed: {e}")
            fail += 1

    elapsed = (time.time() - t_start) / 60
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Ingestion done — ok={ok}  skipped={skipped}  fail={fail}")
    logger.info(f"New chunks added: {total_chunks:,}")
    logger.info(f"Time: {elapsed:.1f} min")
    logger.info("=" * 60)

    if fail > 0:
        logger.warning(f"{fail} file(s) failed embedding — still uploading what succeeded.")

    # Upload to S3
    upload_to_s3()

    # Restart ECS so new task picks up fresh FAISS
    restart_ecs()

    total_elapsed = (time.time() - t_start) / 60
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"ALL DONE — Total time: {total_elapsed:.1f} min")
    logger.info("LETA will be live with updated index in ~2-3 minutes.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
