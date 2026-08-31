"""
quarantine.py — Shared chunk quarantine gate for LETA retrieval.

A chunk is quarantined when:
  - metadata.is_active is explicitly False, OR
  - metadata.status == "NEEDS_REVIEW"

Both the top-level (flattened) chunk dict and the nested ``metadata``
sub-dict are checked, because different ingestion paths store these
fields in different locations.
"""


def _is_quarantined(chunk: dict) -> bool:
    """Return True if *chunk* must be excluded from every retrieval path."""
    # Top-level / flattened fields
    if chunk.get("is_active") is False:
        return True
    if chunk.get("status") == "NEEDS_REVIEW":
        return True
    # Nested metadata sub-dict
    meta = chunk.get("metadata", {}) or {}
    if meta.get("is_active") is False:
        return True
    if meta.get("status") == "NEEDS_REVIEW":
        return True
    return False
