import logging
import uuid
import json
from datetime import datetime
from app.utils.time import utc_now
from app.database import get_db
from app.config import ai_log_context

logger = logging.getLogger(__name__)

def init_ai_log(
    user_id: str, 
    username: str | None, 
    query: str, 
    endpoint: str,
    session_id: str | None = None,
    request_id: str | None = None,
    client_ip: str | None = None
):
    """Initializes the AI log context for the current request context."""
    log_data = {
        "query_id": request_id or str(uuid.uuid4()),
        "timestamp": utc_now(),
        "user_id": user_id,
        "username": username,
        "endpoint": endpoint,
        "query": query,
        "query_length": len(query) if query else 0,
        "draft_type": None,
        "model_used": "unknown",
        "retrieved_chunks": 0,
        "citations_count": 0,
        "retrieval_time_ms": 0.0,
        "reranker_time_ms": 0.0,
        "generation_time_ms": 0.0,
        "total_latency_ms": 0.0,
        "estimated_prompt_tokens": 0,
        "estimated_completion_tokens": 0,
        "response_length": 0,
        "cache_hit": False,
        "success": False,
        "http_status": 200,
        "error_message": None,
        "session_id": session_id,
        "request_id": request_id,
        "client_ip": client_ip
    }
    ai_log_context.set(log_data)
    return log_data

def update_ai_log(**kwargs):
    """Updates fields of the active AI log context."""
    ctx = ai_log_context.get()
    if ctx is not None:
        for k, v in kwargs.items():
            ctx[k] = v

def commit_ai_log(success: bool = True, http_status: int = 200, error_message: str | None = None):
    """Persists the request-scoped AI log context to MongoDB's ai_query_analytics collection."""
    log_data = ai_log_context.get()
    if not log_data or log_data.get("_committed"):
        return

    log_data["_committed"] = True
    log_data["success"] = success
    log_data["http_status"] = http_status
    log_data["error_message"] = error_message
    
    # Calculate total latency
    start_time = log_data.get("timestamp")
    if start_time:
        delta = utc_now() - start_time
        log_data["total_latency_ms"] = round(delta.total_seconds() * 1000.0, 2)

    # Estimate prompt/completion tokens if not explicitly set
    if not log_data.get("estimated_completion_tokens") and log_data.get("response_length"):
        log_data["estimated_completion_tokens"] = log_data["response_length"] // 4

    # Save to MongoDB
    try:
        db = get_db()
        if db is not None:
            db["ai_query_analytics"].insert_one(log_data)
        else:
            logger.warning("Database unavailable — AI Query log not persisted")
    except Exception as e:
        logger.error(f"Failed to persist AI Query log to MongoDB: {e}", exc_info=True)

    # Structured Logging
    try:
        tokens = log_data.get("estimated_prompt_tokens", 0) + log_data.get("estimated_completion_tokens", 0)
        structured_log = {
            "query_id": log_data.get("query_id"),
            "user": log_data.get("username") or log_data.get("user_id"),
            "latency_ms": int(log_data.get("total_latency_ms", 0)),
            "retrieval_ms": int(log_data.get("retrieval_time_ms", 0)),
            "generation_ms": int(log_data.get("generation_time_ms", 0)),
            "tokens": tokens,
            "cache_hit": log_data.get("cache_hit", False),
            "success": success
        }
        logger.info(json.dumps(structured_log))
    except Exception as e:
        logger.error(f"Failed to emit structured log: {e}")
