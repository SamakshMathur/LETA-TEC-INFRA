"""
Shared pytest fixtures.

The app is imported once per session.  All I/O is mocked at the boundary:
  - classify_intent  → returns a fixed intent dict (no LLM call)
  - get_db / get_session_collection → returns None (no MongoDB needed)

Tests that exercise pure-Python functions (parse_markers, _coerce_session_doc,
check_hallucinated_numbers, build_keyword_queries) import them directly and
need no mocking at all.
"""
import os
import sys
import pytest

# Make 'app' importable without installing as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Fake env so config.py reads don't raise ───────────────────────────────────
os.environ.setdefault("ANTHROPIC_API_KEY",      "ci-placeholder")
os.environ.setdefault("MONGODB_URI",             "mongodb://localhost:27017/ci_test")
os.environ.setdefault("SECRET_KEY",             "ci-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",              "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET",    "ci-placeholder")
os.environ.setdefault("FAST2SMS_API_KEY",       "ci-placeholder")
os.environ.setdefault("RESEND_API_KEY",         "ci-placeholder")
os.environ.setdefault("RAZORPAY_KEY_ID",        "ci-placeholder")
os.environ.setdefault("RAZORPAY_KEY_SECRET",    "ci-placeholder")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET","ci-placeholder")
os.environ.setdefault("DEV_MODE",               "true")


@pytest.fixture(scope="session")
def fastapi_app(monkeypatch_session):
    """
    Import and return the FastAPI app with all live I/O mocked out.

    Mocks applied once for the entire test session (not per-test) because
    importing app.api.app is expensive and the mocks are stateless.
    """
    # Patch classify_intent before app.py is imported so it never reaches Anthropic.
    monkeypatch_session.setattr(
        "app.routing.intent_classifier.classify_intent",
        lambda q: {"intent": "general", "confidence": 0.9, "method": "mock"},
    )
    # Patch DB accessors so health endpoint and session endpoints return gracefully.
    monkeypatch_session.setattr("app.database.get_db",                lambda: None, raising=False)
    monkeypatch_session.setattr("app.database.get_session_collection", lambda: None, raising=False)

    from app.api.app import app as _app
    return _app


@pytest.fixture(scope="session")
def monkeypatch_session(request):
    """Session-scoped monkeypatch (pytest's built-in is function-scoped only)."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session")
def client(fastapi_app):
    """ASGI test client — no live server, no network."""
    from starlette.testclient import TestClient
    # raise_server_exceptions=False so a 500 shows up as a 500 response rather
    # than a test exception — lets us assert on the status code directly.
    with TestClient(fastapi_app, raise_server_exceptions=False) as c:
        yield c
