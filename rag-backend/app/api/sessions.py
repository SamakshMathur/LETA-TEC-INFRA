from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timezone
import uuid
import logging

from app.database import get_session_collection
from app.security import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG
# =============================================================================

MAX_MESSAGES_PER_SESSION = 500
MAX_MESSAGE_LENGTH = 25000

# =============================================================================
# MODELS
# =============================================================================

class SessionCreate(BaseModel):
    title: Optional[str] = Field(
        default="New Chat",
        max_length=120
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if v is None:
            return "New Chat"

        v = v.strip()

        if not v:
            return "New Chat"

        return v[:120]


class MessageInput(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    metadata: Optional[Dict[str, Any]] = None
    citations: Optional[List[Dict[str, Any]]] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        v = v.strip()

        if not v:
            raise ValueError("Message content cannot be empty")

        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message too large. Max length = {MAX_MESSAGE_LENGTH}"
            )

        return v


class Message(BaseModel):
    message_id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    timestamp: datetime


class Session(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    messages: List[Message] = []


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int

# =============================================================================
# HELPERS
# =============================================================================

def utc_now():
    return datetime.now(timezone.utc)


def sanitize_session(session: dict) -> dict:
    session.pop("_id", None)
    return session


# =============================================================================
# CREATE SESSION
# =============================================================================

@router.post(
    "/new",
    response_model=Session,
    status_code=status.HTTP_201_CREATED
)
def create_session(
    data: SessionCreate,
    current_user: dict = Depends(get_current_user)
):
    collection = get_session_collection()

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )

    now = utc_now()

    new_session = {
        "session_id": str(uuid.uuid4()),
        "user_id": current_user["username"],
        "title": data.title,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "messages": [],
    }

    collection.insert_one(new_session)

    logger.info(
        f"Session created | user={current_user['username']} "
        f"| session={new_session['session_id']}"
    )

    return sanitize_session(new_session)


# =============================================================================
# LIST USER SESSIONS
# =============================================================================

@router.get(
    "/list",
    response_model=List[SessionSummary]
)
def list_sessions(
    current_user: dict = Depends(get_current_user)
):

    collection = get_session_collection()

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )

    sessions_cursor = collection.find(
        {
            "user_id": current_user["username"]
        },
        {
            "_id": 0,
            "messages": 0,
        }
    ).sort("updated_at", -1)

    return list(sessions_cursor)


# =============================================================================
# GET SINGLE SESSION
# =============================================================================

@router.get(
    "/{session_id}",
    response_model=Session
)
def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):

    collection = get_session_collection()

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )

    session = collection.find_one(
        {
            "session_id": session_id,
            "user_id": current_user["username"],
        },
        {
            "_id": 0,
        }
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return session

class SessionRename(BaseModel):
    title: str

@router.patch("/{session_id}/rename")
def rename_session(session_id: str, data: SessionRename, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return {"session_id": session_id, "title": data.title}
    user_id = current_user["username"]
    result = collection.update_one(
        {"session_id": session_id, "user_id": user_id},
        {"$set": {"title": data.title, "updated_at": datetime.now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "title": data.title}

@router.get("/search", response_model=List[Session])
def search_sessions(q: str, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return []
    user_id = current_user["username"]
    regex = {"$regex": q, "$options": "i"}
    sessions_cursor = collection.find(
        {"user_id": user_id, "$or": [
            {"title": regex},
            {"messages.content": regex},
        ]},
        {"_id": 0, "messages": 0}
    ).sort("updated_at", -1).limit(20)
    return list(sessions_cursor)

@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):

    collection = get_session_collection()

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )

    result = collection.delete_one({
        "session_id": session_id,
        "user_id": current_user["username"],
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    logger.info(
        f"Session deleted | user={current_user['username']} "
        f"| session={session_id}"
    )

    return {
        "status": "deleted",
        "session_id": session_id,
    }


# =============================================================================
# CLEAR SESSION MESSAGES
# =============================================================================

@router.delete("/{session_id}/messages")
def clear_session_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):

    collection = get_session_collection()

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )

    result = collection.update_one(
        {
            "session_id": session_id,
            "user_id": current_user["username"],
        },
        {
            "$set": {
                "messages": [],
                "message_count": 0,
                "updated_at": utc_now(),
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    logger.info(
        f"Session cleared | user={current_user['username']} "
        f"| session={session_id}"
    )

    return {
        "status": "cleared",
        "session_id": session_id,
    }


# =============================================================================
# SESSION HEALTH
# =============================================================================

@router.get("/health/check")
def session_health():

    collection = get_session_collection()

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable"
        )

    return {
        "status": "healthy",
        "service": "sessions",
        "database": "connected",
        "timestamp": utc_now(),
    }
