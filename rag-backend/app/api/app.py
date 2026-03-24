from fastapi import FastAPI, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.retrieval.retriever import Retriever
from app.routing.router import route_query
from app.generation.context_builder import build_context
from app.generation.final_answer import build_final_answer
from app.routing.intent_classifier import classify_intent

# ---------- App ----------
app = FastAPI(
    title="GST Legal RAG API",
    version="1.0",
    description="In-house GST knowledge assistant",
    # docs_url=None, # Temporarily un-hidden for the user
    # redoc_url=None # Temporarily un-hidden for the user
)

from fastapi.middleware.cors import CORSMiddleware
import os

# CORS: Use ALLOWED_ORIGINS env var in production (comma-separated),
# falls back to localhost dev origins when not set.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
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

# Maximum Security: Strict Security Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Maximum Security: Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
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
import json
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

async def stream_and_save(generator, session_id, user_query, chunks=None, context="", truth_rules_text=""):
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
    full_answer = ""
    try:
        for chunk in generator:
            full_answer += chunk
            yield chunk

        if chunks and full_answer.strip():
            # --- Layer 1: Citation Validator ---
            try:
                from app.generation.citation_validator import CitationValidator
                annotated = CitationValidator.validate_citations(full_answer, chunks)
                report = annotated[len(full_answer):]
                if report:
                    full_answer = annotated
                    yield report
            except Exception as e:
                _logger.warning(f"Citation validator error: {e}")

            # --- Layer 2: Answer Verifier (LLM second-pass) ---
            try:
                from app.generation.answer_verifier import verify_answer
                verification_warning = verify_answer(user_query, full_answer, chunks)
                if verification_warning:
                    full_answer += verification_warning
                    yield verification_warning
            except Exception as e:
                _logger.warning(f"Answer verifier error: {e}")

            # --- Layer 3: Hallucination Guard (ungrounded numbers) ---
            try:
                from app.generation.hallucination_guard import check_hallucinated_numbers
                number_warning = check_hallucinated_numbers(
                    full_answer, context, truth_rules_text, chunks,
                )
                if number_warning:
                    full_answer += number_warning
                    yield number_warning
            except Exception as e:
                _logger.warning(f"Hallucination guard error: {e}")

            # --- Layer 4: Template Matcher ---
            try:
                from app.retrieval.template_matcher import search_templates, format_template_suggestions
                matched_templates = search_templates(user_query, top_k=3)
                template_block = format_template_suggestions(matched_templates)
                if template_block:
                    full_answer += template_block
                    yield template_block
            except Exception as e:
                _logger.warning(f"Template matcher error: {e}")

    except Exception as e:
        _logger.error(f"Error in stream_and_save: {e}")
        yield f"\n[System Error: {str(e)}]"
    finally:
        # Save whatever we have generated so far
        if session_id and full_answer.strip():
            collection = get_session_collection()
            if collection is not None:
                collection.update_one(
                    {"session_id": session_id},
                    {"$push": {"messages": {"role": "assistant", "content": full_answer, "timestamp": datetime.now()}},
                     "$set": {"updated_at": datetime.now()}}
                )

from app.security import get_current_user
from fastapi import Depends, Request

@app.post("/ask")
@limiter.limit("30/minute")
async def ask_question(request: Request, req: QuestionRequest, current_user: dict = Depends(get_current_user)):
    question = req.question.strip()
    session_id = req.session_id
    
    # IMMEDIATE SAVE: Save User Question First to prevent data loss on switch
    if session_id:
        collection = get_session_collection()
        if collection is not None:
             collection.update_one(
                {"session_id": session_id},
                {"$push": {"messages": {"role": "user", "content": question, "timestamp": datetime.now()}}}
            )
    
    # 1. Fetch History if Session ID exists (exclude the just-added current question)
    history_context = ""
    if session_id:
        collection = get_session_collection()
        if collection is not None:
            session = collection.find_one({"session_id": session_id})
            if session and "messages" in session:
                recent = session["messages"][:-1][-6:]
                for msg in recent:
                    history_context += f"{msg['role'].upper()}: {msg['content']}\n"
    
    # Smart Query Refinement & Expansion (HyDE + Multi-Query)
    from app.retrieval.query_refiner import generate_advanced_queries
    advanced_queries = generate_advanced_queries(question)
    refined_q = advanced_queries.get("queries", [question])[0] # Use the first query for simple routing functions below
    
    intent_info = classify_intent(refined_q)
    intent = intent_info["intent"]
    route = route_query(refined_q)
    retriever = get_retriever()
    chunks = retriever.search(
        query=refined_q,
        top_k=50,
        allowed_sources=route["use_sources"],
        advanced_queries=advanced_queries
    )
    context = build_context(chunks)
    
    # Append History to Context
    full_rag_context = context
    if history_context:
        full_rag_context = f"--- CHAT HISTORY ---\n{history_context}\n--- END HISTORY ---\n\n" + context

    # Build truth rules text for hallucination guard
    from app.generation.rules_engine import rules_engine
    truth_rules_text = rules_engine.get_all_rules_as_text()

    # Generate streaming answer
    from app.generation.synthesizer import synthesize_answer_stream
    response_stream = synthesize_answer_stream(question, full_rag_context)

    from fastapi.responses import StreamingResponse
    # Wrap with full post-generation accuracy pipeline
    wrapped_stream = stream_and_save(
        response_stream, session_id, question,
        chunks=chunks, context=context, truth_rules_text=truth_rules_text,
    )

    return StreamingResponse(wrapped_stream, media_type="text/event-stream")

@app.post("/ask-with-file")
@limiter.limit("20/minute")
async def ask_question_with_file(
    request: Request,
    file: UploadFile = File(...),
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
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
    
    intent_info = classify_intent(refined_q)
    intent = intent_info["intent"]
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
async def submit_feedback(request: Request, req: FeedbackRequest, current_user: dict = Depends(get_current_user)):
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
                "user": current_user.get("username", "anonymous"),
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
    filename = f"Report_{hash(req.title)}.pdf"
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
import os
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
