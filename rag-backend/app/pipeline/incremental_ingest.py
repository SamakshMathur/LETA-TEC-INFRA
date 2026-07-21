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

import faiss
import numpy as np

from app.config import DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH
from app.ingestion.legal_parser import LegalParser
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.docx_reader import extract_text_from_docx
from app.ingestion.excel_reader import extract_text_from_excel

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

        for p in pages:
            p["metadata"] = p.get("metadata", {})
            p["metadata"].update(cls_info)
            p["metadata"]["rel_path"] = rel_path
            p["metadata"]["source"]   = str(file_path)

        return pages

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

    texts      = [c["text"] for c in chunks]
    embeddings = embed_texts(texts).astype("float32")

    # Load existing index (or create fresh if missing)
    if INDEX_FILE.exists():
        index = faiss.read_index(str(INDEX_FILE))
    else:
        from app.config import VECTOR_DIM
        index = faiss.IndexFlatL2(VECTOR_DIM)

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


# ── Public entry point ────────────────────────────────────────────────────────

def ingest_file(file_path: Path, rel_path: str) -> Dict:
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

    _append_to_chunks_file(chunks)
    vectors_added = _embed_and_append(chunks)

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
