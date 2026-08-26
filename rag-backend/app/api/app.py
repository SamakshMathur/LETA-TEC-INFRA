import json
import logging
import time
import uuid

from fastapi import FastAPI, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Any, Optional
from pathlib import Path

from app.routing.router import route_query
from app.generation.context_builder import build_context

# ── Structured JSON logging setup ────────────────────────────────────────────
# Each log line is a JSON object — queryable in CloudWatch Logs Insights.
# Fields: timestamp, level, logger, message, plus any extra kwargs passed
# to logger.info(..., extra={...}).

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any extra fields (query_id, latency_ms, cache_hit, etc.)
        for key, val in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                payload[key] = val
        return json.dumps(payload, default=str)


def _configure_json_logging():
    formatter = _JsonFormatter()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(formatter)
    root.setLevel(logging.INFO)


_configure_json_logging()
logger = logging.getLogger(__name__)

# ---------- App ----------
app = FastAPI(
    title="GST Legal RAG API",
    version="1.0",
    description="In-house GST knowledge assistant",
)

# Readiness gate: ALB health check returns 503 until models are loaded.
# Prevents live traffic from hitting a task that isn't ready to serve yet.
_warmup_complete: bool = False

@app.on_event("startup")
async def _startup_tasks():
    """Seed feed store and pre-warm AI models in background."""
    import asyncio as _asyncio

    # 1. Seed in-memory event log
    try:
        from app.api.documents import get_activity_feed
        from app.feed_store import _event_log
        items = get_activity_feed()
        for item in reversed(items):
            _event_log.append(item)
        logger.info(f"Feed store seeded with {len(items)} events from filesystem")
    except Exception as e:
        logger.warning(f"Feed store seed failed (non-fatal): {e}")

    # 2. Pre-load embedding model + FAISS index so the first /ask-sync request
    #    doesn't pay the ~15-20s cold-start cost and timeout at API Gateway.
    async def _warmup():
        global _warmup_complete
        try:
            from app.dependencies import preload_all_models
            await _asyncio.to_thread(preload_all_models)
            logger.info("Startup model warmup complete")
        except Exception as e:
            logger.warning(f"Startup warmup failed (non-fatal): {e}")
        finally:
            _warmup_complete = True  # always unblock health check, even on error

    _asyncio.ensure_future(_warmup())


@app.get("/")
async def root():
    return {
        "message": "GST Legal RAG API is running.",
        "docs": "/docs",
        "health": "/api/health"
    }

from fastapi.middleware.cors import CORSMiddleware
import os

# CORS: Merge ALLOWED_ORIGINS env var with local dev origins so Vite
# preflight requests keep working even when production origins are configured.
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://letatec.com",
    "https://www.letatec.com",
    "https://main.d1q7i80dk455hq.amplifyapp.com",
]
_env_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
ALLOWED_ORIGINS = list(dict.fromkeys([*_default_origins, *_env_origins]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https://[a-z0-9-]+\.amplifyapp\.com$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# ── Security headers middleware ───────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        # Prevent browsers from MIME-sniffing the content type
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Block clickjacking — skip for document view so the frontend iframe can embed PDFs
        if not request.url.path.startswith("/api/documents/view"):
            response.headers["X-Frame-Options"] = "DENY"
        # Force HTTPS for 1 year, include subdomains
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        # Only send origin in Referer header, no full URL
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Disable browser features not needed by the API
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
        # Prevent caching of API responses (contains legal/confidential data)
        if not request.url.path.startswith("/api/documents/view"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        for h in ("server", "x-powered-by"):
            if h in response.headers:
                del response.headers[h]
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── Request size limit middleware ─────────────────────────────────────────────
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_BODY_BYTES = 20 * 1024 * 1024  # 20 MB

    async def dispatch(self, request: StarletteRequest, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.MAX_BODY_BYTES:
                from starlette.responses import JSONResponse
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)

app.add_middleware(RequestSizeLimitMiddleware)

from fastapi import Request

# ── Request logging middleware ────────────────────────────────────────────────
# Emits one JSON log line per request with fields queryable in CloudWatch:
#   query_id, method, path, status_code, latency_ms
# The /ask endpoint adds extra fields (cache_hit, domain, etc.) via its own logs.

_request_logger = logging.getLogger("leta.request")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Full query_id: LETA-YYYYMMDD-HHMMSS-XXXXXXXX (CloudWatch-searchable prefix)
    import datetime as _dt_mw
    _ts = _dt_mw.datetime.now().strftime("%Y%m%d-%H%M%S")
    _rand = str(uuid.uuid4()).replace("-", "")[:6].upper()
    query_id = f"LETA-{_ts}-{_rand}"
    request.state.query_id = query_id
    t0 = time.monotonic()

    response = await call_next(request)

    latency_ms = round((time.monotonic() - t0) * 1000, 1)
    _request_logger.info(
        f"{request.method} {request.url.path} {response.status_code}",
        extra={
            "query_id": query_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    response.headers["X-Request-ID"] = query_id
    return response

# Rate limiting — shared singleton so router modules (payments, etc.) can
# import the same Limiter without creating a circular import through app.py.
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.rate_limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global exception handler ──────────────────────────────────────────────────
# Catches any unhandled exception that escapes a route handler and returns
# structured JSON with the request_id instead of the default 22-byte plain-text
# "Internal Server Error".  Logs the full traceback so CloudWatch Logs Insights
# can correlate failures via filter request_id = "LETA-...".
#
# HTTPException and RequestValidationError are explicitly delegated back to
# FastAPI's built-in handlers so they keep their correct status codes and bodies.
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    from starlette.exceptions import HTTPException as _HTTP
    from fastapi.exceptions import RequestValidationError as _ValErr
    from fastapi.exception_handlers import (
        http_exception_handler as _http_h,
        request_validation_exception_handler as _val_h,
    )
    if isinstance(exc, _HTTP):
        return await _http_h(request, exc)
    if isinstance(exc, _ValErr):
        return await _val_h(request, exc)

    import traceback as _tb
    query_id = getattr(request.state, "query_id", "no-id")
    logger.error(
        f"Unhandled exception | request_id={query_id} "
        f"| path={request.url.path} "
        f"| {type(exc).__name__}: {exc!r}\n{_tb.format_exc()}"
    )
    from starlette.responses import JSONResponse as _J
    return _J(
        status_code=500,
        content={"detail": "An unexpected error occurred.", "request_id": query_id},
    )

def _get_user_info_from_req(request: Request) -> tuple:
    user_id = "anonymous"
    username = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            from app.security import verify_token
            payload = verify_token(token, "access")
            if payload:
                user_id = payload.get("sub", "anonymous")
                username = payload.get("sub")
        except Exception:
            pass
    return user_id, username

from app.api import documents
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])

from app.api import advisory
app.include_router(advisory.router, prefix="/api/advisory", tags=["Advisory"])

from app.api import sessions
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])

from app.api import auth
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

from app.api import templates
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])

from app.api import admin
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

from app.api import knowledge
app.include_router(knowledge.router, prefix="/api/admin/knowledge", tags=["Admin Knowledge"])

from app.api import control_center
app.include_router(control_center.router, prefix="/api/admin/control-center", tags=["Admin Control Center"])

from app.api import feed
app.include_router(feed.router, prefix="/api/feed", tags=["Feed"])

from app.api import transcribe
app.include_router(transcribe.router, prefix="/api", tags=["Transcribe"])

from app.api import payments
app.include_router(payments.router, tags=["Payments"])

from app.api import debug as _debug_api
app.include_router(_debug_api.router, tags=["Debug"])

# ---------- Request / Response ----------
class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    intent: Optional[str] = "general"

class Source(BaseModel):
    source: str
    page: int

class AnswerResponse(BaseModel):
    answer: str
    confidence: float
    intent: str
    sources: List[Source]
    reasoning: Optional[Any] = None

# ---------- Lazy Load Retriever ----------
from app.dependencies import get_retriever
from app.database import get_session_collection
from datetime import datetime

# ---------- Endpoint ----------
@app.get("/api/health")
async def health_check():
    from starlette.responses import JSONResponse

    # Return 503 while models are still loading so ALB withholds live traffic
    # until this task is genuinely ready to serve requests.
    if not _warmup_complete:
        return JSONResponse(
            status_code=503,
            content={
                "status": "warming_up",
                "timestamp": datetime.now().isoformat(),
                "message": "Model warmup in progress — retry in 30s",
            },
            headers={"Retry-After": "30"},
        )

    health_status = {
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "systems": {
            "api": "ok",
            "database": "unknown",
            "retriever": "unknown"
        }
    }

    # Check Database
    try:
        from app.database import get_db
        db = get_db()
        if db is not None:
            # Simple ping
            db.command('ping')
            health_status["systems"]["database"] = "connected"
    except Exception as e:
        health_status["systems"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check Retriever
    try:
        retriever = get_retriever()
        if retriever is not None:
            health_status["systems"]["retriever"] = "initialized"
    except Exception as e:
        health_status["systems"]["retriever"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    return health_status

async def stream_and_save(generator, session_id, user_query, chunks=None, context="", truth_rules_text="", query_vec=None, is_draft_session: bool = False, marker_map=None):
    """
    Wrapper that streams the LLM response AND runs post-generation
    accuracy layers before saving to DB.

    Post-stream pipeline:
      1. Citation Validator   — cross-checks cited sections against chunks
      2. Answer Verifier      — LLM second-pass for logical consistency
      3. Hallucination Guard  — flags ungrounded numbers
      4. Template Matcher     — surfaces relevant litigation templates
    """
    import logging
    _logger = logging.getLogger("stream_and_save")
    import asyncio
    import json
    full_answer = ""
    unique_sources = []

    # 1. Immediately emit metadata about retrieved sources (Perplexity-style transparency)
    if chunks:
        try:
            unique_sources = []
            seen_src = set()
            import urllib.parse as _urlparse
            for c in chunks:
                _dedup_rel = c.get("rel_path", "") or c.get("metadata", {}).get("rel_path", "") or c.get("source", "")
                src_key = (_dedup_rel, c.get("page", 0))
                if src_key not in seen_src:
                    seen_src.add(src_key)
                    _raw_src = c.get("source", "") or c.get("metadata", {}).get("source", "")
                    _rel_path = c.get("rel_path", "") or c.get("metadata", {}).get("rel_path", "")
                    # Use rel_path for display name — it holds the real filename.
                    _basename = os.path.basename(_rel_path) if _rel_path else os.path.basename(_raw_src)
                    _enc_path = _urlparse.quote(_rel_path.replace("\\", "/"), safe="") if _rel_path else ""
                    _enc_name = _urlparse.quote(_basename, safe="")
                    _url = (
                        f"/api/documents/view_by_path?path={_enc_path}"
                        if _enc_path else
                        f"/api/documents/view?category=all&filename={_enc_name}"
                    )
                    _snippet = (c.get("text") or "").strip()
                    unique_sources.append({
                        "title": _basename or "Document",
                        "page": c.get("page", 1),
                        "url": _url,
                        "rel_path": _rel_path,
                        "score": float(c.get("_rerank_score", 0)),
                        "snippet": _snippet[:800] if _snippet else "",
                    })
                if len(unique_sources) >= 20:  # collect more, then sort + cap
                    break

            # Sort by relevance score — the reranker already encodes legal
            # authority (30% weight) + semantic similarity (50%) + topic (20%).
            # Most relevant doc wins regardless of type; linkifyLegalRefs no
            # longer uses sources[0] as a fallback so AAR-as-first-link is gone.
            unique_sources.sort(key=lambda s: s.get("score", 0), reverse=True)
            unique_sources = unique_sources[:8]

            metadata_payload = {
                "type": "metadata",
                "sources": unique_sources
            }
            yield f"__METADATA__:{json.dumps(metadata_payload)}__END_METADATA__"
        except Exception as me:
            _logger.warning(f"Metadata emission failed: {me}")

    import time
    t_gen_start = time.monotonic()
    try:
        for chunk in generator:
            full_answer += chunk
            yield chunk

        if chunks and full_answer.strip():
            # Use the session-level draft flag passed in — do not re-detect from
            # user_query alone, which breaks on follow-up/correction messages.
            is_draft = is_draft_session or any(kw in user_query.lower() for kw in [
                "draft","notice","reply","appeal","submission","advisory","scn",
                "show cause","drc-01","drc 01","asmt-10","our understanding",
                "gst implications","provide opinion","our comments","tax position",
                "advise on","legal opinion","our client is","we are engaged in",
            ])
            
            if not is_draft:
                # --- Parallel Accuracy Pipeline ---
                async def run_citation_validator():
                    try:
                        from app.generation.citation_validator import CitationValidator
                        return CitationValidator.validate_citations(full_answer, chunks)
                    except Exception as e:
                        _logger.warning(f"Citation validator error: {e}")
                        return full_answer

                async def run_answer_verifier():
                    try:
                        from app.generation.answer_verifier import verify_answer
                        return await asyncio.to_thread(verify_answer, user_query, full_answer, chunks)
                    except Exception as e:
                        _logger.warning(f"Answer verifier error: {e}")
                        return None

                async def run_authority_verifier():
                    """Priority 10: Answer Verification Agent.
                    Checks if the LLM answer cited every mandatory governing authority
                    predicted by the authority taxonomy. Runs in ~1ms (string matching,
                    no LLM call). Logs gaps for monitoring and future regression tracking."""
                    try:
                        from app.dependencies import get_retriever
                        from app.retrieval.query_refiner import verify_answer_authority_coverage
                        _ret = get_retriever()
                        _tax = getattr(_ret, "_last_taxonomy", {})
                        _cov = getattr(_ret, "_last_coverage", {})
                        if _tax.get("confidence", 0) > 0 and (_tax.get("sections") or _tax.get("circulars")):
                            _av = verify_answer_authority_coverage(user_query, full_answer, _tax, _cov)
                            if _av["verdict"] != "pass":
                                _logger.warning(
                                    f"[AUTHORITY_VERIFY] verdict={_av['verdict']} | "
                                    f"topics={_tax.get('topics')} | "
                                    f"cited={_av['cited']} | "
                                    f"missing={_av['missing']} | "
                                    f"note={_av['note']}"
                                )
                        return None
                    except Exception as e:
                        _logger.warning(f"Authority verifier error: {e}")
                        return None

                async def run_hallucination_guard():
                    try:
                        from app.generation.hallucination_guard import check_hallucinated_numbers
                        # Build marker → chunk-text map so the guard can verify each
                        # numeric claim against the SPECIFIC chunk it was cited from,
                        # not just whether the number appears anywhere in the context blob.
                        # e.g. answer says "18% (S3)" but S3's text says "5%" → flagged.
                        _sn_map = {
                            f"S{i+1}": (chunks[i].get("text") or "")
                            for i in range(len(chunks))
                        } if chunks else None
                        return check_hallucinated_numbers(
                            full_answer, context, truth_rules_text, chunks,
                            sn_text_map=_sn_map,
                        )
                    except Exception as e:
                        _logger.warning(f"Hallucination guard error: {e}")
                        return ""

                async def run_template_matcher():
                    try:
                        from app.retrieval.template_matcher import search_templates, format_template_suggestions
                        matched = await asyncio.to_thread(search_templates, user_query, top_k=3)
                        return format_template_suggestions(matched)
                    except Exception as e:
                        _logger.warning(f"Template matcher error: {e}")
                        return ""

                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(
                            run_citation_validator(),
                            run_hallucination_guard(),
                            run_authority_verifier(),
                            run_answer_verifier(),
                        ),
                        timeout=12.0,  # extended: answer_verifier makes an LLM call
                    )
                except asyncio.TimeoutError:
                    _logger.warning("Post-generation validators timed out — skipping")
                    results = (full_answer, "", None, None)

                _, hallu_warn, _, verifier_warn = results

                # Hallucination guard — log only (number issues are low-signal noise)
                if hallu_warn:
                    _logger.warning(f"Hallucination guard: {hallu_warn[:300]}")

                # Answer verifier — stream visible warning to user when a contradiction
                # is detected (e.g., cites Section 17(5) but concludes ITC is available)
                if verifier_warn:
                    _logger.warning(f"Answer verifier flagged: {verifier_warn[:200]}")
                    yield verifier_warn

                # ── Phase 2: emit resolved [Sn] citations as a structured block ──
                # The frontend replaces [S1] inline markers with real document links
                # using this map — no guessing, no regex scoring.
                if marker_map:
                    try:
                        from app.generation.context_builder import parse_markers
                        citation_result = parse_markers(full_answer, marker_map)
                        if citation_result["citations"] or citation_result["unresolved"]:
                            citations_payload = {
                                "type": "citations",
                                "citations": citation_result["citations"],
                                "unresolved": citation_result["unresolved"],
                            }
                            yield f"__CITATIONS__:{json.dumps(citations_payload)}__END_CITATIONS__"
                    except Exception as _ce:
                        _logger.debug(f"Citation parser error (non-fatal): {_ce}")

                # ── Safety guards: compute confidence and append caveat if needed ──
                try:
                    from app.generation.confidence import estimate_confidence
                    from app.generation.safety import apply_safety_guards
                    _confidence = estimate_confidence(context, chunks or [])
                    _logger.debug(f"Confidence (context-based): {_confidence:.3f}")
                    _safe_answer = apply_safety_guards(full_answer, _confidence, "")
                    # If safety guard appended a caveat, stream it now
                    if _safe_answer != full_answer:
                        caveat = _safe_answer[len(full_answer):]
                        yield caveat
                except Exception as _sg_exc:
                    _logger.debug(f"Safety guard error (non-fatal): {_sg_exc}")

                # template_block intentionally not streamed — surfaced via /api/templates instead

    except Exception as e:
        _logger.error(f"Error in stream_and_save: {e}", exc_info=True)
        yield "\n[System: An error occurred processing your request. Please try again.]"
    finally:
        # DB save — wrapped in to_thread so the sync pymongo write doesn't
        # block the event loop while the HTTP response is still open.
        if session_id and full_answer.strip():
            collection = get_session_collection()
            if collection is not None:
                try:
                    from datetime import timezone as _tz
                    _now = datetime.now(_tz.utc)
                    await asyncio.to_thread(
                        collection.update_one,
                        {"session_id": session_id},
                        {
                            "$push": {"messages": {
                                "message_id": str(uuid.uuid4()),
                                "role": "assistant",
                                "content": full_answer,
                                "sources": unique_sources,
                                "timestamp": _now,
                            }},
                            "$set": {"updated_at": _now},
                            "$inc": {"message_count": 1},
                        },
                    )
                except Exception as dbe:
                    _logger.warning(f"DB save error (non-fatal): {dbe}")

        # Confidence-gated cache store — also off the event loop
        if full_answer.strip() and query_vec is not None:
            try:
                from app.cache import cache_store
                from app.generation.confidence import estimate_confidence
                # Pass the RETRIEVED CONTEXT string (not the generated answer) so
                # confidence reflects evidence volume, not answer verbosity.
                confidence = await asyncio.to_thread(estimate_confidence, context, chunks or [])
                await asyncio.to_thread(cache_store, user_query, query_vec, full_answer, confidence, unique_sources if chunks else [])
                _logger.debug(f"Cache store attempt | confidence={confidence:.3f}")
            except Exception as ce:
                _logger.warning(f"Cache store error (non-fatal): {ce}")

        # Commit AI log analytics
        try:
            from app.ai_logger import update_ai_log, commit_ai_log
            update_ai_log(
                generation_time_ms=round((time.monotonic() - t_gen_start) * 1000, 2),
                estimated_completion_tokens=len(full_answer) // 4,
                response_length=len(full_answer),
                citations_count=len(unique_sources)
            )
            commit_ai_log(success=bool(full_answer.strip()))
        except Exception as cle:
            _logger.warning(f"AI logger commit error (non-fatal): {cle}")

_ask_logger = logging.getLogger("leta.ask")

@app.post("/ask")
@limiter.limit("30/minute")
async def ask_question(request: Request, req: QuestionRequest):
    question = req.question.strip()
    session_id = req.session_id
    query_id = getattr(request.state, "query_id", str(uuid.uuid4())[:8])
    t0 = time.monotonic()

    user_id, username = _get_user_info_from_req(request)
    from app.ai_logger import init_ai_log
    init_ai_log(
        user_id=user_id,
        username=username,
        query=question,
        endpoint="/api/ask",
        session_id=session_id,
        request_id=query_id,
        client_ip=request.client.host if request.client else None
    )

    # IMMEDIATE SAVE: Save User Question First
    if session_id and _warmup_complete:
        collection = get_session_collection()
        if collection is not None:
            from datetime import timezone as _tz
            collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": {
                        "message_id": str(uuid.uuid4()),
                        "role": "user",
                        "content": question,
                        "timestamp": datetime.now(_tz.utc),
                    }},
                    "$inc": {"message_count": 1},
                }
            )

    async def rag_pipeline_orchestrator():
        import asyncio as _asyncio
        # ── Warmup wait (ECS rolling-deployment grace period) ────────────────────
        # During a rolling deploy the new task registers in the ALB target group
        # before finishing model/index load (60-90s).  Instead of 503-ing immediately
        # and exhausting the frontend's retry budget, we hold the streaming connection
        # open with a STATUS keepalive and release it as soon as warmup completes.
        if not _warmup_complete:
            yield f"__STATUS__:{json.dumps({'msg': 'LETA is starting up — please wait…'})}__END_STATUS__"
            _wt = 0
            while not _warmup_complete and _wt < 90:
                await _asyncio.sleep(3)
                _wt += 3
            if not _warmup_complete:
                yield "\n\n⚠ **LETA is taking longer than expected to start.** Please refresh the page and try your question again in a moment."
                return
        from app.routing.router import route_query
        from app.generation.synthesizer import _estimate_complexity
        from app.generation.calculation_engine import detect_and_calculate, format_for_context
        from app.generation.context_compressor import compress_context
        from app.cache import cache_lookup
        from app.retrieval.retriever import embed_query
        from app.retrieval.retrieval_trace import RetrievalTrace, store_trace

        # ── RetrievalTrace — created once per query, threaded through entire pipeline ──
        _trace = RetrievalTrace(query_id=query_id, query=question)

        # ── Stage 1: Intent classification (LLM-first via classify_intent, 5s cap) ──
        # route_query() calls classify_intent() which makes a real blocking Haiku
        # round-trip (capped at 5s; keyword fallback on any error).  Offload it to a
        # thread so the blocking call doesn't stall the event loop under concurrency.
        route = await _asyncio.to_thread(route_query, question)
        domain_paths = route.get("domain_paths", [])
        _complexity = _estimate_complexity(question)
        _q = question.lower()

        _DRAFT_KW = [
            "draft","notice","reply","appeal","submission","advisory","scn","show cause",
            "drc-01","drc 01","asmt-10","asmt 10","drc-07","drc 07","drc-03","drc 03",
            "write a letter","write letter","prepare reply","representation",
            "response to notice","respond to","our understanding","gst implications",
            "gst implication","provide opinion","provide advisory","our comments",
            "tax position","gst treatment of","advise on","legal opinion",
            "our client is","we are engaged in","facts of the case",
        ]
        # Definition/explanation queries must NEVER route to DRAFTING_PROMPT regardless
        # of session history. A plain knowledge query ("define X", "what is X",
        # "provide definition of X") has no missing facts and should never trigger
        # the check-3 clarification flow.
        _NEVER_DRAFT_PATTERNS = [
            r'\b(what\s+is|what\s+are|define|definition\s+of|explain|meaning\s+of)\b',
            r'\b(provide|give|state|share)\s+(the\s+)?(definition|meaning|explanation|rate|provision)',
            r'\b(relevant\s+circular|applicable\s+circular|circular\s+on)\b',
            r'\b(full\s+form|abbreviation|what\s+does\s+.+stand\s+for)\b',
            # Correction / continuation signals — never reroute to advisory/drafting mode
            r'you\s+got\s+me\s+(all\s+)?wrong',
            r'(that\'s|that\s+is)\s+(wrong|incorrect|not\s+right|off\s+route|off\s+track)',
            r'completely\s+(switched|diverted|changed)\s+to',
            r'stick\s+to\s+(our|the|this)\s+conversation',
            r'take\s+it\s+forward|taking\s+(it|this)\s+forward',
            r'continue\s+(the|our|this)\s+(discussion|conversation|analysis|thread|topic)',
            r'\bi\s+(already|have\s+already)\s+(said|told|replied|mentioned)',
            r'\bi\s+replied\s+to\s+you',
            r'as\s+(i|we)\s+(said|mentioned|discussed|told|replied)',
            r'not\s+what\s+(i|we)\s+(asked|said|meant)',
        ]
        import re as _re
        _is_never_draft = any(_re.search(p, _q) for p in _NEVER_DRAFT_PATTERNS)

        _is_draft_early = (not _is_never_draft) and any(k in _q for k in _DRAFT_KW)

        if "rule 42" in _q or "rule42" in _q:
            _init_msg = "Computing Rule 42 ITC Reversal..."
        elif "rule 43" in _q or "rule43" in _q:
            _init_msg = "Computing Rule 43 Capital Goods Reversal..."
        elif any(k in _q for k in ["itc", "input tax credit", "section 16", "section 17"]):
            _init_msg = "Analyzing ITC Eligibility Provisions..."
        elif _is_draft_early:
            _init_msg = "Initializing Advisory & Drafting Engine..."
        elif any(k in _q for k in ["refund", "export", "lut"]):
            _init_msg = "Checking Refund & Export Provisions..."
        elif any(k in _q for k in ["interest", "section 50", "penalty"]):
            _init_msg = "Computing Interest & Penalty Exposure..."
        else:
            _init_msg = "Initializing Statutory Analyzer..."

        yield f"__STATUS__:{json.dumps({'msg': _init_msg})}__END_STATUS__"

        # ── Stage 2: PARALLEL — session history + query embedding ─────────────────
        # Both are independent I/O-bound tasks; run them simultaneously.
        _HISTORY_DRAFT_KW = [
            "advisory","our understanding","gst implications","gst implication",
            "provide opinion","our comments","tax position","gst treatment",
            "advise on","legal opinion","our client","we are engaged",
            "facts of the case","draft","notice","reply","appeal","scn","show cause",
            "drc-01","drc-07","asmt-10","representation",
            "our comments from gst perspective","i've reviewed your",
            "issue raised","section invoked","to draft a strong reply",
        ]

        # Phrases that indicate the user is referencing a previous session
        _CROSS_SESSION_KW = [
            "remember", "that chat", "previous session", "last time", "we discussed",
            "earlier session", "you mentioned", "from before", "that consultation",
            "we talked about", "as discussed", "recall when", "in our previous",
            "that case we", "previous chat", "last session",
        ]
        _is_cross_session_ref = any(k in question.lower() for k in _CROSS_SESSION_KW)

        def _fetch_cross_session_context():
            """Search the user's other sessions for relevant content when they reference a past chat."""
            if not _is_cross_session_ref:
                return ""
            _coll = get_session_collection()
            if _coll is None:
                return ""
            # Get the user_id from the current session
            _sess_doc = _coll.find_one({"session_id": session_id}, {"user_id": 1}) if session_id else None
            if not _sess_doc:
                return ""
            _user_id = _sess_doc.get("user_id", "")
            if not _user_id:
                return ""
            # Build search terms: strip cross-session keywords and use remaining words
            _search_q = question.lower()
            for kw in _CROSS_SESSION_KW:
                _search_q = _search_q.replace(kw, " ")
            _search_terms = [w for w in _search_q.split() if len(w) > 3][:6]
            if not _search_terms:
                return ""
            _regex = "|".join(_search_terms)
            try:
                _matches = list(_coll.find(
                    {"user_id": _user_id, "session_id": {"$ne": session_id},
                     "messages.content": {"$regex": _regex, "$options": "i"}},
                    {"_id": 0, "session_id": 1, "title": 1, "messages": 1, "updated_at": 1}
                ).sort("updated_at", -1).limit(3))
            except Exception:
                return ""
            if not _matches:
                return ""
            _ctx_parts = []
            for _m in _matches:
                # Find the most relevant message pair (user question + LETA answer)
                _msgs = _m.get("messages", [])
                _best_pair = ""
                for _i, _msg in enumerate(_msgs):
                    _content = _msg.get("content", "")
                    if any(t in _content.lower() for t in _search_terms):
                        # Include user question + LETA response pair
                        _u_msg = _msgs[_i - 1]["content"][:300] if _i > 0 and _msgs[_i-1]["role"] == "user" else ""
                        _a_msg = _content[:500]
                        if _u_msg:
                            _best_pair = f"USER: {_u_msg}\nLETA: {_a_msg}"
                        else:
                            _best_pair = f"LETA: {_a_msg}"
                        break
                if _best_pair:
                    _title = _m.get("title", "Previous Session")
                    _date = _m.get("updated_at", "")
                    _date_str = _date.strftime("%b %d, %Y") if hasattr(_date, "strftime") else str(_date)[:10]
                    _ctx_parts.append(f'[MEMORY — "{_title}" ({_date_str})]:\n{_best_pair}')
            return "\n\n".join(_ctx_parts)

        def _fetch_history_sync():
            if not session_id:
                return "", False
            _coll = get_session_collection()
            if _coll is None:
                return "", False
            _sess = _coll.find_one({"session_id": session_id})
            if not _sess or "messages" not in _sess:
                return "", False
            # IMPORTANT: include the current user message (already saved by the
            # immediate save above) in the history window. Previously [:-1] excluded
            # it, so CHECK 1 in the drafting prompt could not see the user's reply
            # to LETA's questions and would ask again. Using [-7:] shows the model
            # the full sequence: LETA-questions → USER-answers → produce draft.
            _recent = _sess["messages"][-7:]
            _hist = "".join(f"{m['role'].upper()}: {m['content']}\n" for m in _recent)
            # Draft detection: check only the 2 most recent messages so a single
            # old advisory turn doesn't permanently lock the whole session into
            # drafting mode for every follow-up question.
            _last_2_text = " ".join(
                m.get("content", "") for m in _sess["messages"][-2:]
            ).lower()
            _is_d = any(k in _last_2_text for k in _HISTORY_DRAFT_KW)
            return _hist, _is_d

        yield f"__STATUS__:{json.dumps({'msg': 'Scanning Semantic Cache...'})}__END_STATUS__"

        (history_context, _session_is_draft), query_vec, cross_session_context = await _asyncio.gather(
            _asyncio.to_thread(_fetch_history_sync),
            _asyncio.to_thread(embed_query, question),
            _asyncio.to_thread(_fetch_cross_session_context),
        )
        _is_draft = _is_draft_early or _session_is_draft

        # ── Stage 3: Cache lookup ─────────────────────────────────────────────────
        cached_answer = await _asyncio.to_thread(cache_lookup, question, query_vec)
        if cached_answer:
            cached_text, cached_sources = cached_answer
            _ask_logger.info("Cache HIT", extra={"query_id": query_id, "cache_hit": True})
            # Log minimal trace for cache hits so query_id is still searchable
            try:
                _trace.record_preprocessing(
                    original_query=question, refined_query=question,
                    domain_route=domain_paths, complexity_score=_complexity,
                    response_mode="cache_hit",
                )
                _trace.answer = {"cache_hit": True, "query_id": query_id}
                store_trace(_trace)
            except Exception:
                pass
            yield f"__STATUS__:{json.dumps({'msg': 'Cache Hit — Instant Retrieval Complete.'})}__END_STATUS__"
            if cached_sources:
                yield f"__METADATA__:{json.dumps({'type': 'metadata', 'sources': cached_sources})}__END_METADATA__"
            yield cached_text
            try:
                from app.ai_logger import update_ai_log, commit_ai_log
                update_ai_log(
                    model_used="cache",
                    cache_hit=True,
                    response_length=len(cached_text),
                    citations_count=len(cached_sources or [])
                )
                commit_ai_log(success=True)
            except Exception:
                pass
            return

        # ── Stage 4: Pre-computed calculations (sync, instant) ────────────────────
        calc_result = detect_and_calculate(question)
        calc_block = format_for_context(calc_result) if calc_result else ""
        if calc_result:
            yield f"__STATUS__:{json.dumps({'msg': 'Pre-computing Statutory Formula...'})}__END_STATUS__"

        # ── Stage 5: Retrieval — strategy depends on query type ───────────────────
        # Follow-up query enrichment: if query is short (<8 words) and history
        # exists, enrich the retrieval query with context from the last exchange
        # so "what about penalties?" searches with full legal context.
        retriever = get_retriever()
        _retrieval_top_k = 30 if _is_draft else (25 if _complexity >= 0.60 else 20)
        domain_label = ", ".join(domain_paths[:2]) if domain_paths else "All Databases"

        def _enrich_for_retrieval(q: str, hist: str) -> str:
            if hist and len(q.split()) < 8:
                _last_lines = [l for l in hist.split('\n') if l.startswith('ASSISTANT:')]
                if _last_lines:
                    _ctx = _last_lines[-1].replace('ASSISTANT:', '').strip()[:100]
                    return f"{q} [context: {_ctx}]"
            return q

        _retrieval_q = _enrich_for_retrieval(question, history_context)

        yield f"__STATUS__:{json.dumps({'msg': f'Searching Statutory Database ({domain_label})...'})}__END_STATUS__"

        if _is_draft:
            # Draft: rule-based sub-queries, no LLM expansion call needed
            _statute_q  = _retrieval_q + " section rule act provisions conditions eligibility liability"
            _caselaw_q  = _retrieval_q + " high court supreme court judgment held ruling decision AAR"
            _circular_q = _retrieval_q + " CBIC circular notification clarification instruction"
            _adv = {
                "queries": [_retrieval_q, _statute_q, _caselaw_q, _circular_q],
                "hyde_document": "", "topic": "General", "subtopic": None,
            }
            # Record preprocessing before handing off to retriever
            _trace.record_preprocessing(
                original_query=question, refined_query=_retrieval_q,
                sub_queries=[_statute_q, _caselaw_q, _circular_q],
                topic="General", domain_route=domain_paths,
                complexity_score=_complexity, response_mode="draft",
            )
            chunks = await _asyncio.to_thread(
                retriever.search, _retrieval_q, _retrieval_top_k,
                route["use_sources"], _adv, domain_paths, True,
                False, _trace,   # skip_rerank=False, trace=_trace
            )

        else:
            # All non-draft queries: run query expansion + fast retrieval IN PARALLEL.
            # Expansion uses 4 angle-specific sub-queries (statutory/circular/notification/factual)
            # + a corpus-authentic HyDE document. Parallel execution means the LLM expansion
            # adds zero latency beyond what retrieval already takes.
            yield f"__STATUS__:{json.dumps({'msg': 'Expanding Query for Precision Retrieval...'})}__END_STATUS__"

            def _fast_retrieve():
                # Trace is NOT passed here — fast retrieve is skip_rerank=True
                # and supplement_and_rerank runs the full reranking pass with trace.
                return retriever.search(
                    _retrieval_q, _retrieval_top_k, route["use_sources"],
                    None, domain_paths, False, skip_rerank=True,
                )

            def _expand():
                from app.retrieval.query_refiner import generate_advanced_queries
                return generate_advanced_queries(_retrieval_q)

            try:
                fast_chunks, advanced_queries = await _asyncio.gather(
                    _asyncio.to_thread(_fast_retrieve),
                    _asyncio.to_thread(_expand),
                )

                # Record preprocessing now that we have expanded queries
                _adv_qs = advanced_queries or {}
                _trace.record_preprocessing(
                    original_query=question,
                    refined_query=_retrieval_q,
                    sub_queries=_adv_qs.get("queries", []),
                    hyde_doc=_adv_qs.get("hyde_document", ""),
                    topic=_adv_qs.get("topic", "General"),
                    subtopic=_adv_qs.get("subtopic"),
                    domain_route=domain_paths,
                    complexity_score=_complexity,
                    response_mode=(
                        "detailed" if _complexity >= 0.60
                        else "standard" if _complexity >= 0.25
                        else "brief"
                    ),
                )

                # Supplement the fast pool with expanded-query FAISS results,
                # then do ONE FlashRank + LegalReranker pass on the merged pool.
                chunks = await _asyncio.to_thread(
                    retriever.supplement_and_rerank,
                    fast_chunks, advanced_queries, _retrieval_q, _retrieval_top_k,
                    _trace,   # trace
                )
            except Exception as _retrieval_exc:
                import traceback as _tb
                logger.error(
                    "[CRASH] rag_pipeline_orchestrator retrieval stage failed | "
                    f"query_id={query_id} | {_retrieval_exc!r}\n{_tb.format_exc()}"
                )
                yield f"__STATUS__:{json.dumps({'msg': 'Retrieval engine error. Please try again.'})}__END_STATUS__"
                yield "\n\n⚠ **LETA encountered a retrieval error.** The statutory database search failed for this query. Please try again — if the problem persists, try rephrasing your question."
                return

        # ── Stage 6: Context assembly (pure Python, no blocking I/O) ─────────────
        try:
            citation_block   = build_context(chunks, is_draft=_is_draft)
            compressed_block = compress_context(chunks, question, is_draft=_is_draft)

            # Build the [S1]→chunk mapping for server-side citation resolution (Phase 2)
            from app.generation.context_builder import build_marker_map
            _marker_map = build_marker_map(chunks) if chunks else []
        except Exception as _ctx_exc:
            import traceback as _tb
            logger.error(
                f"[CRASH] Stage 6 context assembly failed | query_id={query_id} | "
                f"{_ctx_exc!r}\n{_tb.format_exc()}"
            )
            yield (
                f"\n\n⚠ **LETA encountered a context assembly error.** "
                f"(`{type(_ctx_exc).__name__}: {str(_ctx_exc)[:120]}`)\n\n"
                "This is unexpected — please retry. If it persists, contact support."
            )
            return

        # Detect if this is a follow-up / correction so the model gets a strong
        # continuation signal and doesn't restart from first principles.
        _FOLLOWUP_KW = [
            "you got me wrong", "you are wrong", "that's wrong", "that is wrong",
            "off route", "off track", "completely switched", "completely diverted",
            "stick to our conversation", "stick to the conversation",
            "take it forward", "taking it forward", "continue the discussion",
            "as i said", "as i mentioned", "i already said", "i already told",
            "i replied", "i have said", "i told you", "you mentioned",
            "building on", "following up", "based on what you said",
            "not what i asked", "not what i meant", "you missed",
        ]
        _is_followup = bool(history_context) and (
            len(question.split()) < 25
            or any(k in question.lower() for k in _FOLLOWUP_KW)
        )
        _history_label = (
            "⚠ ACTIVE CONVERSATION — CONTINUE FROM HERE. Do NOT restart with basics already covered. "
            "Directly continue the specific legal discussion in progress.\n"
            if _is_followup else "CHAT HISTORY"
        )

        full_rag_context = (
            (f"--- MEMORY FROM PREVIOUS SESSIONS ---\n{cross_session_context}\n--- END MEMORY ---\n\n" if cross_session_context else "")
            + (f"--- {_history_label} ---\n{history_context}\n--- END HISTORY ---\n\n" if history_context else "")
            + citation_block
            + (f"\n\n{calc_block}" if calc_block else "")
            + "\n\n--- COMPRESSED STATUTORY EXCERPTS (for quick reference) ---\n\n"
            + compressed_block
        )

        try:
            from app.generation.rules_engine import rules_engine
            truth_rules_text = rules_engine.get_all_rules_as_text()
        except Exception as _re_exc:
            logger.warning(f"Rules engine failed (using empty truth rules): {_re_exc}")
            truth_rules_text = ""

        # ── Stage 7: Streaming LLM synthesis ──────────────────────────────────────
        if _is_draft:
            _synth_msg = "Synthesizing Advisory & Drafting..."
        elif _complexity >= 0.60:
            _synth_msg = "Synthesizing Legal Position & Precedents..."
        else:
            _synth_msg = "Synthesizing Sovereign Legal Position..."

        yield f"__STATUS__:{json.dumps({'msg': _synth_msg})}__END_STATUS__"

        from app.generation.synthesizer import synthesize_answer_stream
        response_stream = synthesize_answer_stream(
            question, full_rag_context, session_is_draft=_is_draft
        )

        # ── Log and store the retrieval trace ────────────────────────────────
        # This fires before streaming starts — captures everything up to synthesis.
        # Answer metadata (latency, model) is captured later in stream_and_save.
        try:
            _trace.answer = {
                "query_id":   query_id,
                "cache_hit":  False,
                "complexity": round(_complexity, 3),
                "mode":       ("draft" if _is_draft else
                               "detailed" if _complexity >= 0.60 else
                               "standard" if _complexity >= 0.25 else "brief"),
            }
            store_trace(_trace)
            # Single structured JSON log line — filterable in CloudWatch Logs Insights:
            #   filter trace_type = "retrieval_trace"
            #   filter query_id = "LETA-20260810-..."
            import logging as _log_mod
            _tlog = _log_mod.getLogger("leta.trace")
            _tlog.info(
                "retrieval_trace",
                extra=_trace.to_log_dict(),
            )
        except Exception as _te:
            logger.debug(f"Trace logging failed (non-fatal): {_te}")

        _synthesis_yielded_text = False
        try:
            async for chunk in stream_and_save(
                response_stream, session_id, question,
                chunks=chunks, context=citation_block, truth_rules_text=truth_rules_text,
                query_vec=query_vec, is_draft_session=_is_draft,
                marker_map=_marker_map,
            ):
                yield chunk
                # Track whether any non-control text was produced.
                # Control tokens (__STATUS__:, __METADATA__:, __CITATIONS__:) are
                # not "real" answer text; we check for at least one plain text chunk.
                if chunk and not chunk.startswith("__") and not chunk.startswith("\n\n⚠"):
                    _synthesis_yielded_text = True
        except Exception as _synth_exc:
            import traceback as _tb
            logger.error(
                "[CRASH] rag_pipeline_orchestrator synthesis stage failed | "
                f"query_id={query_id} | {_synth_exc!r}\n{_tb.format_exc()}"
            )
            yield "\n\n⚠ **LETA encountered an error while generating the response.** The statutory sources were retrieved successfully but the synthesis step failed. Please try asking again — your question is valid and the answer exists in our database."
            _synthesis_yielded_text = True  # don't double-emit

        # Safety net: if the entire synthesis pipeline completed without yielding
        # any answer text, emit a visible diagnostic instead of a silent blank response.
        if not _synthesis_yielded_text:
            logger.error(
                f"[EMPTY_SYNTHESIS] Model stream produced zero text content | "
                f"query_id={query_id} | complexity={_complexity:.2f} | draft={_is_draft}"
            )
            yield (
                "\n\n⚠ **LETA's language model returned an empty response.**\n\n"
                "This is an infrastructure issue — not your query. Possible causes: "
                "model rate-limit, API timeout, or extended-thinking budget exhausted. "
                "**Please retry in a few seconds.** If this happens repeatedly, "
                "contact support with query ID `" + query_id + "`."
            )

    async def log_wrapper(generator):
        success = False
        error_msg = None
        status_code = 200
        try:
            async for chunk in generator:
                yield chunk
            success = True
        except Exception as e:
            import traceback as _tb
            success = False
            error_msg = str(e)
            status_code = 500
            # Log the full crash with traceback so CloudWatch shows the real cause.
            logger.error(
                f"[CRASH] rag_pipeline unhandled exception | {e!r}\n{_tb.format_exc()}"
            )
            # Yield a visible error message so the user sees something instead of blank.
            # The raw `raise e` here caused StreamingResponse to abort silently — the
            # frontend received only status tokens and displayed "unable to generate".
            yield (
                f"\n\n⚠ **LETA encountered an unexpected error.**\n\n"
                f"**Debug info (for support):** `{type(e).__name__}: {str(e)[:200]}`\n\n"
                "Please screenshot this message and retry. If the issue persists, "
                "try rephrasing your question."
            )
        finally:
            try:
                from app.ai_logger import commit_ai_log
                commit_ai_log(success=success, http_status=status_code, error_message=error_msg)
            except Exception:
                pass

    from fastapi.responses import StreamingResponse
    return StreamingResponse(log_wrapper(rag_pipeline_orchestrator()), media_type="text/event-stream")


def log_analytics_sync(endpoint_name: str):
    def decorator(func):
        import functools
        @functools.wraps(func)
        async def wrapper(request: Request, req: QuestionRequest, *args, **kwargs):
            question = req.question.strip()
            session_id = req.session_id
            
            user_id, username = _get_user_info_from_req(request)
            request_id = getattr(request.state, "query_id", str(uuid.uuid4())[:8])
            
            from app.ai_logger import init_ai_log, commit_ai_log
            init_ai_log(
                user_id=user_id,
                username=username,
                query=question,
                endpoint=endpoint_name,
                session_id=session_id,
                request_id=request_id,
                client_ip=request.client.host if request.client else None
            )
            
            success = False
            error_msg = None
            status_code = 200
            try:
                res = await func(request, req, *args, **kwargs)
                success = True
                return res
            except Exception as e:
                success = False
                error_msg = str(e)
                status_code = 500
                raise e
            finally:
                try:
                    commit_ai_log(success=success, http_status=status_code, error_message=error_msg)
                except Exception:
                    pass
        return wrapper
    return decorator


@app.post("/ask-sync")
@limiter.limit("20/minute")
@log_analytics_sync("/api/ask-sync")
async def ask_question_sync(request: Request, req: QuestionRequest):
    """Non-streaming version of /ask — returns complete JSON response.
    Required for AWS API Gateway HTTP_PROXY compatibility (no SSE streaming support)."""
    # Wait up to 50s for warmup (well under the ALB 60s idle timeout) so callers
    # don't see 503 during ECS rolling-deployment warm-up windows.
    if not _warmup_complete:
        import asyncio as _asyncio_w
        _wt = 0
        while not _warmup_complete and _wt < 50:
            await _asyncio_w.sleep(2)
            _wt += 2
        if not _warmup_complete:
            from starlette.responses import JSONResponse as _jr
            return _jr(status_code=503, content={"detail": "Service warming up — retry in 30s"}, headers={"Retry-After": "30"})

    import asyncio as _asyncio
    import urllib.parse as _urlparse
    from fastapi.responses import JSONResponse as _JSONResponse
    from app.routing.router import route_query as _route_query
    from app.generation.synthesizer import _estimate_complexity, synthesize_answer_stream as _synth_stream
    from app.generation.calculation_engine import detect_and_calculate, format_for_context
    from app.generation.context_compressor import compress_context
    from app.cache import cache_lookup
    from app.retrieval.retriever import embed_query

    question = req.question.strip()
    session_id = req.session_id

    if session_id:
        collection = get_session_collection()
        if collection is not None:
            from datetime import timezone as _tz
            collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": {
                        "message_id": str(uuid.uuid4()),
                        "role": "user",
                        "content": question,
                        "timestamp": datetime.now(_tz.utc),
                    }},
                    "$inc": {"message_count": 1},
                }
            )

    # Offload to thread: _route_query calls classify_intent() which makes a
    # blocking Haiku network call (5s cap).  Must not run on the event loop.
    route = await _asyncio.to_thread(_route_query, question)
    domain_paths = route.get("domain_paths", [])
    _q = question.lower()
    _complexity = _estimate_complexity(question)

    history_context = ""
    _session_is_draft = False
    if session_id:
        collection = get_session_collection()
        if collection is not None:
            _sess = collection.find_one({"session_id": session_id})
            if _sess and "messages" in _sess:
                recent = _sess["messages"][:-1][-6:]
                for msg in recent:
                    history_context += f"{msg['role'].upper()}: {msg['content']}\n"
                _DRAFT_HIST_KW = [
                    "advisory", "our understanding", "gst implications", "provide opinion",
                    "our comments", "tax position", "gst treatment", "advise on", "legal opinion",
                    "draft", "notice", "reply", "appeal", "scn", "show cause", "drc-01",
                ]
                _session_is_draft = any(k in history_context.lower() for k in _DRAFT_HIST_KW)

    query_vec = embed_query(question)
    cached_answer = cache_lookup(question, query_vec)
    if cached_answer:
        cached_text, cached_sources = cached_answer
        update_ai_log(
            model_used="cache",
            cache_hit=True,
            response_length=len(cached_text),
            citations_count=len(cached_sources or [])
        )
        commit_ai_log(success=True)
        return _JSONResponse({"answer": cached_text, "sources": cached_sources or []})

    calc_result = detect_and_calculate(question)
    calc_block = format_for_context(calc_result) if calc_result else ""

    _DRAFT_KW = [
        "draft", "notice", "reply", "appeal", "submission", "advisory", "scn", "show cause",
        "drc-01", "drc 01", "asmt-10", "our understanding", "gst implications",
        "provide opinion", "our comments", "tax position", "advise on",
    ]
    _is_draft = _session_is_draft or any(k in _q for k in _DRAFT_KW)

    # Sync mode: use rule-based 4-angle multi-query (avoids extra LLM latency on the sync path).
    # Covers statutory, circular, notification, and factual angles — same structure as the
    # LLM expansion but keyword-driven so it completes in microseconds.
    refined_q = question
    if _is_draft:
        advanced_queries = {
            "queries": [
                refined_q,
                refined_q + " section rule act provisions conditions eligibility liability",
                refined_q + " high court supreme court judgment held ruling decision AAR",
                refined_q + " CBIC circular notification clarification instruction",
            ],
            "hyde_document": "", "topic": "General", "subtopic": None,
        }
    else:
        advanced_queries = {
            "queries": [
                refined_q,
                refined_q + " section CGST Act rule proviso conditions eligibility",
                refined_q + " CBIC Circular clarification instruction",
                refined_q + " GST Notification Central Tax Rate exemption 2017 2018 2019 2020 2021 2022 2023 2024 2025",
            ],
            "hyde_document": "", "topic": "General", "subtopic": None,
        }

    retriever = get_retriever()
    # CrossEncoder reranking enabled: ms-marco-MiniLM-L-6-v2 runs in ~200-400ms
    # for 50 candidate pairs on CPU — well within the 29s ALB timeout.
    # The old NLI DeBERTa model was both slow AND broken (returned 3-class arrays).
    _top_k = 20 if _is_draft else (18 if _complexity >= 0.60 else 15)
    chunks = retriever.search(
        query=refined_q,
        top_k=_top_k,
        allowed_sources=route["use_sources"],
        advanced_queries=advanced_queries,
        domain_paths=domain_paths,
        is_draft=_is_draft,
        skip_rerank=False,
    )

    citation_block = build_context(chunks, is_draft=_is_draft)
    compressed_block = compress_context(chunks, question, is_draft=_is_draft)

    # Build the (S1)→chunk mapping for server-side citation resolution (Phase 2)
    from app.generation.context_builder import build_marker_map, parse_markers as _parse_markers
    _marker_map_sync = build_marker_map(chunks) if chunks else []

    full_rag_context = (
        (f"--- CHAT HISTORY ---\n{history_context}\n--- END HISTORY ---\n\n" if history_context else "")
        + citation_block
        + (f"\n\n{calc_block}" if calc_block else "")
        + "\n\n--- COMPRESSED STATUTORY EXCERPTS (for quick reference) ---\n\n"
        + compressed_block
    )

    # Draft/advisory queries: Haiku + 4000 tokens (~23-27s) — fits API Gateway's 29s limit.
    # Non-draft Q&A: Sonnet (6000-12000 tokens — Quick Take + Key Extracts + Detailed Advisory).
    answer = await _asyncio.to_thread(
        lambda: "".join(_synth_stream(question, full_rag_context, session_is_draft=_is_draft, force_haiku=_is_draft))
    )
    t_gen_end = time.monotonic()

    # Resolve (S1), (S2), … markers in the generated answer → structured citation list
    _citation_result_sync = _parse_markers(answer, _marker_map_sync)

    unique_sources: list = []
    seen_src: set = set()
    for c in chunks:
        _dedup_rel = c.get("rel_path", "") or c.get("metadata", {}).get("rel_path", "") or c.get("source", "")
        src_key = (_dedup_rel, c.get("page", 0))
        if src_key not in seen_src:
            seen_src.add(src_key)
            _raw_src = c.get("source", "") or c.get("metadata", {}).get("source", "")
            _rel_path = c.get("rel_path", "") or c.get("metadata", {}).get("rel_path", "")
            _basename = os.path.basename(_rel_path) if _rel_path else os.path.basename(_raw_src)
            _enc_path = _urlparse.quote(_rel_path.replace("\\", "/"), safe="") if _rel_path else ""
            _enc_name = _urlparse.quote(_basename, safe="")
            _url = (
                f"/api/documents/view_by_path?path={_enc_path}"
                if _enc_path else
                f"/api/documents/view?category=all&filename={_enc_name}"
            )
            _snippet = (c.get("text") or "").strip()
            unique_sources.append({
                "title": _basename or "Document",
                "page": c.get("page", 1),
                "url": _url,
                "rel_path": _rel_path,
                "score": float(c.get("_rerank_score", 0)),
                "snippet": _snippet[:800] if _snippet else "",
            })
        if len(unique_sources) >= 8:
            break

    if session_id and answer.strip():
        collection = get_session_collection()
        if collection is not None:
            from datetime import timezone as _tz
            _now = datetime.now(_tz.utc)
            collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": {
                        "message_id": str(uuid.uuid4()),
                        "role": "assistant",
                        "content": answer,
                        "timestamp": _now,
                    }},
                    "$set": {"updated_at": _now},
                    "$inc": {"message_count": 1},
                }
            )

    # Commit AI log analytics
    try:
        from app.ai_logger import update_ai_log, commit_ai_log
        update_ai_log(
            generation_time_ms=round((t_gen_end - t_gen_start) * 1000, 2),
            estimated_completion_tokens=len(answer) // 4,
            response_length=len(answer),
            citations_count=len(unique_sources)
        )
        commit_ai_log(success=bool(answer.strip()))
    except Exception as cle:
        logger.warning(f"AI logger commit error (non-fatal): {cle}")

    return _JSONResponse({
        "answer":              answer,
        "sources":             unique_sources,
        "citations":           _citation_result_sync["citations"],
        "unresolved_citations": _citation_result_sync["unresolved"],
    })


async def _execute_ask_question_with_file(
    request: Request,
    file: UploadFile,
    question_text: str,
    session_id: Optional[str]
):
    # Same 50s warmup wait as /ask-sync (under ALB 60s idle timeout).
    if not _warmup_complete:
        import asyncio as _asyncio_w
        _wt = 0
        while not _warmup_complete and _wt < 50:
            await _asyncio_w.sleep(2)
            _wt += 2
        if not _warmup_complete:
            from starlette.responses import JSONResponse as _jr
            return _jr(status_code=503, content={"detail": "Service warming up — retry in 30s"}, headers={"Retry-After": "30"})

    question_text = question.strip()

    # 1. Read the file
    file_bytes = await file.read()
    filename = (file.filename or "").lower()
    
    extracted_text = ""
    # 2. Parse based on extension
    if filename.endswith(".pdf"):
        from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
        import tempfile
        import os
        # Need to save to temp file for fitz to open
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        try:
            pages = extract_text_from_scanned_pdf(tmp_path)
            extracted_text = "\n".join(p["text"] for p in pages)
        finally:
            os.remove(tmp_path)
            
    elif filename.endswith((".png", ".jpg", ".jpeg")):
        from app.ingestion.pdf_scanned import extract_text_from_image
        extracted_text = extract_text_from_image(file_bytes)
    elif filename.endswith(".txt"):
        extracted_text = file_bytes.decode("utf-8", errors="replace")
    elif filename.endswith(".docx"):
        try:
            import docx as _docx
            from io import BytesIO as _BytesIO
            _doc = _docx.Document(_BytesIO(file_bytes))
            _paras = [p.text for p in _doc.paragraphs if p.text.strip()]
            # Also extract table cell text
            for _tbl in _doc.tables:
                for _row in _tbl.rows:
                    for _cell in _row.cells:
                        if _cell.text.strip():
                            _paras.append(_cell.text.strip())
            extracted_text = "\n".join(_paras)
        except Exception as _e:
            extracted_text = f"[DOCX extraction error: {_e}]"
    else:
        extracted_text = "[Unsupported file format. Please upload PDF, DOCX, TXT, PNG, JPG, or JPEG.]"
    
    # Save User Question
    if session_id:
        collection = get_session_collection()
        if collection is not None:
            from datetime import timezone as _tz
            collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": {
                        "message_id": str(uuid.uuid4()),
                        "role": "user",
                        "content": question_text,
                        "timestamp": datetime.now(_tz.utc),
                    }},
                    "$inc": {"message_count": 1},
                }
            )

    # Fetch history
    history_context = ""
    if session_id:
        collection = get_session_collection()
        if collection is not None:
            session = collection.find_one({"session_id": session_id})
            if session and "messages" in session:
                recent = session["messages"][:-1][-6:]
                for msg in recent:
                    history_context += f"{msg['role'].upper()}: {msg['content']}\n"

    # Offload to thread: route_query calls classify_intent() which makes a
    # blocking Haiku network call (5s cap).  Must not run on the event loop.
    import asyncio as _asyncio_route
    route = await _asyncio_route.to_thread(route_query, question_text)
    from app.generation.synthesizer import _estimate_complexity
    _file_complexity = _estimate_complexity(question_text)
    if _file_complexity >= 0.80:
        from app.retrieval.query_refiner import generate_advanced_queries
        advanced_queries = generate_advanced_queries(question_text)
        refined_q = advanced_queries.get("queries", [question_text])[0]
    else:
        advanced_queries = {"queries": [question_text], "hyde_document": "", "topic": "General", "subtopic": None}
        refined_q = question_text

    retriever = get_retriever()
    chunks = retriever.search(
        query=refined_q,
        top_k=15,
        allowed_sources=route["use_sources"],
        advanced_queries=advanced_queries,
        domain_paths=route.get("domain_paths", []),
    )
    from app.generation.context_builder import build_context
    from app.generation.context_compressor import compress_context
    rag_context = (
        build_context(chunks)
        + "\n\n--- COMPRESSED STATUTORY EXCERPTS (for quick reference) ---\n\n"
        + compress_context(chunks, question_text)
    )

    # Combine File Content with RAG Context
    file_context = ""
    if extracted_text.strip():
        file_context = f"\n--- UPLOADED FILE CONTENT ({file.filename}) ---\n{extracted_text}\n--- END UPLOADED FILE ---\n\n"
    
    full_rag_context = file_context + rag_context
    if history_context:
        full_rag_context = f"--- CHAT HISTORY ---\n{history_context}\n--- END HISTORY ---\n\n" + full_rag_context

    # Build truth rules text for hallucination guard
    from app.generation.rules_engine import rules_engine
    truth_rules_text = rules_engine.get_all_rules_as_text()

    # Generate Stream
    from app.generation.synthesizer import synthesize_answer_stream
    response_stream = synthesize_answer_stream(question_text, full_rag_context)

    from fastapi.responses import StreamingResponse
    wrapped_stream = stream_and_save(
        response_stream, session_id, question_text,
        chunks=chunks, context=rag_context, truth_rules_text=truth_rules_text,
    )

    return StreamingResponse(wrapped_stream, media_type="text/event-stream")


@app.post("/ask-with-file")
@limiter.limit("20/minute")
async def ask_question_with_file(
    request: Request,
    file: UploadFile = File(...),
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
):
    question_text = question.strip()
    user_id, username = _get_user_info_from_req(request)
    request_id = getattr(request.state, "query_id", str(uuid.uuid4())[:8])
    
    from app.ai_logger import init_ai_log
    init_ai_log(
        user_id=user_id,
        username=username,
        query=question_text,
        endpoint="/api/ask-with-file",
        session_id=session_id,
        request_id=request_id,
        client_ip=request.client.host if request.client else None
    )

    try:
        return await _execute_ask_question_with_file(request, file, question_text, session_id)
    except Exception as e:
        try:
            from app.ai_logger import commit_ai_log
            commit_ai_log(success=False, http_status=500, error_message=str(e))
        except Exception:
            pass
        raise e


# ---------- Feedback Endpoint ----------

class FeedbackRequest(BaseModel):
    session_id: Optional[str] = None
    question: str
    answer_preview: str
    rating: int          # 1 = thumbs up, -1 = thumbs down
    comment: Optional[str] = None

@app.post("/feedback")
@limiter.limit("60/minute")
async def submit_feedback(request: Request, req: FeedbackRequest):
    """Stores user ratings (thumbs up/down) for quality monitoring and future fine-tuning."""
    import logging
    _fb_logger = logging.getLogger("feedback")
    try:
        from app.database import get_db
        db = get_db()
        if db is not None:
            db["feedback"].insert_one({
                "session_id": req.session_id,
                "question": req.question,
                "answer_preview": req.answer_preview[:200],
                "rating": req.rating,
                "comment": req.comment,
                "user": "anonymous",
                "timestamp": datetime.now(),
            })
        _fb_logger.info(f"Feedback recorded | rating={req.rating} | q={req.question[:60]}")
        return {"status": "recorded", "rating": req.rating}
    except Exception as e:
        _fb_logger.error(f"Feedback save error: {e}")
        return {"status": "error", "detail": str(e)}


# ---------- PDF Reporting Endpoint ----------
from fastapi.responses import Response
from app.generation.pdf_report import PDFReportGenerator
import os

pdf_gen = PDFReportGenerator(output_dir="data/generated_reports")

class PDFRequest(BaseModel):
    title: str
    content: str

@app.post("/generate-pdf")
@limiter.limit("10/minute")
def create_pdf(request: Request, req: PDFRequest):
    # Use the class to generate PDF
    # We construct a filename
    import hashlib
    title_hash = hashlib.md5(req.title.encode()).hexdigest()[:8]
    filename = f"Report_{title_hash}.pdf"
    pdf_path = pdf_gen.generate_report(req.content, filename)
    
    if not os.path.exists(pdf_path):
        return Response(status_code=500, content="Error generating PDF")
        
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=advisory_report.pdf"}
    )

# ---------- Frontend Serving ----------
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# We look for the dist directory which should exist in the multi-stage docker container
frontend_dist_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if frontend_dist_path.exists() and frontend_dist_path.is_dir():
    # Mount assets directly
    assets_path = frontend_dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    
    # Catch-all route for SPA
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Ignore API routes
        if full_path.startswith("api/"):
            return Response(status_code=404)
            
        filepath = frontend_dist_path / full_path
        if filepath.exists() and filepath.is_file():
            return FileResponse(filepath)
            
        # Fallback to index.html for React Router
        index_path = frontend_dist_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
            
        return Response(status_code=404, content="Frontend not found")
