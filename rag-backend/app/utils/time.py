"""
Shared time utilities.

Use ``utc_now()`` everywhere instead of ``datetime.utcnow()`` (deprecated,
naive) or ad-hoc ``datetime.now(timezone.utc)`` calls scattered across the
codebase.  Having one canonical call site means timezone handling is correct
and consistent — naive-vs-aware timestamp bugs have already been fixed twice
in this project; a shared helper prevents a third.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime object."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (with +00:00 suffix)."""
    return utc_now().isoformat()
