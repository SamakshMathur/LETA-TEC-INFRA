"""
Tests for _verify_plan_active (app.py) — the server-side enforcement of the
paid plan's time limit on /ask, /ask-sync, /ask-with-file.

Before this, the time limit was enforced ONLY client-side, by SessionClock's
per-tab countdown force-logging the user out at zero. These three write
endpoints resolve identity via _get_user_info_from_req, which just checks
the JWT itself is valid — never session_end. get_current_user (used
elsewhere, e.g. /api/auth/me) already did this check; these endpoints
never called it, so anyone hitting the API directly, or whose SessionClock
timer was throttled in a backgrounded/second tab, could keep using paid
features indefinitely after their time ran out.

Found during a flow audit this session, alongside the create_order
active-plan-blocks-repurchase fix (see test_payments.py) — same root
problem (session_end only ever checked client-side or on the purchase
path), different endpoint.
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


class _FakeUserCollection:
    def __init__(self, docs=None):
        self._docs = {d["username"]: dict(d) for d in (docs or [])}

    def find_one(self, query, projection=None):
        doc = self._docs.get(query.get("username"))
        if doc is None:
            return None
        result = dict(doc)
        if projection:
            include = {k for k, v in projection.items() if v}
            for k in list(result.keys()):
                if include and k not in include:
                    result.pop(k, None)
        return result


def test_verify_plan_active_blocks_an_expired_plan(monkeypatch):
    """The core bug this closes: a user whose plan time is up must not be
    able to keep chatting just because their JWT is still (or was silently
    refreshed to be) valid."""
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException
    from app.api import app as app_module

    fake_users = _FakeUserCollection([
        {"username": "alice", "session_end": datetime.now(timezone.utc) - timedelta(minutes=1)},
    ])
    monkeypatch.setattr("app.database.get_user_collection", lambda: fake_users)

    with pytest.raises(HTTPException) as exc_info:
        app_module._verify_plan_active("alice")
    assert exc_info.value.status_code == 401
    # Same wording get_current_user's own check uses, so the frontend's
    # existing plan-expiry-vs-generic-401 split (interceptors.ts's
    # PLAN_EXPIRED_DETAIL) recognizes this the same way it already does
    # elsewhere, rather than introducing a third error shape it doesn't
    # know how to classify.
    assert exc_info.value.detail == "Session expired. Please log in again."


def test_verify_plan_active_allows_an_active_plan(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.api import app as app_module

    fake_users = _FakeUserCollection([
        {"username": "alice", "session_end": datetime.now(timezone.utc) + timedelta(hours=1)},
    ])
    monkeypatch.setattr("app.database.get_user_collection", lambda: fake_users)

    app_module._verify_plan_active("alice")  # must not raise


def test_verify_plan_active_blocks_a_user_who_never_had_a_plan(monkeypatch):
    """The real bug this was tightened to close: AskLetaWidget.tsx linked
    straight into the workspace with no plan check at all, so a freshly
    registered user — session_end never set, since only a real payment
    (_credit_session) sets it — could reach /ask with full, free, unlimited
    access. A user with no session_end AND no admin grant on record must be
    blocked, not waved through."""
    from fastapi import HTTPException
    from app.api import app as app_module

    fake_users = _FakeUserCollection([{"username": "bob"}])
    monkeypatch.setattr("app.database.get_user_collection", lambda: fake_users)

    with pytest.raises(HTTPException) as exc_info:
        app_module._verify_plan_active("bob")
    assert exc_info.value.status_code == 401
    # Deliberately different wording from the expired-plan case — telling
    # someone who never paid to "log in again" would be misleading; they
    # need to buy a plan, not re-authenticate.
    assert exc_info.value.detail == "No active plan. Please purchase a plan to continue."


def test_verify_plan_active_allows_an_admin_granted_unlimited_plan(monkeypatch):
    """admin.py's grant_plan endpoint, called with hours=None, deliberately
    $unsets session_end entirely to grant unlimited access — but always
    sets last_granted_by in the same update. That field is the reliable
    signal distinguishing "an admin genuinely granted this" from "this
    account has simply never been granted anything" — both look identical
    otherwise (session_end absent)."""
    from app.api import app as app_module

    fake_users = _FakeUserCollection([{"username": "carol", "last_granted_by": "admin"}])
    monkeypatch.setattr("app.database.get_user_collection", lambda: fake_users)

    app_module._verify_plan_active("carol")  # must not raise


def test_verify_plan_active_noop_for_no_username(monkeypatch):
    """A fully anonymous request (no JWT at all) — this function only ever
    narrows access for a real, expired user, never blocks the anonymous
    case (a separate, pre-existing concern this fix doesn't touch)."""
    from app.api import app as app_module

    def _should_not_be_called():
        raise AssertionError("must not even query the DB for a missing username")
    monkeypatch.setattr("app.database.get_user_collection", lambda: _should_not_be_called())

    app_module._verify_plan_active(None)  # must not raise


def test_verify_plan_active_exempts_admin(monkeypatch):
    """Mirrors get_current_user's own admin exemption (security.py) —
    admin has no plan/session_end at all, so this must never try to
    enforce one."""
    from app.api import app as app_module

    def _should_not_be_called():
        raise AssertionError("must not query the DB for admin")
    monkeypatch.setattr("app.database.get_user_collection", lambda: _should_not_be_called())

    app_module._verify_plan_active("admin")  # must not raise


def test_verify_plan_active_handles_db_unavailable_gracefully(monkeypatch):
    from app.api import app as app_module
    monkeypatch.setattr("app.database.get_user_collection", lambda: None)

    app_module._verify_plan_active("alice")  # must not raise
