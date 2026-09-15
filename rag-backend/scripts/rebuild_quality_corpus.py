"""Build a clean, section-aware corpus and matching FAISS index.

Usage:
    python scripts/rebuild_quality_corpus.py --dry-run
    python scripts/rebuild_quality_corpus.py --apply

The apply mode backs up the current chunks and index before replacing them.
It intentionally avoids LLM enrichment: the source passage remains the
retrieval truth, while deterministic metadata makes the result reproducible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import sys
import os
import unicodedata
from collections import Counter
from pathlib import Path

import fitz

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.config import CHUNKS_PATH, VECTOR_DB_PATH, VECTOR_DIM

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("quality_rebuild")

DATA_ROOT = BASE_DIR / "RAG_INFORMATION_DATABASE"
CHUNKS_FILE = Path(CHUNKS_PATH)
INDEX_FILE = Path(VECTOR_DB_PATH)
META_FILE = INDEX_FILE.with_suffix(".meta.json")

CATEGORY_MAP = {
    "CGST Acts": ("CGST Act", "cgst"),
    "CGST Rules 10-08-2026": ("Rules", "rules"),
    "circulars(2017-2025)": ("Circular", "circulars"),
    "High Court Case Laws": ("Case Law", "highcourt"),
    "IGST Acts": ("IGST Act", "igst"),
    "IGST rules": ("Rules", "rules"),
    "Rate_notifications_2.0": ("Notification", "notifications"),
    "Supreme Court Case Laws": ("Case Law", "supremecourt"),
}

# Explicitly reviewed non-GST material. New exclusions should be added only
# after review, rather than using a broad keyword filter that could hide law.
EXCLUDED_NAME_PARTS = (
    "mineral area development authority v. steel authority of india",
)

_SECTION_RE = re.compile(
    r"\b(?:section|sec\.?|s\.)\s*(\d+[A-Za-z]?(?:\s*\(\s*[\da-zA-Z]+\s*\))*)",
    re.IGNORECASE,
)
_RULE_RE = re.compile(
    r"\b(?:rule|u/r)\s*(\d+[A-Za-z]?(?:\s*\(\s*[\da-zA-Z]+\s*\))*)",
    re.IGNORECASE,
)
_CIRCULAR_RE = re.compile(r"\bcircular(?:\s+no\.?)?\s*(\d+)", re.IGNORECASE)
_NOTIFICATION_RE = re.compile(r"\bnotification(?:\s+no\.?)?\s*(\d+)", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^\s*(?:page\s*)?\d+\s*$", re.IGNORECASE)
_BOUNDARY_RE = re.compile(
    r"^\s*(?:section|sec\.?|rule|article)\s+\d+|"
    r"^\s*(?:\d+\.|\(\d+\)|\([a-z]\))\s+|"
    r"^\s*(?:provided that|explanation|whereas|now,? therefore)\b",
    re.IGNORECASE,
)

# Canonical document-level circular and notification regexes (shared with retriever.py)
_CIR_NUM_RE = re.compile(
    r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
    r'|cir[-_.](?:cgst[-_.])?'
    r'|cir(?=[0-9])'
    r'|circularno[-_.])'
    r'(\d{2,3})',
    re.IGNORECASE,
)
_CIR_LEADING_RE = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)

_NOTIF_NUM_RE = re.compile(
    r'(?:notif(?:ication)?[-_.\s]*(?:no[-_.\s]*)?)?(\d+)[-_/](\d{4})',
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line and not _PAGE_NUMBER_RE.match(line):
            lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _paragraphs(text: str) -> list[str]:
    blocks = [re.sub(r"\s*\n\s*", " ", block).strip() for block in re.split(r"\n\s*\n", text)]
    return [block for block in blocks if block]


from app.ingestion.provision_extractor import StructuralProvisionExtractor


def _section_aware_chunks(paragraphs: list[str], rel_path: str = "", category: str = "") -> list[dict]:
    chunks = []
    current: list[str] = []
    current_words = 0
    max_words = 420
    overlap_words = 60

    def flush() -> None:
        nonlocal current, current_words
        if not current:
            return
        text = " ".join(current).strip()
        extracted = StructuralProvisionExtractor.extract(text, rel_path, category)
        chunks.append({
            "text": text,
            "section_label": extracted.primary_section_label,
            "section_labels": extracted.primary_section_labels,
            "provision_keys": extracted.all_provision_keys,
        })
        tail = text.split()[-overlap_words:]
        current = [" ".join(tail)] if tail else []
        current_words = len(tail)

    for paragraph in paragraphs:
        words = paragraph.split()
        if current and (_BOUNDARY_RE.match(paragraph) or current_words + len(words) > max_words):
            flush()
        if len(words) <= max_words:
            current.append(paragraph)
            current_words += len(words)
            continue
        sentences = re.split(r"(?<=[.;])\s+", paragraph)
        for sentence in sentences:
            sentence_words = sentence.split()
            if current and current_words + len(sentence_words) > max_words:
                flush()
            current.append(sentence)
            current_words += len(sentence_words)
    flush()
    return chunks


def _provision_keys(text: str, existing: list, category: str, rel_path: str) -> list[str]:
    """Extract canonical provision keys using the data-driven structural provision extractor."""
    extracted = StructuralProvisionExtractor.extract(text, rel_path, category)
    keys = set(extracted.all_provision_keys)
    for key in existing or []:
        if key:
            keys.add(key)
    return sorted(keys)


def _extract_pdf(pdf_path: Path, use_ocr: bool) -> str:
    pages = []
    with fitz.open(str(pdf_path)) as document:
        for page in document:
            text = page.get_text("text")
            if len(text.strip()) < 80 and use_ocr:
                try:
                    import pytesseract
                    from PIL import Image
                    if not shutil.which("tesseract"):
                        for candidate in (
                            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                        ):
                            if os.path.exists(candidate):
                                pytesseract.pytesseract.tesseract_cmd = candidate
                                break
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                    text = pytesseract.image_to_string(image)
                except Exception as exc:
                    log.debug("OCR unavailable for %s: %s", pdf_path.name, exc)
            text = _clean_text(text)
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def _source_files() -> list[tuple[Path, str, str]]:
    files = []
    source_root = DATA_ROOT / "Database_V2.0"
    if not source_root.exists():
        source_root = DATA_ROOT
    for folder, (document_type, category) in CATEGORY_MAP.items():
        root = source_root / folder
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.pdf")):
            if not any(part in path.name.lower() for part in EXCLUDED_NAME_PARTS):
                files.append((path, document_type, category))
    return files


def build_corpus(use_ocr: bool = True) -> tuple[list[dict], dict]:
    seen_documents: set[str] = set()
    seen_chunks: set[str] = set()
    chunks: list[dict] = []
    stats = Counter()

    for number, (pdf_path, document_type, category) in enumerate(_source_files(), 1):
        rel_path = str(pdf_path.relative_to(DATA_ROOT)).replace("\\", "/")
        raw = _extract_pdf(pdf_path, use_ocr)
        if not raw:
            stats["empty_documents"] += 1
            continue
        document_hash = hashlib.sha256(re.sub(r"\s+", " ", raw).encode()).hexdigest()
        if document_hash in seen_documents:
            stats["duplicate_documents"] += 1
            continue
        seen_documents.add(document_hash)

        source_chunks = _section_aware_chunks(_paragraphs(raw), rel_path, category)
        for index, item in enumerate(source_chunks):
            text = _clean_text(item.get("text", ""))
            if len(text) < 120:
                stats["short_chunks"] += 1
                continue
            text_hash = hashlib.sha256(re.sub(r"\s+", " ", text).encode()).hexdigest()
            if text_hash in seen_chunks:
                stats["duplicate_chunks"] += 1
                continue
            seen_chunks.add(text_hash)
            keys = _provision_keys(text, item.get("provision_keys", []), category, rel_path)
            chunk_id = hashlib.sha256(f"{rel_path}\n{index}\n{text}".encode()).hexdigest()[:24]
            metadata = {
                "source": str(pdf_path),
                "rel_path": rel_path,
                "document_type": document_type,
                "category": category,
                "filename": pdf_path.name,
                "chunk_id": chunk_id,
                "chunk_index": index,
                "provision_keys": keys,
                "section_label": item.get("section_label"),
                "section_labels": item.get("section_labels", []),
            }
            chunks.append({
                "chunk_id": chunk_id,
                "text": text,
                "embed_text": text,
                "source": str(pdf_path),
                "rel_path": rel_path,
                "metadata": metadata,
            })
        if number % 50 == 0:
            log.info("Processed %d/%d documents", number, len(_source_files()))

    chunks.sort(key=lambda chunk: (chunk["rel_path"], chunk["metadata"]["chunk_index"]))
    stats["documents_kept"] = len(seen_documents)
    stats["chunks_kept"] = len(chunks)
    stats["with_provisions"] = sum(bool(c["metadata"]["provision_keys"]) for c in chunks)
    stats["source_files"] = len(_source_files())
    return chunks, dict(stats)


def retag_chunks_list(chunks: list[dict]) -> tuple[list[dict], dict]:
    """
    Re-tag an existing chunk collection with the StructuralProvisionExtractor
    without needing to re-extract raw PDFs from scratch.
    """
    retagged = []
    stats = Counter()
    for c in chunks:
        meta = dict(c.get("metadata", {}))
        text = c.get("text", "") or c.get("content", "")
        rel_path = meta.get("rel_path") or c.get("rel_path", "")
        category = meta.get("category") or c.get("category", "")
        extracted = StructuralProvisionExtractor.extract(text, rel_path, category)

        meta["provision_keys"] = extracted.all_provision_keys
        meta["section_label"] = extracted.primary_section_label
        meta["section_labels"] = extracted.primary_section_labels

        chunk_copy = dict(c)
        chunk_copy["metadata"] = meta
        retagged.append(chunk_copy)
        stats["chunks_retagged"] += 1
        if extracted.all_provision_keys:
            stats["with_provisions"] += 1

    return retagged, dict(stats)


def write_candidate_index(
    chunks: list[dict],
    candidate_chunks_file: Path,
    candidate_index_file: Path,
    reuse_existing_faiss: bool = True,
) -> None:
    """Build a complete, isolated candidate FAISS index and metadata without touching production."""
    candidate_chunks_file.parent.mkdir(parents=True, exist_ok=True)
    candidate_index_file.parent.mkdir(parents=True, exist_ok=True)
    candidate_meta_file = candidate_index_file.with_suffix(".meta.json")

    import faiss
    import numpy as np

    metadata = [item["metadata"] for item in chunks]

    if reuse_existing_faiss and INDEX_FILE.exists():
        log.info("Reusing existing FAISS vectors from %s (text unchanged)", INDEX_FILE)
        shutil.copy2(INDEX_FILE, candidate_index_file)
        index = faiss.read_index(str(candidate_index_file))
    else:
        from app.embeddings.embedder import embed_texts
        index = faiss.IndexFlatIP(VECTOR_DIM)
        for start in range(0, len(chunks), 64):
            batch = chunks[start:start + 64]
            vectors = embed_texts([item.get("embed_text") or item.get("text", "") for item in batch]).astype("float32")
            if vectors.ndim != 2 or vectors.shape[1] != VECTOR_DIM:
                raise ValueError(f"Embedding dimension mismatch: got {vectors.shape}, expected (*, {VECTOR_DIM})")
            index.add(np.ascontiguousarray(vectors))
        faiss.write_index(index, str(candidate_index_file))

    with candidate_chunks_file.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    candidate_meta_file.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    if index.ntotal != len(chunks):
        raise RuntimeError(f"FAISS/chunk mismatch after candidate build: {index.ntotal} != {len(chunks)}")
    log.info("Candidate build complete: %d chunks at %s", len(chunks), candidate_chunks_file)


def write_and_rebuild(chunks: list[dict], backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in (CHUNKS_FILE, INDEX_FILE, META_FILE):
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
    import faiss
    import numpy as np
    from app.embeddings.embedder import embed_texts

    index = faiss.IndexFlatIP(VECTOR_DIM)
    metadata = []
    for start in range(0, len(chunks), 64):
        batch = chunks[start:start + 64]
        vectors = embed_texts([item["embed_text"] for item in batch]).astype("float32")
        if vectors.ndim != 2 or vectors.shape[1] != VECTOR_DIM:
            raise ValueError(f"Embedding dimension mismatch: got {vectors.shape}, expected (*, {VECTOR_DIM})")
        index.add(np.ascontiguousarray(vectors))
        metadata.extend(item["metadata"] for item in batch)

    # Only replace the corpus after every batch has produced valid vectors.
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    META_FILE.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    if index.ntotal != len(chunks):
        raise RuntimeError(f"FAISS/chunk mismatch after rebuild: {index.ntotal} != {len(chunks)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", action="store_true", help="build isolated candidate corpus and index")
    parser.add_argument("--candidate-chunks", default="data/candidate_corpus/chunks.jsonl")
    parser.add_argument("--candidate-index", default="vectordb/candidate/index.faiss")
    parser.add_argument("--retag-existing", action="store_true", help="re-tag existing production chunks instead of re-reading PDFs")
    parser.add_argument("--apply", action="store_true", help="replace production chunks and rebuild FAISS")
    parser.add_argument("--dry-run", action="store_true", help="report results without changing files")
    parser.add_argument("--no-ocr", action="store_true", help="disable OCR fallback")
    parser.add_argument("--backup-dir", default="vectordb/quality_rebuild_backup")
    args = parser.parse_args()

    if args.retag_existing:
        log.info("Loading existing production chunks from %s", CHUNKS_FILE)
        existing_chunks = []
        with CHUNKS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    existing_chunks.append(json.loads(line))
        chunks, stats = retag_chunks_list(existing_chunks)
        log.info("Re-tag stats: %s", json.dumps(stats, sort_keys=True))
    else:
        chunks, stats = build_corpus(use_ocr=not args.no_ocr)
        log.info("Quality rebuild stats: %s", json.dumps(stats, sort_keys=True))

    if args.candidate:
        cand_chunks_path = BASE_DIR / args.candidate_chunks
        cand_index_path = BASE_DIR / args.candidate_index
        write_candidate_index(chunks, cand_chunks_path, cand_index_path)
        log.info("Successfully built candidate index at %s and chunks at %s", cand_index_path, cand_chunks_path)
        return

    if not args.apply:
        log.info("Dry run only. Re-run with --candidate or --apply after reviewing the counts.")
        return
    write_and_rebuild(chunks, BASE_DIR / args.backup_dir)
    log.info("Rebuilt %d chunks and matching FAISS index", len(chunks))


if __name__ == "__main__":
    main()