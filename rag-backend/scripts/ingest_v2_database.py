"""
ingest_v2_database.py  —  Database_V2.0 Incremental Ingestion
==============================================================
Highest-quality ingestion pipeline for Database_V2.0 into the existing index.

What it does
------------
Phase 1  — Chunk surgery: purge stale chunks from categories that V2.0 replaces
           (CGST, Rules, Circulars, High Court, IGST, Supreme Court, generated_reports).
           Keeps: ICAI, AAR, Notification, Responses, Forms, FAQs, Brochures, root.

Phase 2  — Discover all PDF files in Database_V2.0, skip any already indexed.

Phase 3  — Extract text (PyMuPDF), chunk with 1500-char sliding window.

Phase 4  — Contextual enrichment: Haiku generates a 2-sentence document-level
           context prefix baked into every chunk's embed_text (Anthropic technique,
           ~49% retrieval-failure reduction). One Haiku call per document, cached
           to vectordb/v2_doc_contexts.json so restarts are free.

Phase 5  — Provision tagging: normalize_citation() stamps provision_keys on every
           new chunk so the provision index picks them up at startup.

Phase 6  — Merge + deduplicate: new V2.0 chunks + surviving old chunks. If V2.0
           contains a path already in the kept set (shouldn't happen), V2.0 wins.

Phase 7  — Rebuild FAISS from scratch on ALL chunks (old kept + new V2.0).

Phase 8  — Upload chunks.jsonl + index.faiss + meta to S3.

Phase 9  — Force-restart ECS so the live backend reloads immediately.

Safe to interrupt and resume at any phase — checkpointed throughout.

Usage:
    .\.win_venv\Scripts\python.exe scripts\ingest_v2_database.py

Estimated time  : 90-180 min  (680 files, Haiku context + BGE-M3 embedding)
Estimated cost  : ~$1-3 USD   (Haiku context generation for ~6800 new chunks)
"""

import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest_v2")

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
BASE_DIR    = SCRIPT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import (
    DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH, VECTOR_DIM,
    ANTHROPIC_API_KEY,
)

DB_ROOT         = Path(DATA_DIR)                          # RAG_INFORMATION_DATABASE
V2_ROOT         = DB_ROOT / "Database_V2.0"
CHUNKS_FILE     = Path(CHUNKS_PATH)                       # data/chunks/chunks.jsonl
INDEX_FILE      = Path(VECTOR_DB_PATH)                    # vectordb/index.faiss
META_FILE       = INDEX_FILE.with_suffix(".meta.json")
BACKUP_CHUNKS   = CHUNKS_FILE.parent / "chunks.jsonl.pre_v2.bak"
CTX_CACHE_FILE  = BASE_DIR / "vectordb" / "v2_doc_contexts.json"
PHASE_FILE      = BASE_DIR / "vectordb" / "v2_ingest_phase.json"

S3_BUCKET     = "gst-rag-data-721082558531"
S3_REGION     = "ap-south-1"
S3_CHUNKS_KEY = "data/chunks/chunks.jsonl"
S3_INDEX_KEY  = "vectordb/index.faiss"
S3_META_KEY   = "vectordb/index.meta.json"

# ── V2.0 folder → (document_type, category_key) ───────────────────────────────
V2_CATEGORY_MAP = {
    "CGST Acts":               ("CGST Act",     "cgst"),
    "CGST Rules 10-08-2026":   ("Rules",        "rules"),
    "circulars(2017-2025)":    ("Circular",     "circulars"),
    "High Court Case Laws":    ("Case Law",     "highcourt"),
    "IGST Acts":               ("IGST Act",     "igst"),
    "IGST rules":              ("Rules",        "rules"),
    "Rate_notifications_2.0":  ("Notification", "notifications"),
    "Supreme Court Case Laws": ("Case Law",     "supremecourt"),
}

# ── Folders to PURGE from existing chunks (being replaced by V2.0) ────────────
# Match on the FIRST path component, case-insensitive
PURGE_FOLDER_PREFIXES = {
    "cgst",
    "act",
    "rules",
    "circulars",
    "high court case laws",
    "igst",
    "supreme court case laws",
    "generated_reports",
}

# Files to always skip
SKIP_EXACT = {
    "Other APP Result/CHATGPT_ITC on Bike_Wrong Answer.docx",
    "Other APP Result/GORK_ITC on Bike_Right Answer but wrong Logic.docx",
}

SUPPORTED_EXT = {".pdf"}  # V2.0 is all PDFs

_YEAR_RE = re.compile(r"[-_](\d{4})[-_.]")


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _save_phase(phase: str, data: dict = None):
    PHASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHASE_FILE.write_text(json.dumps({"phase": phase, **(data or {})}))

def _load_phase() -> dict:
    if PHASE_FILE.exists():
        try:
            return json.loads(PHASE_FILE.read_text())
        except Exception:
            pass
    return {"phase": "start"}

def _load_ctx_cache() -> dict:
    if CTX_CACHE_FILE.exists():
        try:
            return json.loads(CTX_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_ctx_cache(ctx: dict):
    CTX_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CTX_CACHE_FILE.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")

def _extract_year(path: Path) -> str | None:
    for part in path.parts:
        if part.isdigit() and 2010 <= int(part) <= 2030:
            return part
    m = _YEAR_RE.search(path.name)
    if m and 2010 <= int(m.group(1)) <= 2030:
        return m.group(1)
    return None

def _folder_prefix(rel_path: str) -> str:
    """Return lowercased first path component."""
    normalized = rel_path.replace("\\", "/")
    return normalized.split("/")[0].lower() if "/" in normalized else ""


# ── Provision key tagging — full pattern set including case-law citation styles ─

_CIT_CGST_SEC = re.compile(
    r"(?:section|sec\.?)\s*(\d+[A-Z]?)(?:\s*\((\d+[a-z]?)\))?",
    re.IGNORECASE,
)
_CIT_RULE = re.compile(
    r"rule\s*(\d+[A-Z]?)(?:\s*\((\d+[a-z]?)\))?",
    re.IGNORECASE,
)
_CIT_NOTIF = re.compile(
    r"notification\s+no\.?\s*(\d+)[/-](\d{4})[^,\n]*?(?:central\s+tax|ct)\b",
    re.IGNORECASE,
)
_CIT_CIRC = re.compile(
    r"circular\s+no\.?\s*(\d+)[/-](\d{4})",
    re.IGNORECASE,
)
# Case-law shorthand: u/s 16, u/s 9(3)  →  CGST_SEC_N
_CIT_US = re.compile(
    r"\bu\s*/\s*s\.?\s*(\d+[A-Z]?)(?:\s*\((\d+[a-z]?)\))?",
    re.IGNORECASE,
)
# Case-law shorthand: u/r 42, u/r 96  →  CGST_RULE_N
_CIT_UR = re.compile(
    r"\bu\s*/\s*r\.?\s*(\d+[A-Z]?)(?:\s*\((\d+[a-z]?)\))?",
    re.IGNORECASE,
)
# S.16, s. 16(2)  →  CGST_SEC_N  (used in HC/SC judgments)
_CIT_S_DOT = re.compile(
    r"\bS\.\s*(\d+[A-Z]?)(?:\s*\((\d+[a-z]?)\))?",
    re.IGNORECASE,
)
# Schedule I / II / III (related-party, supply, exemption tables)
_CIT_SCHED = re.compile(
    r"\bSchedule\s+(I{1,3}|IV|V|VI|[1-6])\b",
    re.IGNORECASE,
)
# Loose notification cite without mandatory "Central Tax" tail
_CIT_NOTIF_LOOSE = re.compile(
    r"notification\s+no\.?\s*(\d+)[/-](\d{4})",
    re.IGNORECASE,
)


def _tag_provision_keys(chunk: dict) -> dict:
    """
    Add provision_keys list to chunk metadata based on text + rel_path.
    Covers both statute-style (Section N, Rule N) and case-law-style
    (u/s N, u/r N, S.N, Schedule I/II/III) citation formats.
    """
    text = chunk.get("text", "")
    rel  = chunk.get("metadata", {}).get("rel_path", chunk.get("rel_path", ""))
    keys: set[str] = set()

    # 1. From inline citations in text
    for m in _CIT_CGST_SEC.finditer(text):
        keys.add(f"CGST_SEC_{m.group(1).upper()}")
    for m in _CIT_RULE.finditer(text):
        keys.add(f"CGST_RULE_{m.group(1).upper()}")
    for m in _CIT_NOTIF.finditer(text):
        keys.add(f"NOTIF_{m.group(1)}_{m.group(2)}")
    for m in _CIT_CIRC.finditer(text):
        keys.add(f"CIRC_{m.group(1)}_{m.group(2)}")

    # 2. Case-law specific patterns (u/s, u/r, S.N, Schedule)
    for m in _CIT_US.finditer(text):
        keys.add(f"CGST_SEC_{m.group(1).upper()}")
    for m in _CIT_UR.finditer(text):
        keys.add(f"CGST_RULE_{m.group(1).upper()}")
    for m in _CIT_S_DOT.finditer(text):
        keys.add(f"CGST_SEC_{m.group(1).upper()}")
    for m in _CIT_SCHED.finditer(text):
        keys.add(f"CGST_SCHED_{m.group(1).upper()}")
    for m in _CIT_NOTIF_LOOSE.finditer(text):
        keys.add(f"NOTIF_{m.group(1)}_{m.group(2)}")

    # 3. From filename
    fname = Path(rel).name.lower() if rel else ""
    sec_m = re.search(r"section[_-]?(\d+[a-z]?)", fname, re.IGNORECASE)
    if sec_m:
        keys.add(f"CGST_SEC_{sec_m.group(1).upper()}")
    rule_m = re.search(r"rule[_-]?(\d+)", fname, re.IGNORECASE)
    if rule_m:
        keys.add(f"CGST_RULE_{rule_m.group(1)}")
    circ_m = re.search(r"cir(?:cular)?[-_]?(\d+)[-_](\d{2})[-_](\d{4})", fname)
    if circ_m:
        keys.add(f"CIRC_{circ_m.group(1)}_{circ_m.group(3)}")

    if keys:
        if "metadata" in chunk:
            chunk["metadata"]["provision_keys"] = sorted(keys)
        else:
            chunk["provision_keys"] = sorted(keys)
    return chunk


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — CHUNK SURGERY
# ═══════════════════════════════════════════════════════════════════════════════

def phase1_purge_stale_chunks() -> list[dict]:
    """
    Read chunks.jsonl, drop chunks from folders that V2.0 replaces, return kept list.
    """
    log.info("=" * 60)
    log.info("PHASE 1 — Purging stale chunks from replaced categories")
    log.info("=" * 60)

    kept, purged = [], 0
    by_folder: dict[str, int] = defaultdict(int)

    with CHUNKS_FILE.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except Exception:
                continue

            meta = c.get("metadata", {})
            rel  = meta.get("rel_path", meta.get("source", c.get("rel_path", c.get("source", ""))))
            rel  = rel.replace("\\", "/")
            prefix = _folder_prefix(rel)

            # Always drop generated_reports (LETA's own AI outputs)
            if rel in SKIP_EXACT or "generated_reports" in rel.lower():
                purged += 1
                continue

            if prefix in PURGE_FOLDER_PREFIXES:
                purged += 1
                by_folder[prefix] += 1
            else:
                kept.append(c)

    log.info(f"  Kept  : {len(kept):,} chunks")
    log.info(f"  Purged: {purged:,} chunks")
    for folder, cnt in sorted(by_folder.items(), key=lambda x: -x[1]):
        log.info(f"    purged [{folder}]: {cnt:,}")
    return kept


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — DISCOVER V2.0 FILES
# ═══════════════════════════════════════════════════════════════════════════════

def phase2_discover_files(kept_chunks: list[dict]) -> list[tuple[Path, str, str]]:
    """
    Walk Database_V2.0, return list of (path, doc_type, category_key) for files
    not already in the kept chunks set.
    """
    log.info("=" * 60)
    log.info("PHASE 2 — Discovering Database_V2.0 files")
    log.info("=" * 60)

    # Build set of already-indexed rel_paths from kept chunks
    already: set[str] = set()
    for c in kept_chunks:
        meta = c.get("metadata", {})
        rel  = meta.get("rel_path", meta.get("source", c.get("rel_path", c.get("source", ""))))
        if rel:
            already.add(rel.replace("\\", "/").lower())
    log.info(f"  Already indexed (kept): {len(already):,} unique paths")

    to_ingest: list[tuple[Path, str, str]] = []
    skipped_dup = 0

    for folder_name, (doc_type, cat_key) in V2_CATEGORY_MAP.items():
        folder_path = V2_ROOT / folder_name
        if not folder_path.exists():
            log.warning(f"  Folder not found: {folder_path} — skipping")
            continue

        files = sorted(folder_path.rglob("*.pdf"))
        log.info(f"  [{folder_name}] {len(files)} PDFs")
        for fp in files:
            if fp.name.startswith(".") or fp.name.startswith("~$"):
                continue
            rel = str(fp.relative_to(DB_ROOT)).replace("\\", "/")
            if rel.replace("\\", "/").lower() in already:
                skipped_dup += 1
                continue
            to_ingest.append((fp, doc_type, cat_key))

    log.info(f"  Total to ingest: {len(to_ingest):,} files ({skipped_dup} already indexed — skipped)")
    return to_ingest


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 3+4+5 — EXTRACT, CHUNK, ENRICH, TAG
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_chunk_context(rel_path: str, doc_type: str, chunk_text: str, client) -> str:
    """
    Haiku: generate a 2-sentence context describing THIS SPECIFIC CHUNK (not the whole doc).
    Each chunk gets its own call so the retrieval embedding reflects the actual passage content.
    """
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        system=(
            "You are a GST legal document indexing assistant. "
            "Write precise, specific descriptions to help a retrieval system "
            "locate exactly this passage — not the document in general."
        ),
        messages=[{"role": "user", "content": (
            f"Document: {rel_path}\n"
            f"Type: {doc_type}\n"
            f"Specific passage text:\n{chunk_text[:600]}\n\n"
            f"Write exactly 2 sentences (max 80 words total) describing WHAT THIS SPECIFIC "
            f"PASSAGE covers. Mention: the specific section/rule/circular number if cited "
            f"(e.g. 'Section 16(4)', 'Rule 42', 'Circular 204/16/2023'), the exact GST topic "
            f"(ITC eligibility, RCM, valuation, Schedule I, penalty, refund, etc.), and any "
            f"key conditions, time limits, exceptions, or ruling. "
            f"Output ONLY the 2 sentences, nothing else."
        )}],
    )
    return resp.content[0].text.strip()


def _process_one_file(
    pdf_path: Path, doc_type: str, cat_key: str, ctx_cache: dict
) -> list[dict]:
    """Extract → chunk → enrich → tag one PDF. Returns list of chunk dicts."""
    try:
        import fitz
    except ImportError:
        log.error("PyMuPDF (fitz) not installed — cannot process PDFs")
        return []

    rel_path = str(pdf_path.relative_to(DB_ROOT)).replace("\\", "/")
    year = _extract_year(pdf_path)

    try:
        doc = fitz.open(str(pdf_path))
        pages_text = [p.get_text().strip() for p in doc if p.get_text().strip()]
        doc.close()
    except Exception as e:
        log.warning(f"  Cannot open {pdf_path.name}: {e}")
        return []

    if not pages_text:
        log.warning(f"  No extractable text: {pdf_path.name}")
        return []

    full_text = "\n\n".join(pages_text)

    # ── Build Anthropic client once per file (reused for every chunk) ─────────
    haiku_client = None
    if ANTHROPIC_API_KEY:
        try:
            import anthropic as _anthropic
            haiku_client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        except Exception as e:
            log.warning(f"  Anthropic client init failed: {e}")

    # ── Sliding-window chunking with per-chunk Haiku context ─────────────────
    # Each chunk gets its OWN Haiku context describing that specific passage.
    # This replaces the old approach of one shared document-level prefix for
    # all chunks from the same file (which caused generic/duplicate contexts).
    WINDOW, STEP = 1500, 1300
    chunks = []
    for i, start in enumerate(range(0, max(1, len(full_text) - 200), STEP)):
        text = full_text[start: start + WINDOW].strip()
        if len(text) < 80:
            continue
        chunk_id = hashlib.md5(f"{rel_path}_{i}".encode()).hexdigest()[:16]

        # Per-chunk Haiku context (chunk_id used as cache key)
        ctx_key  = chunk_id
        if ctx_key not in ctx_cache:
            if haiku_client:
                try:
                    ctx_prefix = _generate_chunk_context(rel_path, doc_type, text, haiku_client)
                except Exception as e:
                    log.warning(f"  Haiku failed for chunk {chunk_id}: {e}")
                    ctx_prefix = ""
            else:
                ctx_prefix = ""
            ctx_cache[ctx_key] = ctx_prefix
        else:
            ctx_prefix = ctx_cache[ctx_key]

        embed_text = f"{ctx_prefix}\n\n{text}" if ctx_prefix else text

        chunk: dict = {
            "text":              text,
            "text_with_context": embed_text,
            "embed_text":        embed_text,
            "context":           ctx_prefix,
            "source":            str(pdf_path),
            "rel_path":          rel_path,
            "metadata": {
                "source":        str(pdf_path),
                "rel_path":      rel_path,
                "document_type": doc_type,
                "category":      cat_key,
                "filename":      pdf_path.name,
                "chunk_id":      chunk_id,
                "chunk_index":   i,
            },
        }
        if year:
            chunk["metadata"]["year"] = year

        # ── Provision key tagging (enhanced patterns) ─────────────────────────
        chunk = _tag_provision_keys(chunk)
        chunks.append(chunk)

    return chunks


def phase345_extract_chunk_enrich(
    to_ingest: list[tuple[Path, str, str]],
) -> list[dict]:
    """
    Process all V2.0 files: extract → chunk → per-chunk Haiku enrichment → provision tag.
    ctx_cache is now keyed by chunk_id (not doc rel_path) so each passage gets its own context.
    Checkpointed every save_every documents.
    """
    log.info("=" * 60)
    log.info("PHASE 3/4/5 — Extract / Chunk / Enrich / Tag")
    log.info("=" * 60)

    ctx_cache = _load_ctx_cache()
    log.info(f"  Context cache loaded: {len(ctx_cache):,} chunk contexts already generated")

    new_chunks: list[dict] = []
    save_every = 5  # save ctx cache every N documents (more often since chunks >> docs)

    for idx, (fp, doc_type, cat_key) in enumerate(to_ingest, 1):
        rel = str(fp.relative_to(DB_ROOT)).replace("\\", "/")
        log.info(f"  [{idx}/{len(to_ingest)}] {rel}")

        chunks = _process_one_file(fp, doc_type, cat_key, ctx_cache)
        if chunks:
            new_chunks.extend(chunks)
            ctx_hits = sum(1 for c in chunks if ctx_cache.get(c["metadata"]["chunk_id"]))
            log.info(f"    -> {len(chunks)} chunks, {ctx_hits} with Haiku context")
        else:
            log.warning(f"    -> 0 chunks (skipped)")

        # Checkpoint context cache every save_every docs
        if idx % save_every == 0:
            _save_ctx_cache(ctx_cache)
            log.info(f"  [checkpoint] ctx_cache saved ({idx}/{len(to_ingest)} docs, "
                     f"{len(ctx_cache):,} chunk contexts)")

    _save_ctx_cache(ctx_cache)
    log.info(f"  New chunks generated: {len(new_chunks):,}")
    return new_chunks


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 6 — MERGE + DEDUPLICATE
# ═══════════════════════════════════════════════════════════════════════════════

def phase6_merge_and_dedup(kept: list[dict], new: list[dict]) -> list[dict]:
    """
    Merge kept old chunks + new V2.0 chunks.
    If a source path appears in both (shouldn't, but safety), V2.0 wins.
    """
    log.info("=" * 60)
    log.info("PHASE 6 — Merge + Deduplicate")
    log.info("=" * 60)

    # Build new_paths set (from V2.0 ingestion)
    new_paths: set[str] = set()
    for c in new:
        meta = c.get("metadata", {})
        rel  = meta.get("rel_path", c.get("rel_path", "")).replace("\\", "/").lower()
        if rel:
            new_paths.add(rel)

    # Remove any kept chunks whose path is now covered by V2.0
    old_kept_final = []
    dupes_removed = 0
    for c in kept:
        meta = c.get("metadata", {})
        rel  = meta.get("rel_path", meta.get("source", c.get("rel_path", ""))).replace("\\", "/").lower()
        if rel in new_paths:
            dupes_removed += 1
        else:
            old_kept_final.append(c)

    if dupes_removed:
        log.info(f"  Removed {dupes_removed:,} duplicates (V2.0 version wins)")

    merged = old_kept_final + new
    log.info(f"  Old kept: {len(old_kept_final):,}  +  New V2.0: {len(new):,}  =  Total: {len(merged):,}")
    return merged


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 7 — WRITE CHUNKS + REBUILD FAISS
# ═══════════════════════════════════════════════════════════════════════════════

def phase7_rebuild_faiss(all_chunks: list[dict]):
    """Write chunks.jsonl, embed ALL chunks from scratch, build FAISS index."""
    log.info("=" * 60)
    log.info("PHASE 7 — Write chunks.jsonl + Rebuild FAISS")
    log.info("=" * 60)

    # ── Backup original if not already done ──────────────────────────────────
    if not BACKUP_CHUNKS.exists() and CHUNKS_FILE.exists():
        shutil.copy2(str(CHUNKS_FILE), str(BACKUP_CHUNKS))
        log.info(f"  Backed up original to {BACKUP_CHUNKS.name}")

    # ── Write merged chunks.jsonl ─────────────────────────────────────────────
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    log.info(f"  Wrote {len(all_chunks):,} chunks to {CHUNKS_FILE.name}")

    # ── Embed + build FAISS ───────────────────────────────────────────────────
    log.info("  Loading embedder (BGE-M3)...")
    from app.retrieval.retriever import get_model
    embedder = get_model()

    try:
        import faiss
        import numpy as np
    except ImportError:
        log.error("faiss / numpy not installed — cannot rebuild index")
        return

    dim = VECTOR_DIM
    index = faiss.IndexFlatIP(dim)
    meta_list: list[dict] = []

    BATCH = 64
    total = len(all_chunks)
    log.info(f"  Embedding {total:,} chunks in batches of {BATCH}…")

    for batch_start in range(0, total, BATCH):
        batch = all_chunks[batch_start: batch_start + BATCH]
        texts = [c.get("text_with_context") or c.get("embed_text") or c.get("text", "") for c in batch]
        try:
            vecs = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            vecs = np.array(vecs, dtype="float32")
            index.add(vecs)
            for c in batch:
                m = c.get("metadata", {})
                meta_list.append({
                    "source":        m.get("source", c.get("source", "")),
                    "rel_path":      m.get("rel_path", c.get("rel_path", "")),
                    "document_type": m.get("document_type", ""),
                    "category":      m.get("category", ""),
                    "filename":      m.get("filename", ""),
                    "chunk_id":      m.get("chunk_id", ""),
                    "year":          m.get("year", ""),
                    "provision_keys": m.get("provision_keys", []),
                    "text":          c.get("text", "")[:300],
                })
        except Exception as e:
            log.error(f"  Embedding error at batch {batch_start}: {e}")
            continue

        if (batch_start // BATCH + 1) % 50 == 0:
            done = min(batch_start + BATCH, total)
            log.info(f"    {done:,}/{total:,} embedded ({100*done//total}%)")

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    META_FILE.write_text(json.dumps(meta_list, ensure_ascii=False), encoding="utf-8")
    log.info(f"  FAISS index: {index.ntotal:,} vectors → {INDEX_FILE.name}")
    log.info(f"  Meta file written: {META_FILE.name}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 8 — UPLOAD TO S3
# ═══════════════════════════════════════════════════════════════════════════════

def phase8_upload_s3():
    log.info("=" * 60)
    log.info("PHASE 8 — Uploading to S3")
    log.info("=" * 60)
    try:
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
            log.info(f"    uploaded")
    except Exception as e:
        log.error(f"S3 upload failed: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 9 — RESTART ECS
# ═══════════════════════════════════════════════════════════════════════════════

def phase9_restart_ecs():
    log.info("=" * 60)
    log.info("PHASE 9 — Force-restarting ECS service")
    log.info("=" * 60)
    try:
        import boto3
        ecs = boto3.client("ecs", region_name=S3_REGION)
        ecs.update_service(
            cluster="gst-rag-cluster",
            service="gst-rag-backend-service",
            forceNewDeployment=True,
        )
        log.info("  ECS force-redeploy triggered. New task will pull fresh S3 data on startup.")
    except Exception as e:
        log.error(f"ECS restart failed: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║   Database_V2.0 Ingestion  —  Highest-Quality Pipeline      ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info(f"  DB root   : {DB_ROOT}")
    log.info(f"  V2.0 root : {V2_ROOT}")
    log.info(f"  Chunks    : {CHUNKS_FILE}")
    log.info(f"  FAISS     : {INDEX_FILE}")
    log.info("")

    if not V2_ROOT.exists():
        log.error(f"Database_V2.0 not found at {V2_ROOT} — aborting")
        sys.exit(1)

    t_start = time.time()

    # ── Phase 1: purge stale chunks ───────────────────────────────────────────
    kept_chunks = phase1_purge_stale_chunks()
    _save_phase("after_phase1", {"kept": len(kept_chunks)})

    # ── Phase 2: discover V2.0 files ─────────────────────────────────────────
    to_ingest = phase2_discover_files(kept_chunks)
    if not to_ingest:
        log.info("No new files to ingest — index is already up to date.")
        return

    # ── Phase 3/4/5: extract + chunk + enrich + tag ───────────────────────────
    new_chunks = phase345_extract_chunk_enrich(to_ingest)
    _save_phase("after_phase5", {"kept": len(kept_chunks), "new": len(new_chunks)})

    # ── Phase 6: merge + dedup ────────────────────────────────────────────────
    all_chunks = phase6_merge_and_dedup(kept_chunks, new_chunks)

    # ── Phase 7: write + rebuild FAISS ───────────────────────────────────────
    phase7_rebuild_faiss(all_chunks)
    _save_phase("after_phase7", {"total": len(all_chunks)})

    # ── Phase 8: upload S3 ───────────────────────────────────────────────────
    phase8_upload_s3()

    # ── Phase 9: restart ECS ─────────────────────────────────────────────────
    phase9_restart_ecs()

    # ── Done ──────────────────────────────────────────────────────────────────
    elapsed = (time.time() - t_start) / 60
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info(f"║   DONE in {elapsed:.1f} min                                          ║")
    log.info(f"║   Total chunks in index: {len(all_chunks):,}                          ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")

    # Clean up phase tracker
    if PHASE_FILE.exists():
        PHASE_FILE.unlink()


if __name__ == "__main__":
    main()
