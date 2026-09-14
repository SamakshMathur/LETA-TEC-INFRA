"""
Tests for chat-sharing access control, added alongside the feature:

  - GET /api/sessions/{id}: the owner always sees it; a non-owner sees it
    ONLY when is_shared=True (read-only — is_owner=False in the response);
    a non-owner never sees an unshared session (plain 404, identical to
    before sharing existed at all).
  - POST /api/sessions/{id}/share and /unshare: owner-only, same
    match-or-404 behavior as the existing rename/delete endpoints.
  - _verify_session_writable (app.py): the ownership gate that keeps a
    shared (read-only) session from ALSO becoming writable by someone who
    isn't its owner via /ask, /ask-sync, /ask-with-file — the real bug
    this whole feature would have reintroduced if shipped without it (a
    pre-existing gap: those endpoints saved messages scoped only by
    session_id, with no ownership check at all, which was low-risk while
    session ids were never deliberately handed to anyone but the owner,
    and stopped being low-risk the moment sharing did exactly that).

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
    who has (or is deliberately given, via sharing) someone else's
    session_id could silently post messages into that session."""
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


# ── get_session / share / unshare (sessions.py) ────────────────────────────

@pytest.fixture
def sessions_module(monkeypatch):
    from app.api import sessions as sessions_module
    return sessions_module


def test_get_session_owner_always_sees_it(monkeypatch, sessions_module):
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [], "is_shared": False,
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)
    monkeypatch.setattr(sessions_module, "_load_session_messages", lambda sid, fb: fb)

    result = sessions_module.get_session("s1", current_user={"username": "alice"})
    assert result["is_owner"] is True
    assert result["is_shared"] is False


def test_get_session_non_owner_blocked_when_not_shared(monkeypatch, sessions_module):
    """This is the exact bug reported live — silently unreachable, not
    fixed here since here it correctly raises instead of failing silent
    (the frontend's own resolveSessionRestore.test.ts covers the silent-
    failure side); this test pins the backend's half: a 404, not a leak."""
    from fastapi import HTTPException
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [], "is_shared": False,
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)

    with pytest.raises(HTTPException) as exc_info:
        sessions_module.get_session("s1", current_user={"username": "mallory"})
    assert exc_info.value.status_code == 404


def test_get_session_non_owner_allowed_read_only_when_shared(monkeypatch, sessions_module):
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [], "is_shared": True,
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)
    monkeypatch.setattr(sessions_module, "_load_session_messages", lambda sid, fb: fb)

    result = sessions_module.get_session("s1", current_user={"username": "mallory"})
    assert result["is_owner"] is False
    assert result["is_shared"] is True
    # Read access, not silence — the actual conversation content is present.
    assert result["session_id"] == "s1"


def test_share_session_owner_only(monkeypatch, sessions_module):
    from fastapi import HTTPException
    fake = _FakeSessionCollection([{"session_id": "s1", "user_id": "alice"}])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)

    result = sessions_module.share_session("s1", current_user={"username": "alice"})
    assert result == {"session_id": "s1", "is_shared": True}
    assert fake._docs["s1"]["is_shared"] is True

    with pytest.raises(HTTPException) as exc_info:
        sessions_module.share_session("s1", current_user={"username": "mallory"})
    assert exc_info.value.status_code == 404


def test_unshare_session_revokes_read_access(monkeypatch, sessions_module):
    fake = _FakeSessionCollection([{
        "session_id": "s1", "user_id": "alice", "title": "T",
        "created_at": None, "updated_at": None, "messages": [], "is_shared": True,
    }])
    monkeypatch.setattr(sessions_module, "get_session_collection", lambda: fake)
    monkeypatch.setattr(sessions_module, "_load_session_messages", lambda sid, fb: fb)

    result = sessions_module.unshare_session("s1", current_user={"username": "alice"})
    assert result == {"session_id": "s1", "is_shared": False}

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        sessions_module.get_session("s1", current_user={"username": "mallory"})
    assert exc_info.value.status_code == 404
