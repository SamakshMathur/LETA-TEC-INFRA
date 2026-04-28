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

@app.get("/")
async def root():
    return {
        "message": "GST Legal RAG API is running.",
        "docs": "/docs",
        "health": "/api/health"
    }

from fastapi.middleware.cors import CORSMiddleware
import os

# CORS: Use ALLOWED_ORIGINS env var in production (comma-separated),
# falls back to localhost dev origins when not set.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,https://gst-rag-95li.vercel.app"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

async def stream_and_save(generator, session_id, user_query, chunks=None, context="", truth_rules_text="", query_vec=None):
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
                src_key = (c.get("source"), c.get("page", 0))
                if src_key not in seen_src:
                    seen_src.add(src_key)
                    _raw_src = c.get("source", "")
                    _basename = os.path.basename(_raw_src)
                    _enc_name = _urlparse.quote(_basename, safe="")
                    unique_sources.append({
                        "title": _basename or "Document",
                        "page": c.get("page", 1),
                        "url": f"/api/documents/view?category=all&filename={_enc_name}&page={c.get('page', 1)}",
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
            # Detect drafting intent to bypass the accuracy pipeline
            is_draft = any(kw in user_query.lower() for kw in ["draft", "notice", "reply", "appeal", "submission", "advisory"])
            
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

                annotated_answer, hallu_warn = results
                verify_warn = None

                if annotated_answer and len(annotated_answer) > len(full_answer):
                    report = annotated_answer[len(full_answer):]
                    full_answer = annotated_answer
                    yield report
                
                if verify_warn:
                    full_answer += verify_warn
                    yield verify_warn
                
                if hallu_warn:
                    full_answer += hallu_warn
                    yield hallu_warn
                
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
                            "$push": {"messages": {"role": "assistant", "content": full_answer, "timestamp": datetime.now()}},
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
        # --- Pulse 1: Analyzer Initialize (~100ms) ---
        yield f"__STATUS__:{json.dumps({'msg': 'Initializing Statutory Analyzer...'})}__END_STATUS__"
        
        # 1. Fetch History if Session ID exists
        history_context = ""
        if session_id:
            collection = get_session_collection()
            if collection is not None:
                session = collection.find_one({"session_id": session_id})
                if session and "messages" in session:
                    recent = session["messages"][:-1][-6:]
                    for msg in recent:
                        history_context += f"{msg['role'].upper()}: {msg['content']}\n"

        # ── Fast local routing (keyword-only, no LLM call) ──
        from app.routing.router import route_query
        route = route_query(question)
        domain = route.get("domain", "general")

        # ── Cache lookup (L1 exact + L2 semantic) ────────────────────────────────
        from app.cache import cache_lookup
        from app.retrieval.retriever import embed_query
        
        yield f"__STATUS__:{json.dumps({'msg': f'Scanning Semantic Cache for {domain.upper()}...'})}__END_STATUS__"
        query_vec = embed_query(question)
        cached_answer = cache_lookup(question, query_vec)
        
        if cached_answer:
            cached_text, cached_sources = cached_answer
            _ask_logger.info("Cache HIT", extra={"query_id": query_id, "cache_hit": True})
            yield f"__STATUS__:{json.dumps({'msg': 'Instant Statutory Retrieval Complete.'})}__END_STATUS__"
            if cached_sources:
                import json as _json
                yield f"__METADATA__:{_json.dumps({'type': 'metadata', 'sources': cached_sources})}__END_METADATA__"
            yield cached_text
            return

        # --- Pulse 2: Expansion (only for very complex multi-section queries) ---
        # Threshold raised 0.25 → 0.70: query expansion is a blocking Haiku API
        # call (~3-5s). Skip it for everything except complex drafting / disputes.
        from app.generation.synthesizer import _estimate_complexity
        _complexity = _estimate_complexity(question)
        if _complexity >= 0.70:
            yield f"__STATUS__:{json.dumps({'msg': 'Deep Legal Analysis Mode...'})}__END_STATUS__"
            from app.retrieval.query_refiner import generate_advanced_queries
            advanced_queries = generate_advanced_queries(question)
            refined_q = advanced_queries.get("queries", [question])[0]
        else:
            advanced_queries = {"queries": [question], "hyde_document": "", "topic": "General", "subtopic": None}
            refined_q = question

        # --- Pulse 3: Retrieval ---
        yield f"__STATUS__:{json.dumps({'msg': f'Querying Statutory Provisions ({domain.upper()})...'})}__END_STATUS__"
        retriever = get_retriever()
        chunks = retriever.search(
            query=refined_q,
            top_k=15,
            allowed_sources=route["use_sources"],
            advanced_queries=advanced_queries,
        )
        context = build_context(chunks)

        # Append History to Context
        full_rag_context = context
        if history_context:
            full_rag_context = f"--- CHAT HISTORY ---\n{history_context}\n--- END HISTORY ---\n\n" + context

        # Build truth rules text for hallucination guard
        from app.generation.rules_engine import rules_engine
        truth_rules_text = rules_engine.get_all_rules_as_text()

        # --- Pulse 4: Final Synthesis ---
        yield f"__STATUS__:{json.dumps({'msg': 'Synthesizing Sovereign Legal Position...'})}__END_STATUS__"
        
        from app.generation.synthesizer import synthesize_answer_stream
        response_stream = synthesize_answer_stream(question, full_rag_context)

        # Wrap with full post-generation accuracy pipeline + cache store
        async for chunk in stream_and_save(
            response_stream, session_id, question,
            chunks=chunks, context=context, truth_rules_text=truth_rules_text,
            query_vec=query_vec,
        ):
            yield chunk

    from fastapi.responses import StreamingResponse
    return StreamingResponse(rag_pipeline_orchestrator(), media_type="text/event-stream")

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
    else:
        # Fallback or unsupported
        extracted_text = "[Unsupported file format. Please upload PDF, PNG, JPG, or TXT.]"
    
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
    
    # Retrieve standard context with Advanced Expansions
    from app.retrieval.query_refiner import generate_advanced_queries
    advanced_queries = generate_advanced_queries(question_text)
    refined_q = advanced_queries.get("queries", [question_text])[0]
    
    route = route_query(refined_q)
    retriever = get_retriever()
    chunks = retriever.search(
        query=refined_q,
        top_k=50,
        allowed_sources=route["use_sources"],
        advanced_queries=advanced_queries
    )
    from app.generation.context_builder import build_context
    rag_context = build_context(chunks)

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
