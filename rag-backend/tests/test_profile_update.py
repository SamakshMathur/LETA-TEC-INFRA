"""
Tests for PATCH /api/auth/me — the profile-update endpoint added to fix a
real gap found during a UX audit: there was no way for any user to view or
edit their own account details at all (the only nav entry pointing at a
settings page 404'd). Specifically, a phone-only signup had no way to ever
add an email — the reason payment receipt emails render blank for most
users, since email delivery has always been best-effort but nothing let
someone actually provide one after the fact.

Deliberately scoped to full_name and email only, not phone — phone is
what OTP login resolves an account by, and deserves its own
verify-the-new-number-belongs-to-you flow rather than a bare text field.
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


class _RealisticFakeUserCollection:
    """Mimics real pymongo.Collection's __bool__/__len__, which both
    unconditionally raise NotImplementedError — matching the established
    fake pattern in this test suite (test_payments.py, test_plan_enforcement.py)
    so a naive truthy-by-default mock can't mask a regression of that bug."""

    def __init__(self, docs=None):
        self._docs = {d["username"]: dict(d) for d in (docs or [])}
        self.update_calls = []

    def __bool__(self):
        raise NotImplementedError(
            "Collection objects do not implement truth value testing or bool(). "
            "Please compare with None instead: collection is not None"
        )

    __len__ = __bool__

    def find_one(self, query, projection=None):
        if "username" in query:
            doc = self._docs.get(query["username"])
        elif "email" in query:
            doc = next((d for d in self._docs.values() if d.get("email") == query["email"]), None)
        else:
            doc = None
        if doc is None:
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
        doc = self._docs.setdefault(query["username"], {"username": query["username"]})
        self.update_calls.append((query, update))
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        return type("Result", (), {"matched_count": 1, "modified_count": 1})()


def _current_user(username="alice", **overrides):
    return {"username": username, "full_name": "Alice", "phone": "9876543210", "role": "user", **overrides}


@pytest.mark.asyncio
async def test_update_me_sets_full_name(monkeypatch):
    from app.api import auth

    fake_users = _RealisticFakeUserCollection([{"username": "alice", "full_name": "Alice"}])
    monkeypatch.setattr(auth, "get_user_collection", lambda: fake_users)

    result = await auth.update_me(
        auth.ProfileUpdate(full_name="Alice Sharma"),
        request=None,
        current_user=_current_user(),
    )
    assert result["full_name"] == "Alice Sharma"


@pytest.mark.asyncio
async def test_update_me_adds_an_email_for_a_phone_only_signup(monkeypatch):
    """The actual reported gap: a phone-only account had no way to ever
    add an email, which is why receipt emails render blank for most users."""
    from app.api import auth

    fake_users = _RealisticFakeUserCollection([{"username": "user_543210", "full_name": "Bob"}])
    monkeypatch.setattr(auth, "get_user_collection", lambda: fake_users)

    result = await auth.update_me(
        auth.ProfileUpdate(email="bob@example.com"),
        request=None,
        current_user=_current_user(username="user_543210"),
    )
    assert result["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_update_me_rejects_an_email_already_used_by_another_account(monkeypatch):
    from app.api import auth
    from fastapi import HTTPException

    fake_users = _RealisticFakeUserCollection([
        {"username": "alice", "email": "shared@example.com"},
        {"username": "mallory"},
    ])
    monkeypatch.setattr(auth, "get_user_collection", lambda: fake_users)

    with pytest.raises(HTTPException) as exc_info:
        await auth.update_me(
            auth.ProfileUpdate(email="shared@example.com"),
            request=None,
            current_user=_current_user(username="mallory"),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_me_allows_resubmitting_your_own_existing_email(monkeypatch):
    """Not a conflict — this must not false-positive as 'taken' just
    because it finds the same account that's making the request."""
    from app.api import auth

    fake_users = _RealisticFakeUserCollection([{"username": "alice", "email": "alice@example.com"}])
    monkeypatch.setattr(auth, "get_user_collection", lambda: fake_users)

    result = await auth.update_me(
        auth.ProfileUpdate(email="alice@example.com", full_name="Alice Updated"),
        request=None,
        current_user=_current_user(username="alice"),
    )
    assert result["email"] == "alice@example.com"
    assert result["full_name"] == "Alice Updated"


@pytest.mark.asyncio
async def test_update_me_rejects_an_invalid_email_format(monkeypatch):
    from pydantic import ValidationError

    from app.api import auth
    with pytest.raises(ValidationError):
        auth.ProfileUpdate(email="not-an-email")


def test_update_me_rejects_a_too_short_full_name():
    from pydantic import ValidationError
    from app.api import auth

    with pytest.raises(ValidationError):
        auth.ProfileUpdate(full_name="A")


@pytest.mark.asyncio
async def test_update_me_with_no_fields_is_a_harmless_no_op(monkeypatch):
    from app.api import auth

    fake_users = _RealisticFakeUserCollection([{"username": "alice", "full_name": "Alice"}])
    monkeypatch.setattr(auth, "get_user_collection", lambda: fake_users)

    result = await auth.update_me(
        auth.ProfileUpdate(),
        request=None,
        current_user=_current_user(),
    )
    assert result["username"] == "alice"
    assert len(fake_users.update_calls) == 0  # no write happened at all
