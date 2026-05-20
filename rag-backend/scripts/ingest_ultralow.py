"""
Ingest the remaining un-indexed files using ultra-low-memory OCR.
Run from: RAG/rag-backend/ using:
    python -X utf8 scripts/ingest_ultralow.py

After this completes, run rebuild_faiss_from_chunks.py to realign the index.
"""
import sys, io, os, json, uuid, gc

# Force UTF-8 stdout/stderr so Unicode in progress bars doesn't crash the script
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except ImportError:
    pytesseract = None

from pathlib import Path

DATA_DIR    = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\RAG_INFORMATION_DATABASE")
DOCS_FILE   = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\documents.jsonl")
CHUNKS_FILE = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\chunks.jsonl")
VECTOR_DIM  = 1024
# File size threshold above which we use ultralow (1x zoom) vs low (2x zoom) OCR
ULTRALOW_THRESHOLD_MB = 0.5  # everything scanned — use ultralow for all


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


def extract_text(file_path: Path, rel_path: str):
    ext = file_path.suffix.lower()
    pages = []

    try:
        if ext == ".pdf":
            from app.ingestion.pdf_text import extract_text_from_pdf
            raw_pages = extract_text_from_pdf(str(file_path))
            total = sum(len(p.get("text", "").strip()) for p in raw_pages)

            if total < 50:
                if pytesseract is not None:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf

                    # Try ultralow first (1x zoom, 72 DPI) — much less memory
                    print(f"    (scanned PDF {size_mb:.1f} MB — ultralow OCR 72 DPI)")
                    raw_pages = extract_text_from_scanned_pdf(
                        str(file_path), ultralow_memory=True
                    )
                    total2 = sum(len(p.get("text", "").strip()) for p in raw_pages
                                 if p.get("text", "").strip() not in ("", "[OCR_EMPTY_PAGE]"))
                    if total2 < 20 and size_mb < 2.0:
                        # Retry at 2x zoom for small files (better quality)
                        print(f"    (ultralow got <20 chars, retrying at 144 DPI)")
                        gc.collect()
                        raw_pages = extract_text_from_scanned_pdf(
                            str(file_path), low_memory=True
                        )
                    raw_pages = [p for p in raw_pages
                                 if p.get("text", "").strip() not in ("", "[OCR_EMPTY_PAGE]")]
                else:
                    raw_pages = []
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

    for p in pages:
        p.setdefault("metadata", {})
        p["metadata"]["rel_path"] = rel_path
        p["metadata"]["source"]   = str(file_path)
        p["text"] = p.get("text", "").strip()

    return [p for p in pages if p.get("text")]


CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100


def simple_chunk(text: str, meta: dict):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_text = " ".join(words[i: i + CHUNK_SIZE]).strip()
        if chunk_text:
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "text":     chunk_text,
                "metadata": meta,
                "source":   meta.get("source", ""),
                "rel_path": meta.get("rel_path", ""),
            })
        i += CHUNK_SIZE - CHUNK_OVERLAP
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
        full_text  = LegalCleaner.clean(full_text)
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
        return simple_chunk(full_text, pages[0].get("metadata", {}))


def run():
    print("Scanning for un-indexed files...")
    indexed = get_indexed_set()
    missing = find_missing(indexed)
    print(f"Already indexed: {len(indexed)} unique files")
    print(f"Files to process: {len(missing)}")
    if not missing:
        print("All files already indexed.")
        return

    total_docs   = 0
    total_chunks = 0
    errors       = 0

    for i, (rel_path, file_path) in enumerate(missing, 1):
        print(f"\n[{i}/{len(missing)}] {rel_path}")
        if file_path.name.startswith("~$") or file_path.name.startswith("._"):
            print("  - skipping temp/hidden file")
            continue

        pages = extract_text(file_path, rel_path)
        if not pages:
            print("  - no text extracted, skipping")
            # Still mark as indexed so future runs don't retry forever
            continue

        with DOCS_FILE.open("a", encoding="utf-8") as f:
            for p in pages:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        total_docs += len(pages)
        print(f"  + {len(pages)} pages extracted")

        chunks = chunk_pages(pages)
        if not chunks:
            print("  - no chunks generated")
            continue

        with CHUNKS_FILE.open("a", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        total_chunks += len(chunks)
        print(f"  + {len(chunks)} chunks written to JSONL")

        gc.collect()

    new_total = sum(1 for _ in CHUNKS_FILE.open(encoding="utf-8", errors="ignore"))
    print(f"\n{'='*60}")
    print(f"DONE.")
    print(f"  Files attempted : {len(missing)}")
    print(f"  Pages added     : {total_docs}")
    print(f"  Chunks added    : {total_chunks}")
    print(f"  chunks.jsonl now: {new_total} lines")
    print()
    print("Next step: run rebuild_faiss_from_chunks.py to rebuild the FAISS index")
    print("  python -X utf8 scripts/rebuild_faiss_from_chunks.py")


if __name__ == "__main__":
    run()
