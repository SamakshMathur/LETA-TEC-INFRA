from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import uuid
from app.database import get_session_collection
from app.security import get_current_user

router = APIRouter()

class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"

class Session(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[Dict] = []

@router.post("/new", response_model=Session)
def create_session(data: SessionCreate, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    session_id = str(uuid.uuid4())
    user_id = current_user["username"]

    new_session = {
        "session_id": session_id,
        "user_id": user_id,
        "title": data.title,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "messages": []
    }

    if collection is not None:
        collection.insert_one(new_session)
        new_session.pop("_id")
        return new_session
    else:
        return new_session

@router.get("/list", response_model=List[Session])
def list_sessions(current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return []

    user_id = current_user["username"]
    sessions_cursor = collection.find(
        {"user_id": user_id},
        {"_id": 0, "messages": 0}
    ).sort("updated_at", -1)
    return list(sessions_cursor)

@router.get("/{session_id}", response_model=Session)
def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return {"session_id": session_id, "title": "Offline Chat", "created_at": datetime.now(), "updated_at": datetime.now(), "messages": []}

    user_id = current_user["username"]
    session = collection.find_one({"session_id": session_id, "user_id": user_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session

@router.delete("/{session_id}")
def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return {"status": "deleted (offline)", "session_id": session_id}

    user_id = current_user["username"]
    result = collection.delete_one({"session_id": session_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "deleted", "session_id": session_id}
