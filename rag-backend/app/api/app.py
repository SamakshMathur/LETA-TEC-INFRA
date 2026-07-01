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
        try:
            from app.dependencies import preload_all_models
            await _asyncio.to_thread(preload_all_models)
            logger.info("Startup model warmup complete")
        except Exception as e:
            logger.warning(f"Startup warmup failed (non-fatal): {e}")

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
    "https://gst-rag-95li.vercel.app",
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
    allow_origin_regex=r"^https://([a-z0-9-]+\.)?(vercel\.app|amplifyapp\.com)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
        # Block clickjacking
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
        # Remove server fingerprinting headers
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── Request size limit middleware ─────────────────────────────────────────────
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB

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
    query_id = str(uuid.uuid4())[:8]
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
    return response


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    # Skip X-Frame-Options for document view so the frontend iframe can embed PDFs
    if not request.url.path.startswith("/api/documents/view"):
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Rate limiting — user-ID keyed, Redis-backed when available
import base64 as _b64
import json as _json_ratelimit
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


def _rate_limit_key(request: Request) -> str:
    """Prefer JWT user-ID over IP so limits survive proxy/CDN hops."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            parts = auth.split(".")
            if len(parts) == 3:
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = _json_ratelimit.loads(_b64.b64decode(padded))
                if "sub" in payload:
                    return f"user:{payload['sub']}"
        except Exception:
            pass
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis as _r
        _r.from_url(_redis_url, socket_connect_timeout=1).ping()
        lim = Limiter(key_func=_rate_limit_key, storage_uri=_redis_url)
        logger.info("Rate limiter: Redis-backed (distributed)")
        return lim
    except Exception as _e:
        logger.warning(f"Rate limiter: in-memory fallback (Redis unavailable: {_e})")
        return Limiter(key_func=_rate_limit_key)


limiter = _build_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

from app.api import feed
app.include_router(feed.router, prefix="/api/feed", tags=["Feed"])

from app.api import transcribe
app.include_router(transcribe.router, prefix="/api", tags=["Transcribe"])

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

async def stream_and_save(generator, session_id, user_query, chunks=None, context="", truth_rules_text="", query_vec=None, is_draft_session: bool = False):
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
                    unique_sources.append({
                        "title": _basename or "Document",
                        "page": c.get("page", 1),
                        "url": _url,
                        "rel_path": _rel_path,
                        "score": float(c.get("_rerank_score", 0))
                    })
                if len(unique_sources) >= 8: # Limit to top 8 unique sources
                    break
            
            metadata_payload = {
                "type": "metadata",
                "sources": unique_sources
            }
            yield f"__METADATA__:{json.dumps(metadata_payload)}__END_METADATA__"
        except Exception as me:
            _logger.warning(f"Metadata emission failed: {me}")

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

                async def run_hallucination_guard():
                    try:
                        from app.generation.hallucination_guard import check_hallucinated_numbers
                        return check_hallucinated_numbers(full_answer, context, truth_rules_text, chunks)
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
                        ),
                        timeout=3.0,
                    )
                except asyncio.TimeoutError:
                    _logger.warning("Post-generation validators timed out — skipping")
                    results = (full_answer, "")

                _, hallu_warn = results

                # Log internally — validator output is NEVER streamed to the user.
                # Citation validator already logs its own warnings.
                if hallu_warn:
                    _logger.warning(f"Hallucination guard: {hallu_warn[:300]}")

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
                    await asyncio.to_thread(
                        collection.update_one,
                        {"session_id": session_id},
                        {
                            "$push": {"messages": {
                                "role": "assistant",
                                "content": full_answer,
                                "sources": unique_sources,
                                "timestamp": datetime.now(),
                            }},
                            "$set": {"updated_at": datetime.now()},
                        },
                    )
                except Exception as dbe:
                    _logger.warning(f"DB save error (non-fatal): {dbe}")

        # Confidence-gated cache store — also off the event loop
        if full_answer.strip() and query_vec is not None:
            try:
                from app.cache import cache_store
                from app.generation.confidence import estimate_confidence
                confidence = await asyncio.to_thread(estimate_confidence, full_answer, chunks or [])
                await asyncio.to_thread(cache_store, user_query, query_vec, full_answer, confidence, unique_sources if chunks else [])
                _logger.debug(f"Cache store attempt | confidence={confidence:.2f}")
            except Exception as ce:
                _logger.warning(f"Cache store error (non-fatal): {ce}")

_ask_logger = logging.getLogger("leta.ask")

@app.post("/ask")
@limiter.limit("30/minute")
async def ask_question(request: Request, req: QuestionRequest):
    question = req.question.strip()
    session_id = req.session_id
    query_id = getattr(request.state, "query_id", str(uuid.uuid4())[:8])
    t0 = time.monotonic()

    # IMMEDIATE SAVE: Save User Question First
    if session_id:
        collection = get_session_collection()
        if collection is not None:
             collection.update_one(
                {"session_id": session_id},
                {"$push": {"messages": {"role": "user", "content": question, "timestamp": datetime.now()}}}
            )

    async def rag_pipeline_orchestrator():
        # ── Stage 1: Query classifier + domain router (pure keyword, <1ms) ──────
        from app.routing.router import route_query
        from app.generation.synthesizer import _estimate_complexity
        from app.generation.calculation_engine import detect_and_calculate, format_for_context
        from app.generation.context_compressor import compress_context

        route = route_query(question)
        domain_paths = route.get("domain_paths", [])
        _complexity = _estimate_complexity(question)

        # Query-aware Pulse 1 message
        _q = question.lower()
        if "rule 42" in _q or "rule42" in _q:
            _init_msg = "Computing Rule 42 ITC Reversal..."
        elif "rule 43" in _q or "rule43" in _q:
            _init_msg = "Computing Rule 43 Capital Goods Reversal..."
        elif any(k in _q for k in ["itc", "input tax credit", "section 16", "section 17"]):
            _init_msg = "Analyzing ITC Eligibility Provisions..."
        elif any(k in _q for k in ["draft","notice","reply","appeal","submission","scn","show cause","drc-01","drc 01","asmt-10","representation","advisory","our understanding","gst implications","provide opinion","our comments","tax position","advise on"]):
            _init_msg = "Initializing Advisory & Drafting Engine..."
        elif any(k in _q for k in ["refund", "export", "lut"]):
            _init_msg = "Checking Refund & Export Provisions..."
        elif any(k in _q for k in ["interest", "section 50", "penalty"]):
            _init_msg = "Computing Interest & Penalty Exposure..."
        else:
            _init_msg = "Initializing Statutory Analyzer..."

        yield f"__STATUS__:{json.dumps({'msg': _init_msg})}__END_STATUS__"

        # 1. Fetch session history
        history_context = ""
        _session_is_draft = False  # becomes True if history shows ongoing advisory/draft session
        if session_id:
            collection = get_session_collection()
            if collection is not None:
                session = collection.find_one({"session_id": session_id})
                if session and "messages" in session:
                    recent = session["messages"][:-1][-6:]
                    for msg in recent:
                        history_context += f"{msg['role'].upper()}: {msg['content']}\n"
                    # If any recent message contains draft/advisory signals, keep the session
                    # in draft mode — this ensures follow-up messages (clarifications, corrections,
                    # "re-analyze" requests) continue routing through DRAFTING_PROMPT.
                    _HISTORY_DRAFT_KW = [
                        "advisory","our understanding","gst implications","gst implication",
                        "provide opinion","our comments","tax position","gst treatment",
                        "advise on","legal opinion","our client","we are engaged",
                        "facts of the case","b)  our comments","our comments from gst",
                        "draft","notice","reply","appeal","scn","show cause",
                        "drc-01","drc-07","asmt-10","representation",
                        # LETA's own advisory/analysis output markers
                        "our comments from gst perspective",
                        "i've reviewed your","issue raised","section invoked",
                        "to draft a strong reply",
                    ]
                    _hist_lower = history_context.lower()
                    _session_is_draft = any(k in _hist_lower for k in _HISTORY_DRAFT_KW)

        # ── Stage 2: Cache lookup (L1 exact + L2 semantic) ───────────────────────
        from app.cache import cache_lookup
        from app.retrieval.retriever import embed_query

        yield f"__STATUS__:{json.dumps({'msg': 'Scanning Semantic Cache...'})}__END_STATUS__"
        query_vec = embed_query(question)
        cached_answer = cache_lookup(question, query_vec)

        if cached_answer:
            cached_text, cached_sources = cached_answer
            _ask_logger.info("Cache HIT", extra={"query_id": query_id, "cache_hit": True})
            yield f"__STATUS__:{json.dumps({'msg': 'Cache Hit — Instant Retrieval Complete.'})}__END_STATUS__"
            if cached_sources:
                yield f"__METADATA__:{json.dumps({'type': 'metadata', 'sources': cached_sources})}__END_METADATA__"
            yield cached_text
            return

        # ── Stage 3: Pre-computed calculation injection (deterministic, <1ms) ────
        calc_result = detect_and_calculate(question)
        calc_block = format_for_context(calc_result) if calc_result else ""
        if calc_result:
            yield f"__STATUS__:{json.dumps({'msg': 'Pre-computing Statutory Formula...'})}__END_STATUS__"

        # ── Stage 4: Query expansion — only for deeply complex non-draft queries ────
        _DRAFT_KW_EARLY = ["draft","notice","reply","appeal","submission","advisory","scn","show cause","drc-01","drc 01","asmt-10","asmt 10","drc-07","drc 07","drc-03","drc 03","write a letter","write letter","prepare reply","representation","response to notice","respond to","our understanding","gst implications","gst implication","provide opinion","provide advisory","our comments","tax position","gst treatment of","advise on","legal opinion","our client is","we are engaged in","facts of the case"]
        _is_draft_early = _session_is_draft or any(k in _q for k in _DRAFT_KW_EARLY)

        if _complexity >= 0.35 and not _is_draft_early:
            yield f"__STATUS__:{json.dumps({'msg': 'Expanding Query for Precision Retrieval...'})}__END_STATUS__"
            from app.retrieval.query_refiner import generate_advanced_queries
            advanced_queries = generate_advanced_queries(question)
            refined_q = advanced_queries.get("queries", [question])[0]
        else:
            advanced_queries = {"queries": [question], "hyde_document": "", "topic": "General", "subtopic": None}
            refined_q = question

        # ── Phase 2B: Draft sub-query injection (no LLM call — rule-based) ────────
        if _is_draft_early:
            _statute_q  = refined_q + " section rule act provisions conditions eligibility liability"
            _caselaw_q  = refined_q + " high court supreme court judgment held ruling decision AAR"
            _circular_q = refined_q + " CBIC circular notification clarification instruction"
            advanced_queries["queries"] = [refined_q, _statute_q, _caselaw_q, _circular_q]

        # ── Stage 5: Targeted hybrid retrieval ────────────────────────────────────
        domain_label = ", ".join(domain_paths[:2]) if domain_paths else "All Databases"
        yield f"__STATUS__:{json.dumps({'msg': f'Querying Statutory Provisions ({domain_label})...'})}__END_STATUS__"
        retriever = get_retriever()
        _DRAFT_KW = ["draft","notice","reply","appeal","submission","advisory","scn","show cause","drc-01","drc 01","asmt-10","asmt 10","drc-07","drc 07","drc-03","drc 03","write a letter","write letter","prepare reply","representation","response to notice","respond to","our understanding","gst implications","gst implication","provide opinion","provide advisory","our comments","tax position","gst treatment of","advise on","legal opinion","our client is","we are engaged in","facts of the case"]
        _is_draft = _session_is_draft or any(k in _q for k in _DRAFT_KW)
        _retrieval_top_k = 30 if _is_draft else (25 if _complexity >= 0.60 else 20)
        chunks = retriever.search(
            query=refined_q,
            top_k=_retrieval_top_k,
            allowed_sources=route["use_sources"],
            advanced_queries=advanced_queries,
            domain_paths=domain_paths,
            is_draft=_is_draft,
        )

        # ── Stage 6: Context assembly — citation registry + compressed excerpts ───
        # build_context() provides the citation registry (hallucination grounding).
        # compress_context() provides the focused factual text block (speed).
        citation_block = build_context(chunks, is_draft=_is_draft)      # ~5 KB: registry + authority metadata
        compressed_block = compress_context(chunks, question, is_draft=_is_draft)  # focused excerpts

        full_rag_context = (
            (f"--- CHAT HISTORY ---\n{history_context}\n--- END HISTORY ---\n\n" if history_context else "")
            + citation_block
            + (f"\n\n{calc_block}" if calc_block else "")
            + "\n\n--- COMPRESSED STATUTORY EXCERPTS (for quick reference) ---\n\n"
            + compressed_block
        )

        from app.generation.rules_engine import rules_engine
        truth_rules_text = rules_engine.get_all_rules_as_text()

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

        async for chunk in stream_and_save(
            response_stream, session_id, question,
            chunks=chunks, context=citation_block, truth_rules_text=truth_rules_text,
            query_vec=query_vec, is_draft_session=_is_draft,
        ):
            yield chunk

    from fastapi.responses import StreamingResponse
    return StreamingResponse(rag_pipeline_orchestrator(), media_type="text/event-stream")


@app.post("/ask-sync")
@limiter.limit("20/minute")
async def ask_question_sync(request: Request, req: QuestionRequest):
    """Non-streaming version of /ask — returns complete JSON response.
    Required for AWS API Gateway HTTP_PROXY compatibility (no SSE streaming support)."""
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
            collection.update_one(
                {"session_id": session_id},
                {"$push": {"messages": {"role": "user", "content": question, "timestamp": datetime.now()}}}
            )

    route = _route_query(question)
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
        return _JSONResponse({"answer": cached_text, "sources": cached_sources or []})

    calc_result = detect_and_calculate(question)
    calc_block = format_for_context(calc_result) if calc_result else ""

    _DRAFT_KW = [
        "draft", "notice", "reply", "appeal", "submission", "advisory", "scn", "show cause",
        "drc-01", "drc 01", "asmt-10", "our understanding", "gst implications",
        "provide opinion", "our comments", "tax position", "advise on",
    ]
    _is_draft = _session_is_draft or any(k in _q for k in _DRAFT_KW)

    # Skip LLM-based query expansion in sync mode — saves ~10-15s from the extra Sonnet call.
    # Use rule-based multi-query for drafts only (no LLM needed).
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
        advanced_queries = {"queries": [question], "hyde_document": "", "topic": "General", "subtopic": None}

    retriever = get_retriever()
    # Reduced top_k + skip_rerank: FlashRank with ms-marco-MiniLM-L-12-v2 takes
    # 30-50s on 100+ candidates — must bypass it to fit inside API Gateway's 29s timeout.
    _top_k = 15 if _is_draft else (12 if _complexity >= 0.60 else 10)
    chunks = retriever.search(
        query=refined_q,
        top_k=_top_k,
        allowed_sources=route["use_sources"],
        advanced_queries=advanced_queries,
        domain_paths=domain_paths,
        is_draft=_is_draft,
        skip_rerank=True,
    )

    citation_block = build_context(chunks, is_draft=_is_draft)
    compressed_block = compress_context(chunks, question, is_draft=_is_draft)
    full_rag_context = (
        (f"--- CHAT HISTORY ---\n{history_context}\n--- END HISTORY ---\n\n" if history_context else "")
        + citation_block
        + (f"\n\n{calc_block}" if calc_block else "")
        + "\n\n--- COMPRESSED STATUTORY EXCERPTS (for quick reference) ---\n\n"
        + compressed_block
    )

    # Drafts (notice replies, advisories) MUST use Sonnet — they require 5,000–12,000 tokens.
    # Non-draft Q&A uses Haiku to stay within API Gateway's 29-second timeout.
    answer = await _asyncio.to_thread(
        lambda: "".join(_synth_stream(question, full_rag_context, session_is_draft=_is_draft, force_haiku=not _is_draft))
    )

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
            unique_sources.append({
                "title": _basename or "Document",
                "page": c.get("page", 1),
                "url": _url,
                "rel_path": _rel_path,
                "score": float(c.get("_rerank_score", 0)),
            })
        if len(unique_sources) >= 8:
            break

    if session_id and answer.strip():
        collection = get_session_collection()
        if collection is not None:
            collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": {"role": "assistant", "content": answer, "timestamp": datetime.now()}},
                    "$set": {"updated_at": datetime.now()},
                }
            )

    return _JSONResponse({"answer": answer, "sources": unique_sources})


@app.post("/ask-with-file")
@limiter.limit("20/minute")
async def ask_question_with_file(
    request: Request,
    file: UploadFile = File(...),
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
):
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
             collection.update_one(
                {"session_id": session_id},
                {"$push": {"messages": {"role": "user", "content": question_text, "timestamp": datetime.now()}}}
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
    
    # Route + optional query expansion (blocked Haiku call — skip for simple queries)
    route = route_query(question_text)
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
def create_pdf(req: PDFRequest):
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
