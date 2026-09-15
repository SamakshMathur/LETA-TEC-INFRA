"""
Tests for chat link-sharing and the write-ownership gate it requires.

  - GET /api/sessions/{id}: any authenticated account can view any session
    it has the id for (session_id is an unguessable UUID4 — "anyone with
    the link", the same model most link-sharing products use). Only a
    genuinely unknown id 404s. is_owner in the response distinguishes the
    owner (full access) from anyone else (read-only, enforced below).

    An earlier version gated non-owner access behind an explicit
    POST /{id}/share toggle, requiring the owner to remember a separate
    "enable sharing" step before a copied link would work for anyone else.
    Removed after a real user copied a chat's plain URL — the way anyone
    naturally would — and got a confusing "not available" because that
    flag was never set.

  - _verify_session_writable (app.py): the ownership gate that keeps
    "anyone can view" from silently also becoming "anyone can write to
    it". Without this, /ask, /ask-sync, /ask-with-file all saved messages
    scoped only by session_id, with no ownership check at all — a
    pre-existing gap that was low-risk while session ids were never
    deliberately handed to anyone but the owner, and stopped being
    low-risk the moment every session became link-viewable by design.

Uses a minimal in-memory fake collection rather than mongomock/a real
Mongo — the code under test only ever calls find_one/update_one with the
exact query/projection shapes exercised here.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ANTHROPIC_API_KEY",       "ci-placeholder")
os.environ.setdefault("MONGODB_URI",             "mongodb://localhost:27017/ci_test")
os.environ.setdefault("SECRET_KEY",              "ci-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",               "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET",     "ci-placeholder")
os.environ.setdefault("DEV_MODE",                "true")


class _FakeResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class _FakeSessionCollection:
    """In-memory stand-in for pymongo's Collection — just find_one/update_one,
    with real-enough query and inclusion/exclusion-projection semantics for
    the exact shapes sessions.py and app.py's ownership check use."""

    def __init__(self, docs):
        self._docs = {d["session_id"]: dict(d) for d in docs}

    def find_one(self, query, projection=None):
        doc = self._docs.get(query.get("session_id"))
        if doc is None:
            return None
        if "user_id" in query and doc.get("user_id") != query["user_id"]:
            return None
        result = dict(doc)
        if projection:
            include = {k for k, v in projection.items() if v}
            exclude = {k for k, v in projection.items() if not v}
            if include:
                result = {k: result[k] for k in include if k in result}
            else:
                for k in exclude:
                    result.pop(k, None)
        return result

    def update_one(self, query, update):
        doc = self._docs.get(query.get("session_id"))
        if doc is None or ("user_id" in query and doc.get("user_id") != query["user_id"]):
            return _FakeResult(0)
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        return _FakeResult(1)


# ── _verify_session_writable (app.py) ──────────────────────────────────────

@pytest.fixture
def owned_session():
    return {"session_id": "s1", "user_id": "alice"}


def test_verify_session_writable_allows_the_owner(monkeypatch, owned_session):
    from app.api import app as app_module
    fake = _FakeSessionCollection([owned_session])
    monkeypatch.setattr(app_module, "get_session_collection", lambda: fake)

    app_module._verify_session_writable("s1", "alice")  # must not raise


def test_verify_session_writable_blocks_a_non_owner(monkeypatch, owned_session):
    """The exact vulnerability: without this check, any authenticated user
    who has (or, now that every session is link-viewable by design, is
    handed) someone else's session_id could silently post messages into
    that session — "anyone can view" would have quietly become "anyone
    can write", which was never the intent."""
    from app.api import app as app_module
    from fastapi import HTTPException
    fake = _FakeSessionCollection([owned_session])
    monkeypatch.setattr(app_module, "get_session_collection", lambda: fake)

    with pytest.raises(HTTPException) as exc_info:
        app_module._verify_session_writable("s1", "mallory")
    assert exc_info.value.status_code == 403


def test_verify_session_writable_allows_a_brand_new_session_id(monkeypatch):
    """No existing document for this id — e.g. a session_id minted by the
    frontend before /api/sessions/new's response has round-tripped. Session
    creation itself is already ownership-scoped there; this check has
    nothing to gate for an id with no document yet."""
    from app.api import app as app_module
    fake = _FakeSessionCollection([])
    monkeypatch.setattr(app_module, "get_session_collection", lambda: fake)

    app_module._verify_session_writable("brand-new-id", "alice")  # must not raise


def test_verify_session_writable_noop_for_no_session_id(monkeypatch, owned_session):
    from app.api import app as app_module
    fake = _FakeSessionCollection([owned_session])
    monkeypatch.setattr(app_module, "get_session_collection", lambda: fake)

    app_module._verify_session_writable(None, "anyone")  # must not raise


# ── get_session (sessions.py) ───────────────────────────────────────────────

@pytest.fixture
def sessions_module():
    from app.api import sessions as sessions_module
    return sessions_module


def test_get_session_owner_sees_it_as_owner(monkeypatch, sessions_module):
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [],
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)
    monkeypatch.setattr(sessions_module, "_load_session_messages", lambda sid, fb: fb)

    result = sessions_module.get_session("s1", current_user={"username": "alice"})
    assert result["is_owner"] is True


def test_get_session_non_owner_can_view_it_too_read_only(monkeypatch, sessions_module):
    """The actual reported bug: a real user copied a chat's plain URL and
    shared it, expecting anyone who opened it to genuinely see the chat.
    Any authenticated account can now view any session it has the id
    for — this pins that a non-owner gets real content back (not a 404),
    just flagged is_owner:False so the frontend renders it read-only."""
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [],
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)
    monkeypatch.setattr(sessions_module, "_load_session_messages", lambda sid, fb: fb)

    result = sessions_module.get_session("s1", current_user={"username": "mallory"})
    assert result["is_owner"] is False
    assert result["session_id"] == "s1"  # real content, not a stub


def test_get_session_unknown_id_still_404s(monkeypatch, sessions_module):
    """Not "anyone can view anything" — only a session_id that actually
    exists. A guessed/mistyped/deleted id still 404s for everyone,
    identical to before link-sharing existed at all."""
    from fastapi import HTTPException
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [],
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)

    with pytest.raises(HTTPException) as exc_info:
        sessions_module.get_session("does-not-exist", current_user={"username": "mallory"})
    assert exc_info.value.status_code == 404
