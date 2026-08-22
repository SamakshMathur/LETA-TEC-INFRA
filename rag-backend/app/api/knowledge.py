from fastapi import APIRouter, Request, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from typing import Optional, List
from app.services.knowledge_service import KnowledgeService
from app.database import get_db
from app.security import get_current_admin
from datetime import datetime

router = APIRouter()

def _get_user_from_request(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            from app.security import verify_token
            payload = verify_token(token, "access")
            if payload and payload.get("sub"):
                return payload.get("sub")
        except Exception:
            pass
    return "admin"

@router.post("/check-duplicate")
async def check_duplicate(request: Request, payload: dict, current_admin: dict = Depends(get_current_admin)):
    file_hash = payload.get("sha256")
    if not file_hash:
        raise HTTPException(status_code=400, detail="Missing sha256 parameter")
    duplicate = KnowledgeService.check_duplicate(file_hash)
    if duplicate:
        return {"duplicate": True, "document": {
            "document_id": duplicate["document_id"],
            "filename": duplicate["filename"],
            "uploaded_at": duplicate["uploaded_at"].isoformat() if isinstance(duplicate["uploaded_at"], datetime) else duplicate["uploaded_at"]
        }}
    return {"duplicate": False}

@router.post("/upload")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(...),
    tags: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    force: bool = Form(False),
    current_admin: dict = Depends(get_current_admin)
):
    uploader = _get_user_from_request(request)
    file_content = await file.read()
    
    tags_list = [t.strip() for t in tags.split(",")] if tags else []
    
    res, duplicate = KnowledgeService.upload_document(
        file_content=file_content,
        filename=file.filename,
        category=category,
        uploader=uploader,
        tags=tags_list,
        effective_date=effective_date,
        force=force,
        background_tasks=background_tasks
    )
    
    if res["status"] == "duplicate":
        return {
            "status": "duplicate",
            "message": res["message"],
            "duplicate_document": {
                "document_id": duplicate["document_id"],
                "filename": duplicate["filename"],
                "uploaded_at": duplicate["uploaded_at"].isoformat() if isinstance(duplicate["uploaded_at"], datetime) else duplicate["uploaded_at"]
            }
        }
    return res

@router.post("/replace/{doc_id}")
async def replace_document(
    doc_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    uploader = _get_user_from_request(request)
    file_content = await file.read()
    
    res = KnowledgeService.replace_document(
        doc_id=doc_id,
        file_content=file_content,
        filename=file.filename,
        uploader=uploader,
        background_tasks=background_tasks
    )
    return res

@router.post("/archive/{doc_id}")
async def archive_document(doc_id: str, request: Request, current_admin: dict = Depends(get_current_admin)):
    user_id = _get_user_from_request(request)
    res = KnowledgeService.archive_document(doc_id, user_id)
    return res

@router.post("/reindex/{doc_id}")
async def reindex_document(doc_id: str, request: Request, background_tasks: BackgroundTasks, current_admin: dict = Depends(get_current_admin)):
    user_id = _get_user_from_request(request)
    res = KnowledgeService.reindex_document(doc_id, user_id, background_tasks)
    return res

@router.get("/list")
async def list_documents(
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_admin: dict = Depends(get_current_admin)
):
    docs = KnowledgeService.list_documents(category, status, search, skip, limit)
    return docs

@router.get("/audit-logs")
async def get_audit_logs(skip: int = 0, limit: int = 50, current_admin: dict = Depends(get_current_admin)):
    db = get_db()
    if db is not None:
        logs = list(db["knowledge_audit_logs"].find().skip(skip).limit(limit).sort("timestamp", -1))
        for log in logs:
            log.pop("_id", None)
            if isinstance(log.get("timestamp"), datetime):
                log["timestamp"] = log["timestamp"].isoformat()
        return logs
    return []
