from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timezone
import uuid
import logging

from app.database import get_session_collection, get_message_collection
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
    client_ref: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Advisor-set client/matter tag, e.g. 'ABC Pvt Ltd — GST Audit'. "
                    "Deliberately separate from title: one client can have several "
                    "differently-titled sessions that should still share memory."
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

    @field_validator("client_ref")
    @classmethod
    def validate_client_ref(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v[:120] if v else None


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
    client_ref: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    messages: List[Message] = []


class SessionSummary(BaseModel):
    session_id: str
    # Allow legacy documents that pre-date a field to coerce cleanly instead of
    # throwing a ValidationError that collapses the whole list endpoint with a
    # generic 21-byte "Internal Server Error".
    title: str = "Untitled"
    client_ref: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0

# =============================================================================
# HELPERS
# =============================================================================

def utc_now():
    return datetime.now(timezone.utc)


def sanitize_session(session: dict) -> dict:
    session.pop("_id", None)
    return session


def _coerce_message(raw: dict) -> Optional[Message]:
    """
    Coerce a raw MongoDB message document into a Message, supplying defaults
    for any field that was added after the document was written (e.g. message_id
    was not present in messages saved before this field was introduced).
    Returns None if the document is so malformed it cannot be coerced at all.
    """
    try:
        return Message(
            message_id=raw.get("message_id") or str(uuid.uuid4()),
            role=raw.get("role", "assistant"),
            content=raw.get("content", ""),
            metadata=raw.get("metadata"),
            citations=raw.get("citations"),
            # "timestamp" is the embedded-array (legacy) field name; messages
            # saved to the separate collection (see get_session_messages
            # below) use "created_at" instead — accept either.
            timestamp=raw.get("timestamp") or raw.get("created_at") or utc_now(),
        )
    except Exception as exc:
        logger.warning(f"_coerce_message: could not coerce message — {exc!r}")
        return None


def _load_session_messages(session_id: str, embedded_fallback: list) -> list:
    """
    Messages are saved as their own documents in the "messages" collection
    (see app.py's _save_message — one document per message, not $push-ed
    into the session doc's embedded array), so that's the real source of
    truth for a session's conversation. Without this, GET /{session_id}
    silently returned an always-empty `messages: []` (the session doc's own
    embedded field, which nothing writes to anymore) — every previously
    saved consultation would show as blank when reopened.

    Falls back to the session doc's embedded array for any legacy session
    that predates the separate-collection change.
    """
    msg_collection = get_message_collection()
    if msg_collection is None:
        return embedded_fallback

    docs = list(
        msg_collection.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1)
    )
    return docs if docs else embedded_fallback


def _coerce_session_doc(doc: dict) -> dict:
    """
    Build a clean session dict from a raw MongoDB document, coercing every
    message so the FastAPI response-model validator never sees legacy
    documents that are missing required fields (e.g. message_id).
    """
    raw_messages = _load_session_messages(doc.get("session_id", ""), doc.get("messages", []))
    coerced_messages = []
    for raw_msg in raw_messages:
        m = _coerce_message(raw_msg)
        if m is not None:
            coerced_messages.append(m.model_dump())

    # message_count: prefer the stored counter but fall back to the actual
    # number of messages so the field is never stale by more than one request.
    stored_count = doc.get("message_count")
    effective_count = stored_count if stored_count is not None else len(coerced_messages)

    return {
        "session_id": doc.get("session_id", ""),
        "user_id": doc.get("user_id", ""),
        "title": doc.get("title") or "Untitled",
        "client_ref": doc.get("client_ref"),
        "created_at": doc.get("created_at") or utc_now(),
        "updated_at": doc.get("updated_at") or utc_now(),
        "message_count": effective_count,
        "messages": coerced_messages,
    }


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
        "client_ref": data.client_ref,
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
    try:
        collection = get_session_collection()

        if collection is None:
            raise HTTPException(
                status_code=500,
                detail="Database connection failed"
            )

        sessions_cursor = collection.find(
            {"user_id": current_user["username"]},
            {"_id": 0, "messages": 0},
        ).sort("updated_at", -1)

        # Coerce each document into SessionSummary defensively.  Legacy sessions
        # created before a field existed (e.g. message_count, title) would cause
        # FastAPI's response-model validation to throw an unhandled exception that
        # surfaces as a generic 21-byte "Internal Server Error" (Content-Length: 21).
        # Building the model manually lets us supply per-field defaults and log any
        # document that can't be coerced without taking down the entire list.
        results: List[SessionSummary] = []
        for doc in sessions_cursor:
            try:
                results.append(SessionSummary(
                    session_id=doc.get("session_id", ""),
                    title=doc.get("title") or "Untitled",
                    client_ref=doc.get("client_ref"),
                    created_at=doc.get("created_at"),
                    updated_at=doc.get("updated_at"),
                    message_count=doc.get("message_count") or len(doc.get("messages", [])),
                ))
            except Exception as doc_exc:
                logger.warning(
                    f"list_sessions: skipping malformed session doc "
                    f"sid={doc.get('session_id', '?')} | {doc_exc}"
                )
                continue

        return results

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"list_sessions: unexpected error for user={current_user.get('username')}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(exc)}")


# =============================================================================
# SEARCH SESSIONS
# NOTE: This route MUST be defined before /{session_id} — FastAPI matches
# routes in registration order, so the literal "/search" path would otherwise
# be swallowed by the parameterised "/{session_id}" handler first.
# =============================================================================

@router.get("/search", response_model=List[SessionSummary])
def search_sessions(q: str, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return []
    user_id = current_user["username"]
    regex = {"$regex": q, "$options": "i"}
    sessions_cursor = collection.find(
        {"user_id": user_id, "$or": [
            {"title": regex},
            {"client_ref": regex},
            {"messages.content": regex},
        ]},
        {"_id": 0, "messages": 0}
    ).sort("updated_at", -1).limit(20)

    results: List[SessionSummary] = []
    for doc in sessions_cursor:
        try:
            results.append(SessionSummary(
                session_id=doc.get("session_id", ""),
                title=doc.get("title") or "Untitled",
                client_ref=doc.get("client_ref"),
                created_at=doc.get("created_at"),
                updated_at=doc.get("updated_at"),
                message_count=doc.get("message_count", 0),
            ))
        except Exception:
            continue
    return results


# =============================================================================
# LIST CLIENT/MATTER TAGS (for autocomplete on the tagging UI)
# NOTE: Must stay above /{session_id} for the same reason as /search above.
# =============================================================================

@router.get("/client-refs")
def list_client_refs(current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return {"client_refs": []}
    user_id = current_user["username"]
    refs = collection.distinct("client_ref", {"user_id": user_id, "client_ref": {"$nin": [None, ""]}})
    return {"client_refs": sorted(refs, key=str.lower)}


# =============================================================================
# GET SINGLE SESSION
# NOTE: Keep this AFTER all literal sub-routes (e.g. /list, /search, /health/*)
# so the path parameter does not shadow them.
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

    doc = collection.find_one(
        {
            "session_id": session_id,
            "user_id": current_user["username"],
        },
        {
            "_id": 0,
        }
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Coerce every message so the response model validator never sees legacy
    # documents that are missing required fields (e.g. message_id was absent
    # before the field was introduced, causing ResponseValidationError 500s).
    try:
        return _coerce_session_doc(doc)
    except Exception as exc:
        logger.exception(
            f"get_session: coercion failed for session={session_id} | {exc}"
        )
        raise HTTPException(status_code=500, detail="Failed to load session")


# =============================================================================
# RENAME SESSION
# =============================================================================

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
        {"$set": {"title": data.title, "updated_at": utc_now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "title": data.title}


# =============================================================================
# SET CLIENT/MATTER TAG
# Separate from rename deliberately — a client can have several differently
# -titled sessions that should still share the same tag (and, later, the same
# remembered context).
# =============================================================================

class SessionClientRef(BaseModel):
    client_ref: Optional[str] = Field(default=None, max_length=120)

    @field_validator("client_ref")
    @classmethod
    def validate_client_ref(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v[:120] if v else None

@router.patch("/{session_id}/client-ref")
def set_session_client_ref(session_id: str, data: SessionClientRef, current_user: dict = Depends(get_current_user)):
    collection = get_session_collection()
    if collection is None:
        return {"session_id": session_id, "client_ref": data.client_ref}
    user_id = current_user["username"]
    result = collection.update_one(
        {"session_id": session_id, "user_id": user_id},
        {"$set": {"client_ref": data.client_ref, "updated_at": utc_now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "client_ref": data.client_ref}


# =============================================================================
# DELETE SESSION
# =============================================================================

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

    # Real messages live in their own collection (see _load_session_messages) —
    # deleting only the session doc would leave them all orphaned.
    msg_collection = get_message_collection()
    if msg_collection is not None:
        msg_collection.delete_many({"session_id": session_id})

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

    # Real messages live in their own collection (see _load_session_messages) —
    # clearing only the session doc's embedded array leaves them all in place.
    msg_collection = get_message_collection()
    if msg_collection is not None:
        msg_collection.delete_many({"session_id": session_id})

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
