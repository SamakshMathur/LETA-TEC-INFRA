"""
Targeted regression tests — each guards a bug class that already happened in
this codebase.  The goal is not broad coverage; it's making sure the same
failure modes cannot slip through undetected a second time.

Test 1 — App startup smoke test
  Guards: any import-time crash (AttributeError, NameError, SyntaxError) that
  means the first real request to the live service fails immediately.
  Directly prevents recurrence of: prompt.py regression, utc_now migration
  syntax error, inactive_paths AttributeError.

Test 2 — route_query() return shape
  Guards: keyword-vs-LLM classifier returning wrong shape or missing keys,
  which caused KeyError crashes deep in the /ask handler.
  The monkeypatched classify_intent returns "general" — exercises the routing
  path without any Anthropic API call.

Test 3 — parse_markers() citation format (parenthesis, not square bracket)
  Guards: a format mismatch between the prompt instruction ("write (S1)") and
  the regex ("find [S1]") that silently broke citation binding — any answer
  with the correct format produced zero citations.
  This test will fail the moment either side changes incompatibly.

Test 4 — _coerce_session_doc() with a malformed legacy document
  Guards: the /api/sessions/list 500 error caused by old MongoDB documents
  that pre-date a required field (message_id was added after some messages
  were already saved).  The coercion must return a usable dict, never raise.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Ensure env vars are set before any app module is imported
os.environ.setdefault("ANTHROPIC_API_KEY",      "ci-placeholder")
os.environ.setdefault("MONGODB_URI",            "mongodb://localhost:27017/ci_test")
os.environ.setdefault("SECRET_KEY",             "ci-placeholder-32-char-secret!!")
os.environ.setdefault("REDIS_URL",              "redis://localhost:6379")
os.environ.setdefault("ADMIN_MASTER_SECRET",    "ci-placeholder")
os.environ.setdefault("FAST2SMS_API_KEY",       "ci-placeholder")
os.environ.setdefault("RESEND_API_KEY",         "ci-placeholder")
os.environ.setdefault("RAZORPAY_KEY_ID",        "ci-placeholder")
os.environ.setdefault("RAZORPAY_KEY_SECRET",    "ci-placeholder")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET","ci-placeholder")
os.environ.setdefault("DEV_MODE",               "true")


# =============================================================================
# Test 1 — App startup smoke test
# =============================================================================

def test_health_endpoint_responds(monkeypatch):
    """
    The /api/health endpoint must respond with valid JSON — never 500.

    In test context _warmup_complete is False (startup event doesn't run),
    so 503 is the expected status.  What we're checking is that the app
    imports, the route resolves, and the response is valid JSON — not that
    everything is warmed up.
    """
    # Patch I/O before importing app to avoid DB connections
    monkeypatch.setattr(
        "app.routing.intent_classifier.classify_intent",
        lambda q: {"intent": "general", "confidence": 0.9, "method": "mock"},
        raising=False,
    )

    from app.api.app import app
    from starlette.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    # Accept 200 (warmed up) or 503 (still warming up — normal in test context).
    assert response.status_code in (200, 503), (
        f"Unexpected status from /api/health: {response.status_code}\n{response.text}"
    )

    body = response.json()
    assert "status" in body, f"/api/health must return a JSON body with 'status': {body}"
    assert body["status"] in ("active", "warming_up"), (
        f"Unexpected status value: {body['status']!r}"
    )


# =============================================================================
# Test 2 — route_query() return shape
# =============================================================================

def test_route_query_returns_required_keys(monkeypatch):
    """
    route_query() must always return a dict with use_sources, mode, and
    domain_paths regardless of the question or intent classification result.

    Monkeypatching classify_intent avoids an Anthropic API call in CI.
    Exercises the routing logic itself — the same code that runs in production.
    """
    monkeypatch.setattr(
        "app.routing.intent_classifier.classify_intent",
        lambda q: {"intent": "general", "confidence": 0.9, "method": "mock"},
    )

    from app.routing.router import route_query

    sample_questions = [
        "What is the GST rate on construction services?",
        "Compare CGST and IGST for inter-state supply",
        "HSN code for mobile phones",
        "Draft show cause notice reply for ITC mismatch",
    ]

    for question in sample_questions:
        result = route_query(question)
        assert isinstance(result, dict), f"route_query must return dict, got {type(result)}"
        assert "use_sources" in result, f"Missing 'use_sources' key for: {question!r}"
        assert "mode" in result, f"Missing 'mode' key for: {question!r}"
        assert "domain_paths" in result, f"Missing 'domain_paths' key for: {question!r}"
        assert isinstance(result["use_sources"], list), "'use_sources' must be a list"
        assert len(result["use_sources"]) > 0, "'use_sources' must not be empty"


# =============================================================================
# Test 3 — parse_markers() citation format: parenthesis form, not square bracket
# =============================================================================

def test_parse_markers_uses_parenthesis_form():
    """
    The LLM prompt instructs the model to write citations as (S1), (S2), etc.
    parse_markers() must find those markers and NOT find the square-bracket
    form [S1] used in context-block headers.

    This test will fail the moment either side changes — if the prompt switches
    to square brackets, or if the regex switches to match parentheses, the test
    catches the mismatch before it reaches production.
    """
    from app.generation.context_builder import parse_markers

    marker_map = [
        {"title": "CGST Act Section 17(5)", "page": 12, "rel_path": "acts/cgst.pdf"},
        {"title": "CBIC Circular 136/2021",  "page": 1,  "rel_path": "circulars/136.pdf"},
        {"title": "Notification 12/2017",    "page": 3,  "rel_path": "notifs/12_2017.pdf"},
    ]

    # ── Parenthesis form: MUST be found ─────────────────────────────────────
    answer_with_parens = (
        "ITC on motor vehicles is blocked under Section 17(5)(a) of the CGST Act (S1). "
        "However, CBIC Circular 136/2021 (S2) clarified exceptions for passenger transport."
    )
    result = parse_markers(answer_with_parens, marker_map)
    assert len(result["citations"]) == 2, (
        f"Expected 2 resolved citations for (S1)(S2) answer, got {result['citations']}"
    )
    assert result["citations"][0]["title"] == "CGST Act Section 17(5)"
    assert result["citations"][1]["title"] == "CBIC Circular 136/2021"
    assert result["unresolved"] == [], f"Expected no unresolved markers: {result['unresolved']}"

    # ── Square-bracket form: must NOT be found ───────────────────────────────
    # These appear in context block headers: "SOURCE [S1] ..." — they should
    # never be confused with inline citations.
    answer_with_brackets = (
        "ITC on motor vehicles is blocked under Section 17(5)(a) of the CGST Act [S1]. "
        "However, CBIC Circular [S2] clarified exceptions."
    )
    result_brackets = parse_markers(answer_with_brackets, marker_map)
    assert len(result_brackets["citations"]) == 0, (
        f"Square-bracket [Sn] must NOT be parsed as citations — "
        f"got {result_brackets['citations']}"
    )

    # ── Out-of-range marker: recorded as unresolved, never silently skipped ──
    answer_out_of_range = "According to (S5), GST applies."
    result_oor = parse_markers(answer_out_of_range, marker_map)
    assert len(result_oor["citations"]) == 0
    assert "(S5)" in result_oor["unresolved"], (
        f"Out-of-range marker must appear in 'unresolved': {result_oor}"
    )


# =============================================================================
# Test 4 — _coerce_session_doc() with malformed / legacy documents
# =============================================================================

def test_coerce_session_doc_handles_legacy_documents():
    """
    _coerce_session_doc() must return a clean dict for any MongoDB document,
    including old ones that pre-date required fields — never raise, never
    produce a ValidationError that collapses the /api/sessions/list endpoint.

    Directly guards the bug class that caused /api/sessions/list to return 500
    for users who had sessions saved before message_id was introduced.
    """
    from app.api.sessions import _coerce_session_doc

    # ── Case 1: fully valid modern document ─────────────────────────────────
    modern_doc = {
        "session_id": "sess_001",
        "title": "GST on construction",
        "message_count": 2,
        "messages": [
            {
                "message_id": "msg_abc",
                "role": "user",
                "content": "What is the GST rate?",
                "timestamp": "2026-01-01T10:00:00+00:00",
            },
            {
                "message_id": "msg_def",
                "role": "assistant",
                "content": "The GST rate is 18%.",
                "timestamp": "2026-01-01T10:00:05+00:00",
            },
        ],
    }
    result = _coerce_session_doc(modern_doc)
    assert result["session_id"] == "sess_001"
    assert len(result["messages"]) == 2

    # ── Case 2: legacy document — missing message_id (pre-feature) ──────────
    legacy_doc = {
        "session_id": "sess_legacy",
        "title": "Old session",
        "messages": [
            {"role": "user", "content": "Hello"},          # no message_id
            {"role": "assistant", "content": "Hi there."},  # no message_id, no timestamp
        ],
    }
    result_legacy = _coerce_session_doc(legacy_doc)
    assert result_legacy["session_id"] == "sess_legacy"
    # Both messages must survive coercion — missing message_id gets generated
    assert len(result_legacy["messages"]) == 2
    for msg in result_legacy["messages"]:
        assert "message_id" in msg and msg["message_id"], (
            "Coerced message must have a non-empty message_id"
        )

    # ── Case 3: empty messages list — must not crash ─────────────────────────
    empty_doc = {"session_id": "sess_empty", "messages": []}
    result_empty = _coerce_session_doc(empty_doc)
    assert result_empty["session_id"] == "sess_empty"
    assert result_empty["messages"] == []

    # ── Case 4: completely malformed message — must be dropped, not crash ────
    malformed_doc = {
        "session_id": "sess_bad",
        "messages": [
            {"role": "user", "content": "Good question"},
            None,       # should be skipped
            "not a dict",  # should be skipped
            {},         # empty dict — should coerce with defaults or be skipped
        ],
    }
    # Must not raise regardless of message content
    result_bad = _coerce_session_doc(malformed_doc)
    assert result_bad["session_id"] == "sess_bad"
    # At minimum the valid message survives; bad ones are dropped
    assert isinstance(result_bad["messages"], list)
