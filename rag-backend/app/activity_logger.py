import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Request

from app.database import get_activity_log_collection

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "authentication",
    "system",
    "ai",
    "draft",
    "documents",
    "search",
}


def _get_user_value(user: Any, key: str) -> Optional[Any]:
    if not user:
        return None

    if isinstance(user, dict):
        return user.get(key)

    return getattr(user, key, None)


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else None


def log_activity(
    *,
    user: Any = None,
    action: str,
    category: str,
    metadata: Optional[dict] = None,
    request: Optional[Request] = None,
    success: bool = True,
    duration: Optional[float] = None,
) -> None:
    """Write an activity event to MongoDB without affecting the request."""
    try:
        if category not in VALID_CATEGORIES:
            logger.warning(f"Unknown activity category: {category}")

        collection = get_activity_log_collection()
        if collection is None:
            logger.warning("Activity logging skipped: MongoDB unavailable")
            return

        duration_ms = None
        if duration is not None:
            duration_ms = round(duration, 2)

        document = {
            "user_id": _get_user_value(user, "id") or _get_user_value(user, "_id"),
            "username": _get_user_value(user, "username"),
            "phone": _get_user_value(user, "phone"),
            "email": _get_user_value(user, "email"),
            "timestamp": datetime.utcnow(),
            "action": action,
            "category": category,
            "metadata": metadata or {},
            "ip_address": _client_ip(request),
            "user_agent": request.headers.get("user-agent") if request else None,
            "request_id": getattr(getattr(request, "state", None), "query_id", None),
            "success": success,
            "duration_ms": duration_ms,
        }

        collection.insert_one(document)
    except Exception as e:
        logger.warning(f"Activity logging failed: {e}")
