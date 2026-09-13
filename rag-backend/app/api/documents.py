"""
documents.py — Document listing and serving API.

Listing endpoints load metadata from a pre-generated JSON file
(data/document_metadata.json, downloaded from S3 by start.sh on boot).
This avoids requiring Database_V2.0/ to be baked into the Docker image.

View/download endpoint tries the local filesystem first, then falls back
to an S3 presigned URL so PDFs are always accessible.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
import os
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
# CWD in the container is /app (ECS WORKDIR).  All relative paths are from /app.
_APP_ROOT  = Path(__file__).resolve().parent.parent.parent   # /app
BASE_DIR   = _APP_ROOT / "Database_V2.0"                    # may not exist in container
META_FILE  = _APP_ROOT / "data" / "document_metadata.json"  # downloaded by start.sh

# S3 config (for PDF serving fallback)
S3_BUCKET  = os.getenv("S3_DATA_BUCKET", "gst-rag-data-721082558531")
S3_REGION  = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
S3_DOCS_PREFIX = "documents"   # s3://<bucket>/documents/<folder>/<filename>


def _content_disposition(disposition: str, filename: str) -> str:
    """
    Build a Content-Disposition value safe to pass as S3's
    ResponseContentDisposition presigned-URL param.

    HTTP header values are ISO-8859-1 (Latin-1) only — a filename with a
    typographic character outside that range (en/em dash, smart quotes;
    common in legal document titles like "Sections 3–6") makes S3 itself
    reject the presigned request with InvalidArgumentHeader, which the
    browser then shows as a raw S3 XML error where the PDF should be.

    Sends both: an ASCII-safe `filename=` fallback (typographic
    punctuation folded to its plain-ASCII equivalent, anything left
    non-ASCII dropped) for older clients, and the RFC 5987
    `filename*=UTF-8''<percent-encoded>` form every modern browser
    actually uses, which preserves the exact original name.
    """
    import re
    from urllib.parse import quote

    ascii_name = (
        filename
        .replace("–", "-").replace("—", "-")   # – —
        .replace("‘", "'").replace("’", "'")    # ‘ ’
        .replace("“", '"').replace("”", '"')    # “ ”
    )
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii").strip() or "document.pdf"
    # `"` and `\` would break out of the quoted-string in `filename="..."`.
    ascii_name = re.sub(r'[\\"]', "_", ascii_name)
    encoded_name = quote(filename, safe="")
    return f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'

# Category → Database_V2.0 top-level folder name.
# As of the 2026-09 restructure, Database_V2.0 is FLAT — one folder per
# category, matching these keys 1:1. The listing endpoints filter by the
# "category" field in metadata JSON; this map is mainly used for the
# /view (PDF serving) route to resolve category → folder.
CATEGORY_MAP = {
    "circulars":     "circulars",
    "notifications": "notifications",
    "cgst":          "cgst_acts",
    "rules":         "cgst_rules",
    "igst":          "igst_acts",
    "igst_rules":    "igst_rules",
    "highcourt":     "high_court",
    "supremecourt":  "supreme_court",
    "aars":          "aars",
    "case_laws":     "case_laws_by_section",
    "forms":         "forms",
    "faqs":          "faqs",
    "brochures":     "brochures",
    "responses":     "responses",
    "export":        "export",
    # Aliases for backward compatibility with older frontend calls
    "acts":          "cgst_acts",
    "reports":       "circulars",
    "icai":          "cgst_acts",
    # Frontend has a "flyers" filter row (label: "AAR / App. Results") with
    # no corresponding category anywhere in the corpus or metadata — it was
    # never mapped, so /list/flyers returned nothing and /view fell through
    # to 404 whenever the category param was "flyers". Point it at AAR
    # rulings, matching the frontend's own label for that row.
    "flyers":        "aars",
}

# ── Metadata cache ─────────────────────────────────────────────────────────────
_meta_lock  = threading.Lock()
_meta_cache: Optional[List[dict]] = None

def _load_metadata() -> List[dict]:
    """Load document metadata from local JSON file (downloaded from S3 by start.sh)."""
    global _meta_cache
    with _meta_lock:
        if _meta_cache is not None:
            return _meta_cache
        if META_FILE.exists():
            try:
                with open(META_FILE, encoding="utf-8") as f:
                    _meta_cache = json.load(f)
                logger.info(f"[docs] Loaded {len(_meta_cache)} documents from {META_FILE}")
                return _meta_cache
            except Exception as e:
                logger.error(f"[docs] Failed to load {META_FILE}: {e}")
        # Fallback: scan filesystem (works locally / if Database_V2.0 is present)
        _meta_cache = _scan_filesystem()
        return _meta_cache


def append_to_metadata_cache(entry: dict) -> None:
    """
    Called by incremental_ingest right after an admin-uploaded document is
    ingested, so it shows up in the document library listing (/list/*)
    immediately — without this, a freshly uploaded document was searchable
    by the RAG pipeline right away but invisible in the library until the
    next container restart re-downloaded metadata.json from S3.
    """
    meta = _load_metadata()  # ensures the cache is populated first
    with _meta_lock:
        meta.append(entry)


def _scan_filesystem() -> List[dict]:
    """Scan Database_V2.0 directory (fallback when metadata JSON is unavailable)."""
    docs = []
    if not BASE_DIR.exists():
        logger.warning(f"[docs] BASE_DIR {BASE_DIR} not found — document library empty")
        return docs
    idx = 0
    for cat_key, folder_name in CATEGORY_MAP.items():
        folder_path = BASE_DIR / folder_name
        if not folder_path.exists():
            continue
        seen = set()
        for fp in folder_path.rglob("*"):
            if not fp.is_file() or fp.suffix.lower() not in ('.pdf', '.docx', '.txt'):
                continue
            rel = str(fp.relative_to(BASE_DIR)).replace("\\", "/")
            if rel in seen:
                continue
            seen.add(rel)
            parts = rel.split("/")
            year = parts[1] if len(parts) > 2 and parts[1].isdigit() and len(parts[1]) == 4 else "other"
            docs.append({
                "id": f"{cat_key}_{idx}",
                "title": fp.name,
                "filename": fp.name,
                "size": f"{round(fp.stat().st_size / 1024, 1)} KB",
                "path": rel,
                "category": cat_key,
                "year": year,
            })
            idx += 1
    logger.info(f"[docs] Scanned filesystem: {len(docs)} documents")
    return docs


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    meta = _load_metadata()
    return {"status": "ok", "service": "documents", "total_docs": len(meta),
            "metadata_source": "json" if META_FILE.exists() else "filesystem"}


@router.get("/categories")
def get_categories():
    meta = _load_metadata()
    counts: Dict[str, int] = {k: 0 for k in CATEGORY_MAP}
    for doc in meta:
        cat = doc.get("category", "")
        if cat in counts:
            counts[cat] += 1
    return counts


@router.get("/list/all")
def list_all_documents():
    """All documents across every category (for instant client-side search)."""
    return _load_metadata()


@router.get("/list/circulars/by-year")
def list_circulars_by_year():
    """Circulars grouped by year for the year-tab UI."""
    meta = _load_metadata()
    result: Dict[str, List] = {}
    for doc in meta:
        if doc.get("category") != "circulars":
            continue
        yr = doc.get("year", "other")
        result.setdefault(yr, []).append(doc)
    return result


@router.get("/list/notifications/by-year")
def list_notifications_by_year():
    """Notifications grouped by year."""
    meta = _load_metadata()
    result: Dict[str, List] = {}
    for doc in meta:
        if doc.get("category") != "notifications":
            continue
        yr = doc.get("year", "other")
        result.setdefault(yr, []).append(doc)
    return result


@router.get("/list/{category}")
def list_documents(category: str):
    """Documents in a specific category."""
    canonical = CATEGORY_MAP.get(category.lower())
    if not canonical:
        raise HTTPException(status_code=404, detail="Category not found")
    meta = _load_metadata()
    folder_name = canonical
    docs = [d for d in meta if d.get("folder") == folder_name or d.get("category") == category.lower()]
    return docs[:200]


@router.get("/view")
def view_document(category: str, filename: str, download: bool = False):
    """
    Serve a document via S3 presigned URL.

    Looks up the document's exact stored `path` from metadata first (this
    is the authoritative source — generate_metadata.py records the real
    relative path under Database_V2.0 for every file, year subfolders
    included, e.g. "notifications/2025/03-2025-ct-eng.pdf"). Falling back
    to a filename-only guess (category top-folder, no year) silently
    missed every file organised under a year subfolder — notifications,
    circulars, aars — which is most of the corpus after the restructure.
    """
    import urllib.parse
    filename = urllib.parse.unquote(os.path.basename(filename))

    try:
        import boto3
        s3 = boto3.client("s3", region_name=S3_REGION)

        # 1. Authoritative lookup: find the doc's real path in metadata.
        s3_key = None
        meta = _load_metadata()
        for d in meta:
            if d.get("filename") == filename:
                if category.lower() in ("all", "any") or d.get("category") == category.lower():
                    s3_key = f"{S3_DOCS_PREFIX}/{d.get('path', '').replace(chr(92), '/')}"
                    break
        # First match on filename alone if the category-scoped pass found nothing
        # (handles a stale/mismatched category param from an older client).
        if not s3_key:
            for d in meta:
                if d.get("filename") == filename:
                    s3_key = f"{S3_DOCS_PREFIX}/{d.get('path', '').replace(chr(92), '/')}"
                    break

        if s3_key:
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
            except Exception:
                s3_key = None  # metadata said it should exist but it's not in S3 — fall through

        # 2. Fallback: guess top-level category folder (no year) — covers
        # categories that were never year-subfoldered, or a metadata miss.
        if not s3_key:
            folder_name = CATEGORY_MAP.get(category.lower(), category)
            try_key = f"{S3_DOCS_PREFIX}/{folder_name}/{filename}"
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=try_key)
                s3_key = try_key
            except Exception:
                pass

        # 3. Last resort: brute-force search every known category folder.
        if not s3_key:
            for fn in set(CATEGORY_MAP.values()):
                try_key = f"{S3_DOCS_PREFIX}/{fn}/{filename}"
                try:
                    s3.head_object(Bucket=S3_BUCKET, Key=try_key)
                    s3_key = try_key
                    break
                except Exception:
                    continue

        if not s3_key:
            raise HTTPException(status_code=404, detail=f"'{filename}' not found")

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key,
                    "ResponseContentDisposition": _content_disposition(
                        "attachment" if download else "inline", filename
                    )},
            ExpiresIn=300,
        )
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[docs] S3 fallback failed: {e}")
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not available")


@router.get("/ai_search")
async def ai_search(query: str = Query(...)):
    """Semantic search across the document library via FAISS retriever."""
    import asyncio
    from app.dependencies import get_retriever
    try:
        # get_retriever() is a lazy singleton — on the FIRST call since a
        # worker (re)starts it does the full cold init synchronously
        # (loading the ~190MB FAISS index, building BM25/TF-IDF/citation
        # graph, loading the CrossEncoder — tens of seconds of CPU work),
        # not just a cheap "return the cached instance" call. Same
        # event-loop-blocking risk as retriever.search() itself, so it
        # needs the same asyncio.to_thread treatment.
        retriever = await asyncio.to_thread(get_retriever)
        if not retriever or not retriever.index:
            return []
        # retriever.search() is synchronous and CPU-heavy (FAISS + BM25 +
        # CrossEncoder rerank + MMR over the full corpus) — calling it
        # directly inside this `async def` blocks the whole event loop for
        # the entire worker process, freezing EVERY other request on that
        # worker (including unrelated health checks) for as long as this
        # search takes. With the larger corpus this can run well past
        # gunicorn's worker timeout, which then SIGKILLs the "unresponsive"
        # worker. Running it in a thread keeps the event loop free.
        # Hard timeout — a search must never be allowed to hang indefinitely.
        # asyncio.to_thread keeps the event loop free while it runs (fixed
        # above), but the underlying thread itself was observed hanging for
        # 9+ minutes on some queries with no exception ever raised — this
        # bounds worst-case latency and fails cleanly instead of leaving the
        # request (and the connection holding it) stuck indefinitely.
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(retriever.search, query, top_k=20),
                timeout=25.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"[docs] ai_search timed out after 25s for query: {query!r}")
            return []
        out = []
        for res in results:
            source = res.get("source", "")
            cat = next((k for k, v in CATEGORY_MAP.items() if v.lower() in source.lower()), "all")
            out.append({
                "id": f"ai_{res.get('chunk_id', source)}",
                "title": os.path.basename(source),
                "filename": os.path.basename(source),
                "category": cat, "path": source,
                "desc": res.get("text", "")[:150] + "...",
                "score": round(float(res.get("_rerank_score", res.get("_debug_score", 0))), 4),
            })
        return out
    except Exception as e:
        logger.error(f"[docs] AI search error: {e}")
        return []


@router.get("/feed")
def get_activity_feed():
    """Recent document activity feed."""
    import time
    from datetime import datetime
    meta = _load_metadata()
    feed = []
    for idx, doc in enumerate(meta[:10]):
        cat = doc.get("category", "other")
        name = doc.get("title", "unknown")
        if cat in ("circulars", "cgst", "igst"):
            text, kind = f"{name} Indexed & Context-Hashed", "INDEX"
        elif cat in ("highcourt", "supremecourt"):
            text, kind = f"Judicial Precedent {name} Citation Integrated", "ANALYSIS"
        else:
            text, kind = f"Document {name} Ingested successfully", "UPDATE"
        t = time.time() - idx * 300
        feed.append({"id": f"meta_{idx}", "text": text, "type": kind,
                     "time": datetime.fromtimestamp(t).strftime("%H:%M:%S"),
                     "timestamp": t})
    return feed
