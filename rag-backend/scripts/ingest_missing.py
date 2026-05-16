"""
Incremental ingestion of the 156 files not yet in the index.
Appends to documents.jsonl, chunks.jsonl, and FAISS without touching
the existing vectors — so the server stays live during the run.

Run from: RAG/rag-backend/
    python scripts/ingest_missing.py
"""
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Tesseract path for scanned PDF OCR
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH, VECTOR_DIM
from app.ingestion.legal_parser import LegalParser
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
from app.ingestion.docx_reader import extract_text_from_docx, extract_text_from_doc
from app.ingestion.excel_reader import extract_text_from_excel
from app.utils.legal_cleaner import LegalCleaner
import re

DOCS_FILE   = Path(CHUNKS_PATH).parent / "documents.jsonl"
CHUNKS_FILE = Path(CHUNKS_PATH)
INDEX_FILE  = Path(VECTOR_DB_PATH)
META_FILE   = INDEX_FILE.with_suffix(".meta.json")
DATA_ROOT   = Path(DATA_DIR)


# ── 1. Find which files are not yet indexed ───────────────────────────────────

def find_missing_files():
    indexed = set()
    with DOCS_FILE.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                rp = json.loads(line).get("metadata", {}).get("rel_path", "")
                if rp:
                    indexed.add(rp)
            except Exception:
                pass

    missing = []
    for p in DATA_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.name.startswith("._"):
            continue
        rel = str(p.relative_to(DATA_ROOT))
        if rel not in indexed:
            missing.append((rel, p))
    return missing


# ── 2. Extract text from a single file ───────────────────────────────────────

def extract_pages(file_path: Path, rel_path: str):
    ext = file_path.suffix.lower()
    try:
        if ext == ".pdf":
            pages = extract_text_from_pdf(str(file_path))
            # If no selectable text, fall back to OCR
            total_chars = sum(len(p.get("text", "").strip()) for p in pages)
            if total_chars < 50:
                print("  (scanned PDF — using OCR)")
                pages = extract_text_from_scanned_pdf(str(file_path))
                # Filter out OCR empty-page markers
                pages = [p for p in pages if p.get("text", "").strip() not in ("", "[OCR_EMPTY_PAGE]")]
        elif ext == ".docx":
            pages = extract_text_from_docx(file_path)
        elif ext == ".doc":
            pages = extract_text_from_doc(file_path)
        elif ext in (".xlsx", ".xls"):
            pages = extract_text_from_excel(file_path)
        else:
            return []

        cls_info = LegalParser.classify_folder(rel_path)
        for p in pages:
            p["metadata"] = p.get("metadata", {})
            p["metadata"].update(cls_info)
            p["metadata"]["rel_path"] = rel_path
            p["metadata"]["source"]   = str(file_path)
            p["text"] = LegalCleaner.clean(p.get("text", ""))
        return [p for p in pages if p.get("text", "").strip()]
    except Exception as e:
        print(f"  ! Extract error ({rel_path}): {e}")
        return []


# ── 3. Chunk pages into legal chunks ──────────────────────────────────────────

def chunk_pages(pages):
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


# ── 4. Embed new chunks and append to FAISS ───────────────────────────────────

def embed_and_append(chunks):
    if not chunks:
        return 0

    import faiss
    import numpy as np
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

    return len(chunks)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    missing = find_missing_files()
    print(f"Files not yet indexed: {len(missing)}")
    if not missing:
        print("Nothing to do — all files are already indexed.")
        return

    total_chunks = 0
    total_vectors = 0
    errors = 0

    for i, (rel_path, file_path) in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] {rel_path}")

        # Extract
        pages = extract_pages(file_path, rel_path)
        if not pages:
            print("  - no text extracted, skipping")
            continue

        # Append raw pages to documents.jsonl
        with DOCS_FILE.open("a", encoding="utf-8") as f:
            for p in pages:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

        # Chunk
        chunks = chunk_pages(pages)
        if not chunks:
            print("  - no chunks generated, skipping")
            continue

        # Append to chunks.jsonl
        with CHUNKS_FILE.open("a", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        # Embed and append to FAISS
        try:
            vectors = embed_and_append(chunks)
            total_chunks  += len(chunks)
            total_vectors += vectors
            print(f"  + {len(chunks)} chunks, {vectors} vectors")
        except Exception as e:
            print(f"  ! Embedding error: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"Done. Added {total_chunks} chunks / {total_vectors} vectors from {len(missing)-errors} files.")
    print(f"Errors: {errors}")
    print(f"FAISS index now at: {INDEX_FILE}")


if __name__ == "__main__":
    run()
