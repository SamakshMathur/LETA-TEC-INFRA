"""
Ingest documents from RAG_INFORMATION_DATABASE into FAISS and upload to S3.

Two modes:

  Default (incremental):
    Only ingests documents NOT already in the index.
    .\.venv_win\Scripts\python.exe scripts\ingest_all_to_s3.py

  Rebuild (full re-ingestion with contextual retrieval):
    Wipes the local index clean and re-ingests EVERY document.
    Each document gets a 2-sentence Haiku context prefix baked into its
    embeddings (Anthropic's contextual retrieval — cuts retrieval failure by ~49%).
    Contexts are generated in parallel (20 workers, ~1 min for 1,400 docs).
    Takes 2-4 hours total (embedding is the bottleneck). Safe to kill and resume.
    .\.venv_win\Scripts\python.exe scripts\ingest_all_to_s3.py --rebuild

Resume files (both modes):
  vectordb/pending_chunks.jsonl       — extracted chunks waiting to be embedded
  vectordb/ingest_checkpoint.json     — {batch_completed, total} saved every 10 batches
  vectordb/index.checkpoint.faiss     — FAISS state at last checkpoint
  vectordb/index.checkpoint.meta.json
  vectordb/doc_contexts.json          — cached Haiku context per document
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
    # ── Database V2.0 ONLY (RAG_INFORMATION_DATABASE/Database_V2.0/<folder>) ─
    ("Database_V2.0/CGST Acts",              "Act",          "cgst"),
    ("Database_V2.0/IGST Acts",              "Act",          "igst"),
    ("Database_V2.0/CGST Rules 10-08-2026",  "Rules",        "rules"),
    ("Database_V2.0/IGST rules",             "Rules",        "rules"),
    ("Database_V2.0/Rate_notifications_2.0", "Notification", "notifications"),
    ("Database_V2.0/circulars(2017-2025)",   "Circular",     "circulars"),
    ("Database_V2.0/High Court Case Laws",   "Case Law",     "highcourt"),
    ("Database_V2.0/Supreme Court Case Laws","Case Law",     "supremecourt"),
]

# generated_reports = system output PDFs, not source law — never ingest
# __MACOSX          = Mac ZIP ghost folders containing duplicate metadata stubs
SKIP_FOLDERS   = {"generated_reports", "__MACOSX"}
CHECKPOINT_EVERY = 10


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

import re as _re
_YEAR_FNAME_RE = _re.compile(r'[-_](\d{4})[-_.]')

def _extract_year(path: Path):
    # 1. Year as a standalone directory component  (.../2022/...)
    for part in path.parts:
        if part.isdigit() and 2010 <= int(part) <= 2030:
            return part
    # 2. Year embedded in the filename (e.g. cir-252-09-2025-cgst.pdf)
    m = _YEAR_FNAME_RE.search(path.name)
    if m and 2010 <= int(m.group(1)) <= 2030:
        return m.group(1)
    return None


# ── Contextual Retrieval — Anthropic technique ─────────────────────────────────
# For each document we ask Claude Haiku to write a 1-2 sentence description
# that gets prepended to every chunk before embedding.  This moves the chunk's
# vector into the right region of embedding space even when the raw text doesn't
# contain the exact keywords a user might search for (e.g. "circular 183" when
# the chunk text only says "the Board hereby clarifies...").
#
# Context is generated ONCE per document (not per chunk) and cached to
# doc_contexts.json so a resumed run never re-hits the API.

DOC_CONTEXTS_FILE = BASE_DIR / "vectordb" / "doc_contexts.json"

def _load_doc_contexts() -> dict:
    if DOC_CONTEXTS_FILE.exists():
        try:
            return json.loads(DOC_CONTEXTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_doc_contexts(ctx: dict):
    DOC_CONTEXTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOC_CONTEXTS_FILE.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")

def _generate_doc_context(rel_path: str, document_type: str, first_text: str) -> str:
    """Generate a 2-sentence embedding context prefix using local Ollama (qwen2.5:7b).
    Free, no API key needed. Falls back to rule-based prefix if Ollama is unavailable.
    Context is cached in doc_contexts.json — Ollama is only called once per document.
    """
    # ── Primary: Ollama (local, free, no API key) ─────────────────────────────
    try:
        import ollama as _ollama
        resp = _ollama.chat(
            model="qwen2.5:7b",
            options={"num_predict": 120, "temperature": 0.1},
            messages=[{"role": "user", "content": (
                f"You are indexing a GST legal document for a vector search system.\n\n"
                f"File path: {rel_path}\n"
                f"Document type: {document_type}\n"
                f"Opening text:\n{first_text[:600]}\n\n"
                f"Write exactly 2 sentences (max 80 words total) describing this document. "
                f"Include: document type (Circular/Notification/Act/etc.), number if visible, "
                f"topic (ITC/RCM/rate/valuation/etc.), and year. "
                f"Output ONLY the 2 sentences, nothing else."
            )}],
        )
        result = resp["message"]["content"].strip()
        if result:
            return result
    except Exception as e:
        log.warning(f"  Ollama context generation failed for {rel_path}: {e} — using rule-based fallback")

    # ── Fallback: rule-based prefix from filename/folder (always works, zero cost) ──
    return _rule_based_context(rel_path, document_type)


def _rule_based_context(rel_path: str, document_type: str) -> str:
    """Derive a context prefix purely from the file path — no model, no API, instant."""
    import re as _re
    r   = rel_path.replace("\\", "/").lower()
    fname = rel_path.replace("\\", "/").split("/")[-1]

    # Extract year (4-digit anywhere in path)
    yr_m = _re.search(r'(20\d{2})', rel_path)
    year_str = f" ({yr_m.group(1)})" if yr_m else ""

    # Circular
    cir_m = _re.search(r'circular[_\-\s]*(?:no[_\-\.\s]*)?(\d{2,3})', fname, _re.IGNORECASE)
    if cir_m or "circular" in r:
        num = f" No. {cir_m.group(1)}" if cir_m else ""
        return (f"This is a CBIC GST Circular{num}{year_str} issued by the Central Board "
                f"of Indirect Taxes and Customs clarifying GST provisions. "
                f"It provides authoritative guidance on the interpretation and application of GST law.")

    # Rate notification
    if "notification" in r or "rate_notification" in r:
        notif_m = _re.search(r'(\d{1,3})[_\-/](\d{4})', fname)
        num = f" No. {notif_m.group(1)}/{notif_m.group(2)}" if notif_m else ""
        return (f"This is a GST Rate Notification{num}{year_str} specifying applicable tax rates, "
                f"exemptions, and HSN/SAC classifications under the GST regime. "
                f"It prescribes the rate of tax on goods and services.")

    # CGST Act
    if "cgst act" in r or ("cgst" in r and "act" in r and "rules" not in r):
        return (f"This is the Central Goods and Services Tax (CGST) Act, 2017{year_str}, "
                f"the primary legislation governing GST in India. "
                f"It defines the charging provisions, ITC rules, registration requirements, and compliance framework.")

    # IGST Act
    if "igst act" in r or ("igst" in r and "act" in r and "rules" not in r):
        return (f"This is the Integrated Goods and Services Tax (IGST) Act, 2017{year_str}, "
                f"governing inter-state supply of goods and services including exports, imports, and place of supply rules.")

    # CGST Rules
    if "cgst rules" in r:
        rule_m = _re.search(r'rule[_\-\s]*(\d+)', fname, _re.IGNORECASE)
        rule_str = f" Rule {rule_m.group(1)}" if rule_m else ""
        return (f"This is{rule_str} of the CGST Rules, 2017{year_str}, "
                f"prescribing the procedural framework for compliance under the CGST Act. "
                f"It covers registration, returns, invoicing, ITC, and valuation procedures.")

    # IGST Rules
    if "igst rules" in r:
        return (f"This is the IGST Rules, 2017{year_str}, prescribing procedures for "
                f"inter-state transactions, place of supply determination, and export/import compliance.")

    # High Court judgment
    if "high court" in r:
        return (f"This is a High Court judgment{year_str} on a GST-related matter. "
                f"It interprets statutory provisions, determines the taxability of specific transactions, "
                f"and may be cited as persuasive precedent in similar GST disputes.")

    # Supreme Court judgment
    if "supreme court" in r:
        return (f"This is a Supreme Court judgment{year_str} on a GST or indirect tax matter. "
                f"It is binding precedent on the interpretation of GST law across all Indian courts.")

    # AAR / Advance Ruling
    if "aar" in r or "advance" in r:
        return (f"This is an Advance Ruling (AAR){year_str} on the GST treatment of a specific "
                f"transaction or activity. It is binding on the applicant and the relevant tax authority.")

    # ICAI / FAQ / Brochure
    if "icai" in r or "faq" in r or "brochure" in r:
        return (f"This is an ICAI publication or GST FAQ document{year_str} providing "
                f"professional guidance and clarifications on GST provisions for practitioners.")

    # Generic fallback
    return (f"This is a GST legal document of type '{document_type}'{year_str} "
            f"relevant to the Indian Goods and Services Tax regime.")


def ingest_pdf(pdf_path: Path, document_type: str, category_key: str,
               doc_contexts: dict | None = None) -> list:
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

    # ── Contextual Retrieval: generate a document-level context prefix ────────
    # The context is cached in doc_contexts dict (persisted to doc_contexts.json)
    # so a resumed ingestion never re-calls the API.
    ctx_prefix = ""
    if doc_contexts is not None:
        ctx_key = rel_path.lower()
        if ctx_key not in doc_contexts:
            ctx_prefix = _generate_doc_context(rel_path, document_type, pages_text[0])
            doc_contexts[ctx_key] = ctx_prefix
        else:
            ctx_prefix = doc_contexts[ctx_key]

    # ── Chunking: RecursiveCharacterTextSplitter ──────────────────────────────
    # Replaces the old blind 1500-char sliding window.
    # Splits in priority order: paragraph breaks → sentence ends → words → chars.
    # Covers 100% of the document text (old window silently dropped last 200 chars).
    # chunk_size=1200 keeps chunks within bge-large-en-v1.5's 512-token sweet spot.
    # chunk_overlap=150 ensures a section heading at the end of one chunk
    # also appears at the start of the next, preserving cross-boundary context.
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    _splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        separators=["\n\n\n", "\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""],
        length_function=len,
    )
    raw_texts = _splitter.split_text(full_text)

    chunks = []
    for i, text in enumerate(raw_texts):
        text = text.strip()
        if len(text) < 80:          # skip near-empty fragments (page headers, footers)
            continue
        chunk_id = hashlib.md5(f"{rel_path}_{i}".encode()).hexdigest()[:16]
        meta = {
            "source": str(pdf_path), "rel_path": rel_path,
            "document_type": document_type, "category": category_key,
            "filename": pdf_path.name, "chunk_id": chunk_id,
        }
        if year:
            meta["year"] = year
        # embed_text = context prefix (Ollama/rule-based) + chunk text.
        # text stays as-is for display; embed_text is what gets encoded into the vector.
        embed_text = f"{ctx_prefix}\n\n{text}" if ctx_prefix else text
        chunks.append({
            "chunk_id": chunk_id, "text": text, "embed_text": embed_text,
            "source": str(pdf_path), "rel_path": rel_path, "metadata": meta,
        })
    return chunks


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_and_append_all(all_new_chunks: list, resume_from_batch: int = 0,
                         fresh_index: bool = False):
    import faiss
    from sentence_transformers import SentenceTransformer

    VECTOR_DIM = 1024  # BAAI/bge-large-en-v1.5

    log.info("Loading BAAI/bge-large-en-v1.5 model...")
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    log.info("Model loaded.")

    # Rebuild: start from empty index.  Incremental: load S3 base or checkpoint.
    if resume_from_batch > 0 and INDEX_CKPT.exists():
        log.info(f"Resuming from checkpoint (batch {resume_from_batch})...")
        index     = faiss.read_index(str(INDEX_CKPT))
        meta_list = load_meta(META_CKPT)
    elif fresh_index:
        log.info("Creating fresh empty FAISS IndexFlatIP (rebuild mode)...")
        index     = faiss.IndexFlatIP(VECTOR_DIM)
        meta_list = []
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
        # Use embed_text (context-enriched) when available; fall back to text.
        # embed_text = Haiku context prefix + raw chunk text for richer vectors.
        texts = [c.get("embed_text") or c["text"] for c in batch]
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


# ── Parallel context pre-generation ───────────────────────────────────────────

def _generate_all_contexts_parallel(pdf_list: list, doc_contexts: dict,
                                    workers: int = 20) -> dict:
    """
    Generate Haiku context for every PDF in parallel.
    pdf_list: list of (pdf_path, document_type, cat_key, pages_text[0])
    Returns updated doc_contexts dict.
    """
    import concurrent.futures

    def _generate_one(item):
        pdf_path, doc_type, cat_key, first_page = item
        rel_path = str(pdf_path.relative_to(DB_ROOT)).replace("\\", "/")
        ctx_key = rel_path.lower()
        if ctx_key in doc_contexts:
            return ctx_key, doc_contexts[ctx_key]   # already cached
        ctx = _generate_doc_context(rel_path, doc_type, first_page)
        return ctx_key, ctx

    todo = [item for item in pdf_list
            if str(item[0].relative_to(DB_ROOT)).replace("\\", "/").lower()
            not in doc_contexts]
    done = len(pdf_list) - len(todo)
    log.info(f"  Context generation: {done} cached, {len(todo)} to generate "
             f"({workers} parallel workers)")

    if not todo:
        return doc_contexts

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_generate_one, item): item for item in todo}
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            try:
                ctx_key, ctx = future.result()
                doc_contexts[ctx_key] = ctx
                completed += 1
                if completed % 50 == 0 or completed == len(todo):
                    log.info(f"  Contexts generated: {completed}/{len(todo)}")
                    _save_doc_contexts(doc_contexts)
            except Exception as e:
                log.warning(f"  Context generation error: {e}")

    _save_doc_contexts(doc_contexts)
    return doc_contexts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LETA Ingestion Pipeline")
    parser.add_argument(
        "--rebuild", action="store_true",
        help=(
            "Full rebuild: wipe local index and re-ingest ALL documents with "
            "contextual retrieval embeddings. Takes 2-4 hrs. Safe to interrupt "
            "and resume (run again without --rebuild to continue)."
        ),
    )
    args = parser.parse_args()
    REBUILD = args.rebuild

    log.info("=" * 70)
    mode = "FULL REBUILD (contextual retrieval)" if REBUILD else "INCREMENTAL"
    log.info(f"LETA INGESTION PIPELINE — {mode}")
    log.info("=" * 70)

    # ── Resume path (both modes) ────────────────────────────────────────────
    checkpoint = load_checkpoint()
    resuming   = (not REBUILD
                  and checkpoint is not None
                  and PENDING_FILE.exists()
                  and INDEX_CKPT.exists())

    if resuming:
        resume_from = checkpoint["batch_completed"] + 1
        log.info(f"\nRESUMING from batch {resume_from} "
                 f"(saved {time.strftime('%H:%M:%S', time.localtime(checkpoint['saved_at']))})")
        all_new_chunks = []
        with PENDING_FILE.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    all_new_chunks.append(json.loads(line))
                except Exception:
                    pass
        log.info(f"Loaded {len(all_new_chunks)} pending chunks from checkpoint.")
        fresh = False

    else:
        resume_from = 0
        fresh = REBUILD

        if REBUILD:
            log.info("\n[REBUILD] Clearing checkpoint files for fresh start...")
            cleanup_checkpoint()
            log.info("[REBUILD] Will create empty FAISS index — NOT downloading from S3.")
        else:
            log.info("\n[1/5] Downloading latest S3 base files...")
            download_from_s3()

        # Decide which documents to process
        if REBUILD:
            # All documents on disk
            all_by_cat: dict = {}
            grand_total_disk = 0
            log.info("\n[2/5] Scanning all categories for full rebuild...")
            for folder_name, doc_type, cat_key in CATEGORIES:
                cat_root = DB_ROOT / folder_name
                if not cat_root.exists():
                    log.warning(f"  {folder_name}: NOT FOUND — skipping")
                    continue
                pdfs = sorted([
                    p for p in cat_root.rglob("*.pdf")
                    if p.is_file()
                    and not any(sk in p.parts for sk in SKIP_FOLDERS)
                    and not p.name.startswith("._")
                ])
                grand_total_disk += len(pdfs)
                if pdfs:
                    all_by_cat[folder_name] = (pdfs, doc_type, cat_key)
                log.info(f"  {folder_name:<30} {len(pdfs):>4} files")
            total_to_process = sum(len(v[0]) for v in all_by_cat.values())
            log.info(f"\n  Total: {grand_total_disk} PDFs across all categories")
        else:
            log.info("\n[2/5] Scanning existing index...")
            indexed = get_indexed_sources()
            log.info("\n[3/5] Auditing all categories...")
            all_by_cat: dict = {}
            grand_total_disk = 0
            for folder_name, doc_type, cat_key in CATEGORIES:
                cat_root = DB_ROOT / folder_name
                if not cat_root.exists():
                    log.warning(f"  {folder_name}: NOT FOUND — skipping")
                    continue
                all_pdfs = sorted([
                    p for p in cat_root.rglob("*.pdf")
                    if p.is_file()
                    and not any(sk in p.parts for sk in SKIP_FOLDERS)
                    and not p.name.startswith("._")
                ])
                grand_total_disk += len(all_pdfs)
                missing = [p for p in all_pdfs
                           if str(p).replace("\\", "/").lower() not in indexed]
                if missing:
                    all_by_cat[folder_name] = (missing, doc_type, cat_key)
                log.info(f"  {folder_name:<30} disk={len(all_pdfs):>4}  "
                         f"indexed={len(all_pdfs)-len(missing):>4}  "
                         f"MISSING={len(missing):>4}")
            total_to_process = sum(len(v[0]) for v in all_by_cat.values())
            log.info(f"\n  Disk total: {grand_total_disk} | To process: {total_to_process}")

        if total_to_process == 0:
            log.info("Nothing to process — index is complete.")
            return

        # ── Step: extract text from all PDFs ─────────────────────────────────
        log.info(f"\n[3/5] Extracting text from {total_to_process} PDFs...")
        raw_chunks_by_doc: dict = {}   # rel_path → (list_of_chunks, doc_type, first_page)
        all_pdfs_flat = []             # for parallel context generation
        all_new_chunks = []

        grand_idx = 0
        for folder_name, (pdfs, doc_type, cat_key) in all_by_cat.items():
            for pdf in pdfs:
                grand_idx += 1
                rel_path = str(pdf.relative_to(DB_ROOT)).replace("\\", "/")
                if grand_idx % 100 == 1:
                    log.info(f"  Extracting [{grand_idx}/{total_to_process}] {rel_path}")
                chunks_no_ctx = ingest_pdf(pdf, doc_type, cat_key, doc_contexts=None)
                if chunks_no_ctx:
                    # Grab first-page text for context generation
                    try:
                        import fitz
                        d = fitz.open(str(pdf))
                        first_page = d[0].get_text().strip()[:800] if d.page_count else ""
                        d.close()
                    except Exception:
                        first_page = chunks_no_ctx[0]["text"][:800]
                    all_pdfs_flat.append((pdf, doc_type, cat_key, first_page))
                    raw_chunks_by_doc[rel_path] = chunks_no_ctx
        log.info(f"  Extracted {sum(len(v) for v in raw_chunks_by_doc.values())} chunks "
                 f"from {len(raw_chunks_by_doc)} documents")

        # ── Step: generate contexts in parallel ───────────────────────────────
        log.info(f"\n[4/5] Generating contextual embeddings via Ollama (qwen2.5:7b)...")
        log.info("      (2 sentences per document, 20 parallel workers, cached after first run)")
        doc_contexts = _load_doc_contexts()
        doc_contexts = _generate_all_contexts_parallel(all_pdfs_flat, doc_contexts, workers=20)
        log.info(f"  Context cache now covers {len(doc_contexts)} documents")

        # ── Step: apply contexts to chunks ────────────────────────────────────
        log.info("\n  Applying context prefixes to chunks...")
        for rel_path, chunks in raw_chunks_by_doc.items():
            ctx_prefix = doc_contexts.get(rel_path.lower(), "")
            for c in chunks:
                c["embed_text"] = f"{ctx_prefix}\n\n{c['text']}" if ctx_prefix else c["text"]
            all_new_chunks.extend(chunks)

        log.info(f"  Total chunks ready for embedding: {len(all_new_chunks)}")

        if not all_new_chunks:
            log.error("No chunks produced. Check PDFs and paths.")
            return

        # Save pending chunks + append to chunks.jsonl
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PENDING_FILE.open("w", encoding="utf-8") as f:
            for c in all_new_chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        log.info(f"  Pending chunks saved ({PENDING_FILE.name}) — resume-safe")

        CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_mode = "w" if REBUILD else "a"
        with CHUNKS_FILE.open(write_mode, encoding="utf-8") as f:
            for c in all_new_chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        action = "Written" if REBUILD else "Appended"
        log.info(f"  {action} {len(all_new_chunks)} chunks to chunks.jsonl")

    # ── Embed ─────────────────────────────────────────────────────────────────
    total = len(all_new_chunks)
    log.info(f"\n[5/5] Embedding {total} chunks "
             f"({'resuming' if resuming else 'fresh' if REBUILD else 'incremental'})...")
    if REBUILD:
        log.info("  ETA: roughly 2-4 hours on CPU. Safe to interrupt — "
                 "run again without --rebuild to resume from last checkpoint.")
    embed_and_append_all(all_new_chunks, resume_from_batch=resume_from,
                         fresh_index=fresh)

    # ── Upload + restart ──────────────────────────────────────────────────────
    log.info("\nUploading updated index to S3...")
    upload_to_s3()

    log.info("\nRestarting ECS service with new index...")
    restart_ecs()

    cleanup_checkpoint()

    log.info("\n" + "=" * 70)
    log.info("DONE — ECS is restarting with the fully contextualised knowledge base.")
    log.info("All circulars, notifications, and laws now have contextual embeddings.")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
