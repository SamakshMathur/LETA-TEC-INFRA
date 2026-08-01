from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
import os
from pathlib import Path
from typing import List, Dict
import urllib.parse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent / "RAG_INFORMATION_DATABASE"

S3_BUCKET = os.getenv("S3_DATA_BUCKET", "")
S3_DOCS_PREFIX = "documents"
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

CATEGORY_MAP = {
    "circulars":     "Circulars",
    "notifications": "Notification",
    "forms":         "Forms",
    "flyers":        "Other APP Result",
    "brochures":     "Brochures",
    "faqs":          "FAQs",
    "reports":       "generated_reports",
    "aars":          "AAR",
    "highcourt":     "High Court Case Laws",
    "supremecourt":  "Supreme Court Case Laws",
    "acts":          "Act",
    "cgst":          "CGST",
    "export":        "Export",
    "igst":          "IGST",
    "rules":         "Rules",
    "icai":          "ICAI",
    "responses":     "Responses",
}

SUPPORTED_EXTS = {'.pdf', '.png', '.jpg', '.jpeg', '.docx', '.txt'}

MEDIA_TYPES = {
    '.pdf':  'application/pdf',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.txt':  'text/plain',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def _s3_client():
    import boto3
    return boto3.client("s3", region_name=AWS_REGION)


def _presigned_url(s3_key: str, filename: str, download: bool = False) -> str:
    disposition = "attachment" if download else "inline"
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": S3_BUCKET,
            "Key": s3_key,
            "ResponseContentDisposition": f'{disposition}; filename="{filename}"',
        },
        ExpiresIn=3600,
    )


def _serve_local(target: Path, filename: str, download: bool) -> Response:
    ext = target.suffix.lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
    disposition = "attachment" if download else "inline"
    with open(target, "rb") as f:
        content = f.read()
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


def _find_local(filename: str, folder: Path = None) -> Path | None:
    search_root = folder if folder else BASE_DIR
    if not search_root.exists():
        return None
    direct = search_root / filename
    if direct.exists():
        return direct
    found = list(search_root.rglob(filename))
    return found[0] if found else None


def _find_s3_key(filename: str, folder_name: str = None) -> str | None:
    """Search for a file in S3 and return its key, or None."""
    s3 = _s3_client()
    prefix = f"{S3_DOCS_PREFIX}/{folder_name}/" if folder_name else f"{S3_DOCS_PREFIX}/"
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if Path(obj["Key"]).name == filename:
                return obj["Key"]
    return None


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    try:
        import boto3
        s3 = boto3.client("s3", region_name=AWS_REGION)
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="documents/", MaxKeys=5)
        keys = [o["Key"] for o in resp.get("Contents", [])]
        folder_to_key = {v.lower(): k for k, v in CATEGORY_MAP.items()}
        sample_parts = [k.split("/") for k in keys]
        sample_folders = [p[1] if len(p) > 1 else "?" for p in sample_parts]
        sample_match = [folder_to_key.get(f.lower(), f"NO_MATCH({f.lower()})") for f in sample_folders]
        return {"status": "ok", "s3": bool(S3_BUCKET), "bucket": S3_BUCKET,
                "sample_keys": keys[:3], "sample_folders": sample_folders, "sample_match": sample_match}
    except Exception as e:
        return {"status": "ok", "s3": bool(S3_BUCKET), "bucket": S3_BUCKET, "error": str(e)}


# ─── View by path ─────────────────────────────────────────────────────────────

@router.get("/view_by_path")
def view_by_path(path: str, download: bool = False):
    decoded = urllib.parse.unquote(path)
    normalised = os.path.normpath(decoded.replace("\\", "/"))
    if normalised.startswith("..") or ".." in normalised.split(os.sep):
        raise HTTPException(status_code=400, detail="Invalid path")

    filename = Path(normalised).name

    # Try local filesystem only in dev (S3_BUCKET not set)
    if not S3_BUCKET and BASE_DIR.exists():
        local = BASE_DIR / normalised
        if not local.exists():
            found = list(BASE_DIR.rglob(filename))
            local = found[0] if found else None
        if local and Path(local).exists():
            return _serve_local(Path(local), filename, download)

    # Production: redirect to S3 presigned URL
    if S3_BUCKET:
        s3_key = f"{S3_DOCS_PREFIX}/{normalised.replace(os.sep, '/')}"
        try:
            url = _presigned_url(s3_key, filename, download)
            return RedirectResponse(url=url, status_code=302)
        except Exception:
            # Key not found at exact path — do a search
            key = _find_s3_key(filename)
            if key:
                return RedirectResponse(url=_presigned_url(key, filename, download), status_code=302)

    raise HTTPException(status_code=404, detail=f"File not found: {decoded}")


# ─── View by category + filename ──────────────────────────────────────────────

@router.get("/view")
def view_document(category: str, filename: str, download: bool = False):
    filename = urllib.parse.unquote(filename)
    safe_filename = os.path.basename(filename)

    # Try local filesystem only in dev (S3_BUCKET not set)
    if not S3_BUCKET and BASE_DIR.exists():
        if category.lower() in ("all", "any", "global", "ai"):
            local = _find_local(safe_filename)
        else:
            folder_name = CATEGORY_MAP.get(category.lower())
            folder = (BASE_DIR / folder_name) if folder_name else None
            local = _find_local(safe_filename, folder)
        if local:
            return _serve_local(local, safe_filename, download)

    # Production: S3 presigned URL
    if S3_BUCKET:
        folder_name = CATEGORY_MAP.get(category.lower()) if category.lower() not in ("all", "any", "global", "ai") else None
        key = _find_s3_key(safe_filename, folder_name)
        if key:
            return RedirectResponse(url=_presigned_url(key, safe_filename, download), status_code=302)

    raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found in library.")


# ─── Categories ───────────────────────────────────────────────────────────────

@router.get("/debug")
def debug_info():
    return {
        "BASE_DIR": str(BASE_DIR),
        "BASE_DIR_exists": BASE_DIR.exists(),
        "S3_BUCKET": S3_BUCKET,
        "S3_DOCS_PREFIX": S3_DOCS_PREFIX,
    }


@router.get("/categories")
def get_categories():
    stats = {}

    # S3 takes priority — if S3_BUCKET is set we're in production and local files won't exist
    if not S3_BUCKET and BASE_DIR.exists():
        for key, folder_name in CATEGORY_MAP.items():
            folder_path = BASE_DIR / folder_name
            if folder_path.exists():
                try:
                    files = [f for f in folder_path.rglob("*")
                             if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
                    stats[key] = len(files)
                except Exception:
                    stats[key] = 0
            else:
                stats[key] = 0
        return stats

    # Production: single S3 scan, count by folder prefix
    if S3_BUCKET:
        s3 = _s3_client()
        counts: dict = {key: 0 for key in CATEGORY_MAP}
        folder_to_key = {v.lower(): k for k, v in CATEGORY_MAP.items()}
        paginator = s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_DOCS_PREFIX}/"):
                for obj in page.get("Contents", []):
                    if Path(obj["Key"]).suffix.lower() not in SUPPORTED_EXTS:
                        continue
                    # Extract folder name from key: documents/FolderName/...
                    parts = obj["Key"].split("/")
                    if len(parts) >= 2:
                        folder = parts[1].lower()
                        cat_key = folder_to_key.get(folder)
                        if cat_key:
                            counts[cat_key] += 1
        except Exception as e:
            print(f"S3 categories scan error: {e}")
        return counts

    return {key: 0 for key in CATEGORY_MAP}


# ─── List all ─────────────────────────────────────────────────────────────────

@router.get("/list/all")
def list_all_documents():
    docs = []

    if not S3_BUCKET and BASE_DIR.exists():
        for cat_key, folder_name in CATEGORY_MAP.items():
            folder_path = BASE_DIR / folder_name
            if not folder_path.exists():
                continue
            all_files = [f for f in folder_path.rglob("*")
                         if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
            for idx, file_path in enumerate(all_files[:150]):
                docs.append({
                    "id": f"{cat_key}_{idx}",
                    "title": file_path.name,
                    "filename": file_path.name,
                    "size": f"{round(file_path.stat().st_size / 1024, 1)} KB",
                    "path": str(file_path.relative_to(BASE_DIR)).replace("\\", "/"),
                    "category": cat_key,
                })
        return docs

    # Production: single S3 scan across all folders
    if S3_BUCKET:
        s3 = _s3_client()
        folder_to_key = {v.lower(): k for k, v in CATEGORY_MAP.items()}
        cat_counts: dict = {k: 0 for k in CATEGORY_MAP}
        paginator = s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_DOCS_PREFIX}/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if Path(key).suffix.lower() not in SUPPORTED_EXTS:
                        continue
                    parts = key.split("/")
                    if len(parts) < 2:
                        continue
                    folder = parts[1].lower()
                    cat_key = folder_to_key.get(folder)
                    if not cat_key:
                        continue
                    if cat_counts[cat_key] >= 150:
                        continue
                    rel = key[len(f"{S3_DOCS_PREFIX}/"):]
                    docs.append({
                        "id": f"{cat_key}_{cat_counts[cat_key]}",
                        "title": Path(key).name,
                        "filename": Path(key).name,
                        "size": f"{round(obj['Size'] / 1024, 1)} KB",
                        "path": rel,
                        "category": cat_key,
                    })
                    cat_counts[cat_key] += 1
        except Exception as e:
            print(f"S3 list/all error: {e}")
    return docs


# ─── List by category ─────────────────────────────────────────────────────────

def _extract_year(key_parts: list) -> str | None:
    """Extract a 4-digit year (2010-2030) from S3 key path parts."""
    for part in key_parts:
        if part.isdigit() and 2010 <= int(part) <= 2030:
            return part
    return None


@router.get("/list/{category}")
def list_documents(category: str):
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(status_code=404, detail="Category not found")

    is_circulars = category.lower() == "circulars"
    docs = []

    if not S3_BUCKET and BASE_DIR.exists():
        folder_path = BASE_DIR / folder_name
        if not folder_path.exists():
            return []
        all_files = [f for f in folder_path.rglob("*")
                     if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
        for idx, file_path in enumerate(all_files[:300]):
            rel = str(file_path.relative_to(BASE_DIR)).replace("\\", "/")
            year = _extract_year(rel.split("/")) if is_circulars else None
            docs.append({
                "id": f"{category}_{idx}",
                "title": file_path.name,
                "desc": f"Document from {folder_name}",
                "date": "N/A",
                "size": f"{round(file_path.stat().st_size / 1024, 1)} KB",
                "filename": file_path.name,
                "path": rel,
                **({"year": year} if is_circulars else {}),
            })
        return docs

    # Production: list from S3
    if S3_BUCKET:
        s3 = _s3_client()
        prefix = f"{S3_DOCS_PREFIX}/{folder_name}/"
        paginator = s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if Path(key).suffix.lower() not in SUPPORTED_EXTS:
                        continue
                    rel = key[len(f"{S3_DOCS_PREFIX}/"):]
                    year = _extract_year(key.split("/")) if is_circulars else None
                    docs.append({
                        "id": f"{category}_{len(docs)}",
                        "title": Path(key).name,
                        "desc": f"Document from {folder_name}",
                        "date": "N/A",
                        "size": f"{round(obj['Size'] / 1024, 1)} KB",
                        "filename": Path(key).name,
                        "path": rel,
                        **({"year": year} if is_circulars else {}),
                    })
        except Exception as e:
            print(f"S3 list error for {folder_name}: {e}")
    return docs


def _group_by_year(category_id: str) -> dict:
    """Shared helper: fetch all docs for a category and bucket them by year."""
    all_docs = list_documents(category_id)
    grouped: dict = {}
    for doc in all_docs:
        year = doc.get("year") or "other"
        grouped.setdefault(year, []).append(doc)
    sorted_grouped = {}
    for y in sorted((k for k in grouped if k != "other"), reverse=True):
        sorted_grouped[y] = grouped[y]
    if "other" in grouped:
        sorted_grouped["other"] = grouped["other"]
    return sorted_grouped


@router.get("/list/circulars/by-year")
def list_circulars_by_year():
    """Return circulars grouped by year: { '2017': [...], '2018': [...], ... }"""
    return _group_by_year("circulars")


@router.get("/list/notifications/by-year")
def list_notifications_by_year():
    """Return notifications grouped by year: { '2017': [...], '2018': [...], ... }"""
    return _group_by_year("notifications")


# ─── AI Search ────────────────────────────────────────────────────────────────

@router.get("/ai_search")
async def ai_search(query: str = Query(...)):
    from app.dependencies import get_retriever
    try:
        retriever = get_retriever()
        if not retriever or not retriever.index:
            return []
        results = retriever.search(query, top_k=20)
        formatted = []
        for res in results:
            source = res.get("source", "")
            category = "all"
            for key, folder_name in CATEGORY_MAP.items():
                if folder_name.lower() in source.lower():
                    category = key
                    break
            formatted.append({
                "id": f"ai_{res.get('chunk_id', source)}",
                "title": os.path.basename(source),
                "filename": os.path.basename(source),
                "category": category,
                "path": source,
                "desc": res.get("text", "")[:150] + "...",
                "score": round(float(res.get("_rerank_score", res.get("_debug_score", 0))), 4),
            })
        return formatted
    except Exception as e:
        print(f"AI Search Error: {e}")
        return []


# ─── Activity feed ────────────────────────────────────────────────────────────

@router.get("/feed")
def get_activity_feed():
    import time
    from datetime import datetime

    feed_items = []

    if BASE_DIR.exists():
        try:
            all_files = []
            for key, folder_name in CATEGORY_MAP.items():
                folder_path = BASE_DIR / folder_name
                if folder_path.exists():
                    for f in folder_path.rglob("*"):
                        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
                            try:
                                all_files.append((f, f.stat().st_mtime, key))
                            except Exception:
                                pass
            all_files.sort(key=lambda x: x[1], reverse=True)
            for idx, (f_path, mtime, cat) in enumerate(all_files[:10]):
                dt = datetime.fromtimestamp(mtime)
                name = f_path.name
                if cat in ("circulars", "cgst", "igst"):
                    text, item_type = f"{name} Indexed & Context-Hashed", "INDEX"
                elif cat in ("highcourt", "supremecourt"):
                    text, item_type = f"Judicial Precedent {name} Citation Integrated", "ANALYSIS"
                elif cat in ("acts", "rules"):
                    text, item_type = f"Statutory Provision {name} Synced", "UPDATE"
                elif cat == "aars":
                    text, item_type = f"Advance Ruling {name} Registered", "NODE"
                else:
                    text, item_type = f"Document {name} Ingested", "UPDATE"
                feed_items.append({
                    "id": f"fs_{idx}_{int(mtime)}",
                    "text": text, "type": item_type,
                    "time": dt.strftime("%H:%M:%S"), "timestamp": mtime,
                })
        except Exception as e:
            print(f"Feed filesystem error: {e}")

    # Fallback items if database has too few
    if len(feed_items) < 7:
        fallbacks = [
            ("Customs Notification 44/2023 Import Classification Hashed", "INDEX"),
            ("Supreme Court Rule of Law Judgment Citation Integrated", "ANALYSIS"),
            ("CGST Rule 37A Reversal Condition Audit Trace Updated", "ALERT"),
            ("SEZ Zero-Rated Supply Interpretation Audit Sync Completed", "UPDATE"),
            ("Direct Tax Section 43B(h) Ingestion Matrix Mapped", "NODE"),
            ("GST Circular 177/2022 Indexed & Context-Hashed", "INDEX"),
            ("Refund Limitation Analysis Generated for Section 54(3)", "ANALYSIS"),
            ("Section 17(5) Blocked Credit Interpretation Updated", "UPDATE"),
        ]
        now = time.time()
        for idx, (text, item_type) in enumerate(fallbacks):
            t_offset = now - (idx + len(feed_items)) * 300
            dt = datetime.fromtimestamp(t_offset)
            feed_items.append({
                "id": f"fb_{idx}_{int(t_offset)}",
                "text": text, "type": item_type,
                "time": dt.strftime("%H:%M:%S"), "timestamp": t_offset,
            })

    feed_items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return feed_items[:10]
