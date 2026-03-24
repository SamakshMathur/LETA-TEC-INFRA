from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import uuid
from app.database import get_session_collection

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
def create_session(data: SessionCreate):
    collection = get_session_collection()
    session_id = str(uuid.uuid4())
    
    new_session = {
        "session_id": session_id,
        "title": data.title,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "messages": []
    }
    
    if collection is not None:
        collection.insert_one(new_session)
        # remove mongo _id
        new_session.pop("_id")
        return new_session
    else:
        # Fallback for when Mongo is not connected (local dev without DB)
        # We return a dummy session so UI doesn't crash
        return new_session

@router.get("/list", response_model=List[Session])
def list_sessions():
    collection = get_session_collection()
    if collection is None:
        return []
    
    # Sort by updated_at desc
    sessions_cursor = collection.find({}, {"_id": 0, "messages": 0}).sort("updated_at", -1)
    return list(sessions_cursor)

@router.get("/{session_id}", response_model=Session)
def get_session(session_id: str):
    collection = get_session_collection()
    if collection is None:
         # Dummy fallback
         return {"session_id": session_id, "title": "Offline Chat", "created_at": datetime.now(), "updated_at": datetime.now(), "messages": []}
    
    session = collection.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session

@router.delete("/{session_id}")
def delete_session(session_id: str):
    collection = get_session_collection()
    if collection is None:
        return {"status": "deleted (offline)", "session_id": session_id}
        
    result = collection.delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {"status": "deleted", "session_id": session_id}
