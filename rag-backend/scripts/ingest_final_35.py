"""
Targeted ingestion of the 35 remaining un-indexed files.
Run from: RAG/rag-backend/
    python scripts/ingest_final_35.py
"""
import sys, os, json, re, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Tesseract OCR setup ───────────────────────────────────────────────────────
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except ImportError:
    pytesseract = None

from pathlib import Path

DATA_DIR    = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\RAG_INFORMATION_DATABASE")
DOCS_FILE   = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\documents.jsonl")
CHUNKS_FILE = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\chunks.jsonl")
INDEX_FILE  = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\vectordb\index.faiss")
VECTOR_DIM  = 1024


# ── 1. Find missing files ────────────────────────────────────────────────────
def get_indexed_set():
    indexed = set()
    with DOCS_FILE.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                rp = json.loads(line).get("metadata", {}).get("rel_path", "")
                if rp:
                    indexed.add(rp)
            except Exception:
                pass
    return indexed


def find_missing(indexed):
    missing = []
    for p in DATA_DIR.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.name.startswith("._") or p.name.startswith("~$"):
            continue
        ext = p.suffix.lower()
        if ext not in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            continue
        try:
            rel = str(p.relative_to(DATA_DIR))
        except Exception:
            continue
        if rel not in indexed:
            missing.append((rel, p))
    return missing


# ── 2. Extract text ───────────────────────────────────────────────────────────
def extract_text(file_path: Path, rel_path: str):
    ext = file_path.suffix.lower()
    pages = []

    try:
        if ext == ".pdf":
            from app.ingestion.pdf_text import extract_text_from_pdf
            raw_pages = extract_text_from_pdf(str(file_path))
            total = sum(len(p.get("text", "").strip()) for p in raw_pages)
            if total < 50 and pytesseract is not None:
                print("    (scanned PDF — using OCR low_memory mode)")
                from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
                raw_pages = extract_text_from_scanned_pdf(str(file_path), low_memory=True)
                raw_pages = [p for p in raw_pages
                             if p.get("text", "").strip() not in ("", "[OCR_EMPTY_PAGE]")]
            pages = [p for p in raw_pages if p.get("text", "").strip()]

        elif ext == ".docx":
            from app.ingestion.docx_reader import extract_text_from_docx
            pages = extract_text_from_docx(file_path)

        elif ext == ".doc":
            from app.ingestion.docx_reader import extract_text_from_doc
            pages = extract_text_from_doc(file_path)

        elif ext in (".xlsx", ".xls"):
            from app.ingestion.excel_reader import extract_text_from_excel
            pages = extract_text_from_excel(file_path)

    except Exception as e:
        print(f"    ERROR extracting {file_path.name}: {e}")
        return []

    # Attach metadata to each page
    for p in pages:
        p.setdefault("metadata", {})
        p["metadata"]["rel_path"] = rel_path
        p["metadata"]["source"]   = str(file_path)
        p["text"] = p.get("text", "").strip()

    return [p for p in pages if p.get("text")]


# ── 3. Simple chunker (fallback when LegalParser unavailable) ────────────────
CHUNK_SIZE = 800   # words per chunk
CHUNK_OVERLAP = 100


def simple_chunk(text: str, meta: dict):
    words = text.split()
    chunks = []
    i = 0
    idx = 0
    while i < len(words):
        chunk_words = words[i: i + CHUNK_SIZE]
        chunk_text  = " ".join(chunk_words).strip()
        if chunk_text:
            cid = str(uuid.uuid4())
            chunks.append({
                "chunk_id": cid,
                "text":     chunk_text,
                "metadata": meta,
                "source":   meta.get("source", ""),
                "rel_path": meta.get("rel_path", ""),
            })
        i += CHUNK_SIZE - CHUNK_OVERLAP
        idx += 1
    return chunks


def chunk_pages(pages):
    if not pages:
        return []

    try:
        from app.ingestion.legal_parser import LegalParser
        from app.utils.legal_cleaner import LegalCleaner

        full_text  = "\n".join(p.get("text", "") for p in pages)
        first_meta = pages[0].get("metadata", {})
        doc_type   = first_meta.get("document_type", "Other")

        full_text = LegalCleaner.clean(full_text)
        chunks_data = LegalParser.structural_split(full_text, doc_type)

        chunks = []
        for idx, obj in enumerate(chunks_data):
            text = obj["text"].strip()
            if not text:
                continue
            norm_cit = LegalParser.extract_citations(text, normalize=True)
            topic    = LegalParser.classify_topic(text)
            full_meta = {**first_meta, "topic": topic, "citations": norm_cit,
                         "section_type": obj["structure"]}
            cid = LegalParser.generate_chunk_id(full_meta, obj["structure"], text, idx)
            chunks.append({
                "chunk_id": cid,
                "text":     text,
                "metadata": full_meta,
                "source":   first_meta.get("source", ""),
                "rel_path": first_meta.get("rel_path", ""),
            })
        return chunks

    except Exception as e:
        print(f"    LegalParser failed ({e}), using simple chunker")
        full_text = "\n".join(p.get("text", "") for p in pages)
        meta = pages[0].get("metadata", {})
        return simple_chunk(full_text, meta)


# ── 4. Embed + append to FAISS ───────────────────────────────────────────────
def embed_and_append(chunks):
    """
    Embeds chunks and appends to the FAISS index.
    Uses a temporary index to avoid loading the full 134 MB index into memory
    (which causes MemoryError in standalone scripts).
    Instead, writes a small side-car index that the server will merge on next restart.
    """
    if not chunks:
        return 0

    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3")
    texts = [c["text"] for c in chunks]
    vecs  = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    vecs  = vecs.astype("float32")

    # Write to a sidecar file — avoids loading the full main index
    sidecar = INDEX_FILE.parent / "index_sidecar.faiss"
    if sidecar.exists():
        idx = faiss.read_index(str(sidecar))
    else:
        idx = faiss.IndexFlatIP(VECTOR_DIM)

    idx.add(vecs)
    faiss.write_index(idx, str(sidecar))
    return len(chunks)


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print("Scanning for un-indexed files...")
    indexed = get_indexed_set()
    missing = find_missing(indexed)

    print(f"Already indexed: {len(indexed)} unique files")
    print(f"Files to process: {len(missing)}")
    if not missing:
        print("Nothing to do — all files already indexed.")
        return

    total_docs    = 0
    total_chunks  = 0
    total_vectors = 0
    errors        = 0

    for i, (rel_path, file_path) in enumerate(missing, 1):
        print(f"\n[{i}/{len(missing)}] {rel_path}")

        # Skip temp lock files
        if file_path.name.startswith("~$") or file_path.name.startswith("._"):
            print("  - skipping temp/hidden file")
            continue

        # Extract
        pages = extract_text(file_path, rel_path)
        if not pages:
            print("  - no text extracted, skipping")
            continue

        # Write raw pages to documents.jsonl
        with DOCS_FILE.open("a", encoding="utf-8") as f:
            for p in pages:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        total_docs += len(pages)
        print(f"  + {len(pages)} pages extracted")

        # Chunk
        chunks = chunk_pages(pages)
        if not chunks:
            print("  - no chunks generated")
            continue

        # Write chunks to chunks.jsonl
        with CHUNKS_FILE.open("a", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        total_chunks += len(chunks)
        print(f"  + {len(chunks)} chunks")

        # Embed + add to FAISS
        try:
            added = embed_and_append(chunks)
            total_vectors += added
            print(f"  + {added} vectors → FAISS")
        except Exception as e:
            print(f"  ! Embedding error: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"DONE.")
    print(f"  Files processed : {len(missing) - errors}")
    print(f"  Pages added     : {total_docs}")
    print(f"  Chunks added    : {total_chunks}")
    print(f"  Vectors added   : {total_vectors}")
    print(f"  Errors          : {errors}")

    # Show new total
    new_chunks = sum(1 for _ in CHUNKS_FILE.open(encoding="utf-8", errors="ignore"))
    print(f"  chunks.jsonl now: {new_chunks} lines")


if __name__ == "__main__":
    run()
