"""
Admin Upload Portal
--------------------
Only accessible to users with role='admin'.

Endpoints:
  GET  /api/admin/status                      - index health, file counts per category
  POST /api/admin/upload                      - upload one or more files to a category
  GET  /api/admin/jobs/{job_id}               - check background ingestion job status
  GET  /api/admin/jobs                        - list all ingestion jobs
  GET  /api/admin/users                       - list all registered users
  POST /api/admin/users/{contact}/toggle-admin - promote/demote admin role
"""
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.security import get_current_admin, require_roles, ROLE_SUPER_ADMIN, ROLE_ADMIN
from app.api.documents import BASE_DIR, CATEGORY_MAP
from app.database import get_user_collection
from app.feed_store import make_event, publish_event
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job tracker {job_id: {status, results, ...}}
_jobs: dict = {}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt"}


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
@limiter.limit("30/minute")
async def admin_status(request: Request, current_admin: dict = Depends(get_current_admin)):
    """Returns FAISS index stats and per-category document counts."""
    import faiss
    from app.config import VECTOR_DB_PATH, CHUNKS_PATH

    index_info = {"total_vectors": 0, "dimension": 0, "status": "missing"}
    try:
        idx = faiss.read_index(VECTOR_DB_PATH)
        index_info = {"total_vectors": idx.ntotal, "dimension": idx.d, "status": "ok"}
    except Exception as e:
        index_info["error"] = str(e)

    chunks_count = 0
    try:
        with open(CHUNKS_PATH, encoding="utf-8") as f:
            chunks_count = sum(1 for _ in f)
    except Exception:
        pass

    categories = {}
    for key, folder_name in CATEGORY_MAP.items():
        folder_path = BASE_DIR / folder_name
        if folder_path.exists():
            files = [
                f for f in folder_path.rglob("*")
                if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
            ]
            categories[key] = {"folder": folder_name, "files": len(files)}
        else:
            categories[key] = {"folder": folder_name, "files": 0, "exists": False}

    return {
        "faiss_index": index_info,
        "chunks_in_corpus": chunks_count,
        "categories": categories,
        "admin": current_admin.get("username"),
    }


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload")
@limiter.limit("5/minute")
async def upload_documents(
    request: Request,
    category: str = Form(..., description="Target category key e.g. 'acts', 'circulars'"),
    files: List[UploadFile] = File(..., description="One or more files to upload"),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Upload files to a category folder and trigger incremental ingestion.
    Returns a job_id — poll /api/admin/jobs/{job_id} for progress.
    """
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category}'. Valid keys: {list(CATEGORY_MAP.keys())}"
        )

    target_dir = BASE_DIR / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for upload in files:
        filename = upload.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"'{filename}' has unsupported extension '{ext}'. Allowed: {ALLOWED_EXTENSIONS}"
            )

        dest = target_dir / filename
        if dest.exists():
            stem = dest.stem
            dest = target_dir / f"{stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"

        content = await upload.read()
        dest.write_bytes(content)
        rel_path = str(dest.relative_to(BASE_DIR)).replace("\\", "/")
        saved_files.append({"path": dest, "rel_path": rel_path, "filename": dest.name})
        logger.info(f"Admin upload: {dest.name} ({len(content)/1024:.1f} KB) → {folder_name}/")

        # ── Live feed event: document uploaded ──────────────────────────────
        _type_map = {
            "circulars": ("INDEX",    "{name} Indexed & Context-Hashed"),
            "cgst":      ("INDEX",    "CGST Document {name} Indexed"),
            "igst":      ("INDEX",    "IGST Notification {name} Hashed"),
            "notifications": ("UPDATE", "Notification {name} Synced with Central Database"),
            "highcourt": ("ANALYSIS", "High Court Judgment {name} Citation Integrated"),
            "supremecourt": ("ANALYSIS", "Supreme Court Ruling {name} Citation Integrated"),
            "acts":      ("UPDATE",   "Statutory Act {name} Synced with Central Database"),
            "rules":     ("UPDATE",   "Rules Document {name} Registered"),
            "aars":      ("NODE",     "Advance Ruling {name} Registered"),
        }
        _cat_key = category.lower()
        _etype, _tmpl = _type_map.get(_cat_key, ("INDEX", "Document {name} Ingested & Indexed"))
        _ev_text = _tmpl.format(name=dest.name)
        await publish_event(make_event(_ev_text, _etype, filename=dest.name, category=_cat_key))

    if not saved_files:
        raise HTTPException(status_code=400, detail="No files were saved")

    # Create job record
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "files": [f["filename"] for f in saved_files],
        "category": folder_name,
        "started_at": datetime.now().isoformat(),
        "results": [],
        "uploaded_by": current_admin.get("username"),
    }

    # Fire background ingestion
    import asyncio

    async def _run_ingestion():
        _jobs[job_id]["status"] = "processing"
        from app.pipeline.incremental_ingest import ingest_file
        results = []
        for f in saved_files:
            try:
                result = await run_in_threadpool(ingest_file, f["path"], f["rel_path"])
                results.append({"file": f["filename"], **result})
            except Exception as e:
                logger.error(f"Ingestion error for {f['filename']}: {e}")
                results.append({"file": f["filename"], "status": "error", "error": str(e)})

        total_chunks = sum(r.get("chunks_added", 0) for r in results)
        _jobs[job_id].update({
            "status": "done",
            "results": results,
            "total_chunks_added": total_chunks,
            "finished_at": datetime.now().isoformat(),
        })
        logger.info(f"Job {job_id} done — {len(saved_files)} files, +{total_chunks} chunks")

        # ── Live feed event: ingestion complete ──────────────────────────────
        _names = ", ".join(f["filename"] for f in saved_files[:2])
        _suffix = f" (+{len(saved_files)-2} more)" if len(saved_files) > 2 else ""
        await publish_event(make_event(
            f"Ingestion Complete — {_names}{_suffix} (+{total_chunks} vectors indexed)",
            "ALERT",
            filename=_names,
            category=folder_name,
        ))

    asyncio.create_task(_run_ingestion())

    return {
        "job_id": job_id,
        "message": f"{len(saved_files)} file(s) uploaded to '{folder_name}'. Ingestion running.",
        "files": [f["filename"] for f in saved_files],
        "poll_url": f"/api/admin/jobs/{job_id}",
    }


# ── Job Status ─────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, current_admin: dict = Depends(get_current_admin)):
    """Poll ingestion job progress."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs")
async def list_jobs(current_admin: dict = Depends(get_current_admin)):
    """List all ingestion jobs, newest first."""
    return list(reversed(list(_jobs.values())))


# ── User Management ────────────────────────────────────────────────────────────

@router.get("/users")
@limiter.limit("20/minute")
async def list_users(request: Request, current_admin: dict = Depends(get_current_admin)):
    """Returns all registered users."""
    users_col = get_user_collection()
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    return list(users_col.find({}, {"_id": 0}))


@router.post("/users/{contact}/toggle-admin")
@limiter.limit("10/minute")
async def toggle_admin_role(
    request: Request,
    contact: str,
    current_admin: dict = Depends(require_roles(ROLE_SUPER_ADMIN)),
):
    """Flip a user between role='user' and role='admin', controlled by super_admin."""
    users_col = get_user_collection()
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user = users_col.find_one(
        {"$or": [{"email": contact}, {"phone": contact}, {"username": contact}]}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent altering self
    if user.get("username") == current_admin.get("username"):
        logger.warning(f"Self role modification attempt blocked | user={current_admin.get('username')}")
        raise HTTPException(
            status_code=400,
            detail="Self-promotion or self-demotion is prohibited"
        )

    # Protect super_admin accounts
    if user.get("role") == ROLE_SUPER_ADMIN:
        logger.warning(
            f"Super Admin demotion attempt blocked | actor={current_admin.get('username')} "
            f"target={user.get('username')}"
        )
        raise HTTPException(
            status_code=400,
            detail="Role of a super_admin cannot be demoted or modified"
        )

    new_role = "user" if user.get("role") == ROLE_ADMIN else "admin"
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"role": new_role}}
    )
    logger.info(
        f"User role toggled | actor={current_admin.get('username')} target={user.get('username')} "
        f"new_role={new_role}"
    )
    return {"username": user.get("username"), "new_role": new_role}
