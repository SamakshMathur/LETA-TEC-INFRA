"""
Incremental Ingestion Pipeline
-------------------------------
Processes ONLY newly uploaded files, appends their vectors to the existing
FAISS index, and appends their chunks to chunks.jsonl.

This means a single PDF upload takes ~30 seconds instead of hours.
"""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict

try:
    import faiss
except ImportError:
    faiss = None  # type: ignore  # CI env; only fails if index load/write is attempted
import numpy as np

from app.config import DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH
from app.ingestion.legal_parser import LegalParser
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.docx_reader import extract_text_from_docx
from app.ingestion.excel_reader import extract_text_from_excel
from app.ingestion.clean_text import clean_text

_S3_BUCKET = os.getenv("S3_DATA_BUCKET", "")
_S3_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
_S3_DOCS_PREFIX = "documents"   # matches app.api.documents.S3_DOCS_PREFIX

# The document *library* listing file — a different thing from this module's
# own META_FILE (index.meta.json, one entry per FAISS-indexed chunk). This
# one is what app.api.documents reads to show a document in /list/* and to
# resolve /view's S3 lookup. Kept in sync here on every admin upload —
# previously nothing updated it, so an uploaded file was searchable right
# away but invisible in the library and its "View PDF" button 404'd, until
# a full offline metadata regen + container restart happened to pick it up.
_DOC_META_FILE = Path(DATA_DIR) / "document_metadata.json"

# Set ENABLE_CONTEXTUAL_ENRICHMENT=true in ECS task definition to enable
# per-chunk Haiku context enrichment on admin-upload ingestion.
# Off by default — each chunk costs one Haiku API call (~$0.0003) and adds
# ~2-5s per chunk; appropriate for nightly batch jobs, not real-time uploads.
_ENRICHMENT_ENABLED = os.getenv("ENABLE_CONTEXTUAL_ENRICHMENT", "false").lower() == "true"

logger = logging.getLogger(__name__)

CHUNKS_FILE = Path(CHUNKS_PATH)
INDEX_FILE  = Path(VECTOR_DB_PATH)
META_FILE   = INDEX_FILE.with_suffix(".meta.json")
DATA_ROOT   = Path(DATA_DIR)


# ── Step 1: Extract text from a single file ───────────────────────────────────

def _extract_pages(file_path: Path, rel_path: str) -> List[Dict]:
    ext = file_path.suffix.lower()
    cls_info = LegalParser.classify_folder(rel_path)

    try:
        if ext == ".pdf":
            pages = extract_text_from_pdf(str(file_path))
            if not pages or sum(len(p.get("text", "")) for p in pages) < 100:
                from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
                pages = extract_text_from_scanned_pdf(str(file_path))
        elif ext == ".docx":
            pages = extract_text_from_docx(file_path)
        elif ext in (".xlsx", ".xls"):
            pages = extract_text_from_excel(file_path)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []

        # Clean text before chunking: normalize unicode, strip mojibake, collapse
        # whitespace.  Also filter out pages that were previously stored as the
        # "[OCR_EMPTY_PAGE]" sentinel — pdf_scanned.py now omits them at source,
        # but old files in the pipeline may still carry the sentinel.
        clean_pages = []
        for p in pages:
            raw_text = p.get("text", "")
            if not raw_text or raw_text.strip() == "[OCR_EMPTY_PAGE]":
                continue
            p["text"] = clean_text(raw_text)
            p["metadata"] = p.get("metadata", {})
            p["metadata"].update(cls_info)
            p["metadata"]["rel_path"] = rel_path
            p["metadata"]["source"]   = str(file_path)
            clean_pages.append(p)

        return clean_pages

    except Exception as e:
        logger.error(f"Extraction failed for {file_path}: {e}")
        return []


# ── Step 2: Chunk the extracted pages ─────────────────────────────────────────

def _chunk_pages(pages: List[Dict]) -> List[Dict]:
    if not pages:
        return []

    full_text   = "\n".join(p["text"] for p in pages)
    first_meta  = pages[0]["metadata"]
    doc_type    = first_meta.get("document_type", "Other")
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

        import re
        raw_section_nums = [
            re.search(r'\d+', c).group()
            for c in normalized_citations
            if "SEC" in c and re.search(r'\d+', c)
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


# ── Step 3: Embed + append to FAISS ───────────────────────────────────────────

def _embed_and_append(chunks: List[Dict]) -> int:
    if not chunks:
        return 0

    from app.embeddings.embedder import embed_texts

    # Use context-enriched text when available (set by enrich_document_chunks).
    # Falls back to raw chunk text when enrichment was skipped or failed.
    texts      = [c.get("text_with_context") or c["text"] for c in chunks]
    embeddings = embed_texts(texts).astype("float32")

    # Load existing index (or create fresh if missing)
    if INDEX_FILE.exists():
        index = faiss.read_index(str(INDEX_FILE))
    else:
        from app.config import VECTOR_DIM
        index = faiss.IndexFlatIP(VECTOR_DIM)  # must match retriever's inner-product search

    # Load existing metadata
    existing_meta: list = []
    if META_FILE.exists():
        with META_FILE.open(encoding="utf-8") as f:
            existing_meta = json.load(f)

    # Append
    index.add(embeddings)
    new_meta = [c.get("metadata", {}) | {"chunk_id": c["chunk_id"]} for c in chunks]
    existing_meta.extend(new_meta)

    # Save
    faiss.write_index(index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(existing_meta, f, ensure_ascii=False)

    logger.info(f"FAISS index updated: +{len(chunks)} vectors → total {index.ntotal}")
    return len(chunks)


# ── Step 4: Append to chunks.jsonl ────────────────────────────────────────────

def _append_to_chunks_file(chunks: List[Dict]):
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")


# ── S3 persistence ────────────────────────────────────────────────────────────

def _persist_to_s3():
    """Upload the updated FAISS index and chunks.jsonl back to S3 so the next
    ECS task restart picks them up instead of re-downloading the stale versions."""
    if not _S3_BUCKET:
        return
    try:
        import boto3
        s3 = boto3.client("s3", region_name=_S3_REGION)
        for local, key in [
            (INDEX_FILE,  "vectordb/index.faiss"),
            (META_FILE,   "vectordb/index.meta.json"),
            (CHUNKS_FILE, "data/chunks/chunks.jsonl"),
        ]:
            if local.exists():
                s3.upload_file(str(local), _S3_BUCKET, key)
                logger.info(f"Persisted {local.name} → s3://{_S3_BUCKET}/{key}")
    except Exception as e:
        logger.warning(f"S3 persistence failed (index still updated in-memory): {e}")


# ── Document-library registration ─────────────────────────────────────────────
# Makes an admin-uploaded file behave like every other document in the
# library, not just a searchable-but-otherwise-invisible set of vectors:
# pushes the raw file to where /view's S3 fallback looks for it, and adds
# it to the metadata list /list/* reads from (local file + S3 + the live
# in-process cache, so it appears without a restart).

def _register_document(file_path: Path, rel_path: str, year: str = None, filename: str = None) -> None:
    folder = rel_path.split("/")[0] if "/" in rel_path else rel_path.split("\\")[0]
    # file_path may be a temp on-disk path (e.g. the knowledge-upload flow's
    # <uuid>_<original name>.pdf) — filename lets the caller give the real,
    # user-facing name instead of that temp path's own basename.
    filename = filename or file_path.name

    # 1. Raw file → S3, at the exact key app.api.documents' /view endpoint
    #    looks up (S3_DOCS_PREFIX/<folder>/<filename>). Without this the file
    #    only ever existed on the container's local disk — gone on the next
    #    restart, and never found by /view even before that.
    if _S3_BUCKET:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=_S3_REGION)
            s3.upload_file(str(file_path), _S3_BUCKET, f"{_S3_DOCS_PREFIX}/{rel_path}")
            logger.info(f"Persisted document → s3://{_S3_BUCKET}/{_S3_DOCS_PREFIX}/{rel_path}")
        except Exception as e:
            logger.warning(f"Document S3 upload failed (still ingested/searchable): {e}")

    # 2. Library metadata entry — same shape as the bulk-generated ones.
    # Re-derive category/document_type/source from rel_path directly rather
    # than trust first_meta's copies: _extract_pages/_extract_text sets
    # metadata["source"] = str(file_path) right after classify_folder() set
    # it to the real authority ("CBIC"/"Judiciary"/"Official"), silently
    # clobbering it (both ingestion paths, pre-existing, not introduced
    # here) — same dict key used for two different things. Re-classifying
    # here keeps this entry correct regardless of that separate bug.
    classified = LegalParser.classify_folder(rel_path)
    entry = {
        "id": f"{classified.get('category', 'other')}_{filename}",
        "title": Path(filename).stem,
        "filename": filename,
        "size": f"{round(file_path.stat().st_size / 1024, 1)} KB",
        "path": rel_path,
        "folder": folder,
        "category": classified.get("category", "other"),
        "year": year or "other",
        "source": classified.get("source", "General"),
        "document_type": classified.get("document_type", "Other"),
    }

    try:
        existing: list = []
        if _DOC_META_FILE.exists():
            with _DOC_META_FILE.open(encoding="utf-8") as f:
                existing = json.load(f)
        existing.append(entry)
        _DOC_META_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _DOC_META_FILE.open("w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False)

        if _S3_BUCKET:
            import boto3
            s3 = boto3.client("s3", region_name=_S3_REGION)
            s3.upload_file(str(_DOC_META_FILE), _S3_BUCKET, "data/document_metadata.json")
            logger.info("Persisted document_metadata.json → S3")
    except Exception as e:
        logger.warning(f"document_metadata.json update failed: {e}")

    # 3. Hot-update the live process's in-memory copy so it shows up in
    #    /list/* immediately, same idea as reload_retriever() below.
    try:
        from app.api.documents import append_to_metadata_cache
        append_to_metadata_cache(entry)
    except Exception as e:
        logger.warning(f"In-memory metadata cache update failed (restart to pick up): {e}")


# ── Public entry point ────────────────────────────────────────────────────────

def ingest_file(file_path: Path, rel_path: str, year: str = None) -> Dict:
    """
    Full incremental pipeline for a single uploaded file.
    Returns a status dict: {chunks_added, vectors_added, status}
    """
    logger.info(f"Incremental ingest: {rel_path}")

    pages  = _extract_pages(file_path, rel_path)
    if not pages:
        return {"chunks_added": 0, "vectors_added": 0, "status": "no_text_extracted"}

    chunks = _chunk_pages(pages)
    if not chunks:
        return {"chunks_added": 0, "vectors_added": 0, "status": "no_chunks_generated"}

    # Optional per-chunk contextual enrichment (Anthropic Contextual Retrieval).
    # When enabled, each chunk gets a Haiku-generated 1-2 sentence context that
    # situates it within its source document.  embed_text (context + raw text) is
    # what gets encoded into the FAISS vector; text is preserved for display.
    # ~49% retrieval failure reduction per Anthropic's published benchmark.
    if _ENRICHMENT_ENABLED:
        try:
            from app.chunking.contextual_enricher import enrich_document_chunks
            full_text = "\n\n".join(p.get("text", "") for p in pages)
            chunks = enrich_document_chunks(chunks, full_text, rel_path)
            logger.info(f"Contextual enrichment complete for {rel_path}")
        except Exception as exc:
            logger.warning(f"Contextual enrichment failed — continuing without it: {exc}")

    _append_to_chunks_file(chunks)
    vectors_added = _embed_and_append(chunks)

    # Persist updated index to S3 so it survives ECS task restarts
    _persist_to_s3()

    # Register the raw file + library metadata so it's viewable/browsable,
    # not just searchable (see _register_document's docstring for why this
    # was a separate, previously-missing step).
    _register_document(file_path, rel_path, year=year)

    # Signal the live retriever to reload so new docs are searchable immediately
    try:
        from app.dependencies import reload_retriever
        reload_retriever()
        logger.info("Retriever hot-reloaded after incremental ingest")
    except Exception as e:
        logger.warning(f"Retriever reload failed (restart server to pick up changes): {e}")

    return {
        "chunks_added":  len(chunks),
        "vectors_added": vectors_added,
        "status":        "success",
    }
