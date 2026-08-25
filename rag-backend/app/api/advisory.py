"""
Advisory API router — /api/advisory/generate

Two endpoints:
  POST /generate          — buffered JSON (backward-compat, ≤35s on Sonnet)
  POST /generate-stream   — SSE streaming (keeps ALB alive for any length)

The streaming endpoint is the preferred path for long advisory queries.
Frontend should switch to /generate-stream for advisory generation.
"""
import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.generation.advisory import generate_legal_advisory, _build_user_message
from app.routing.router import route_query
from app.dependencies import get_retriever
from app.generation.context_builder import build_context
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Shared helpers ────────────────────────────────────────────────────────────

def _extract_subject(query: str) -> str:
    lines = [l.strip() for l in query.splitlines() if l.strip()]
    topic_patterns = [
        r"advisory (?:services )?on (.{10,120})",
        r"GST implication[s]? on (.{10,120})",
        r"analyzing (.{10,120})",
        r"provide (?:advisory|opinion|comments) on (.{10,120})",
    ]
    for line in lines[:8]:
        for pat in topic_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                return m.group(1).rstrip(".,;:")[:160]
    for line in lines:
        if len(line) > 20:
            return line[:160]
    return "GST Implications on the Specified Transaction"


def _fetch_context(query: str, context_text: Optional[str]) -> str:
    """Use provided context if rich enough, else re-retrieve."""
    if context_text and len(context_text) >= 50:
        return context_text
    retriever = get_retriever()
    search_query = query[:500] if len(query) > 500 else query
    chunks = retriever.search(query=search_query, top_k=30)
    return build_context(chunks)


class AdvisoryRequest(BaseModel):
    query: str
    context_text: Optional[str] = None
    manual_case: bool = False


# ── POST /generate — buffered JSON (backward compat) ─────────────────────────

@router.post("/generate")
async def create_advisory(
    req: AdvisoryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Buffered advisory generation. Works for most queries (≤35s).
    For very long drafts, use /generate-stream instead.
    """
    try:
        context_to_use = _fetch_context(req.query, req.context_text)
        result = await __import__("fastapi").concurrency.run_in_threadpool(
            generate_legal_advisory,
            user_input=req.query,
            context=context_to_use,
            subject=_extract_subject(req.query),
        )
        return {
            "advisory": result["content"],
            "pdf_url":  result["pdf_url"],
            "status":   "success",
            "cached":   result.get("cached", False),
        }
    except Exception as e:
        logger.error(f"Advisory generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /generate-stream — SSE streaming (long drafts, keeps ALB alive) ─────

@router.post("/generate-stream")
async def create_advisory_stream(
    req: AdvisoryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming advisory generation via SSE.
    Keeps the ALB connection alive even for 60-90s Sonnet responses.
    Frontend reads the stream and assembles the final advisory.

    SSE event types emitted:
      data: {"type":"token",  "text":"<chunk>"}
      data: {"type":"done",   "pdf_url":"<url>|null"}
      data: {"type":"error",  "detail":"<msg>"}
    """
    context_to_use = _fetch_context(req.query, req.context_text)

    async def event_generator():
        import hashlib
        import anthropic as _anthropic
        from app.config import ANTHROPIC_API_KEY, CLAUDE_MAIN_MODEL, PROMPT_VERSION
        from app.generation.rules_engine import rules_engine
        from app.generation.prompts.advisory_prompt import ADVISORY_SYSTEM_PROMPT
        from app.generation.pdf_report import PDFReportGenerator
        from app.config import DATA_DIR
        import os

        query_hash = hashlib.md5((req.query + context_to_use[:100]).encode()).hexdigest()
        cache_key  = f"advisory_{PROMPT_VERSION}_{query_hash}"

        # ── Cache hit ─────────────────────────────────────────────────────────
        from diskcache import Cache
        from app.config import CACHE_DIR
        _cache = Cache(CACHE_DIR)
        if cache_key in _cache:
            cached = _cache[cache_key]
            yield f"data: {json.dumps({'type': 'token', 'text': cached['content']})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'pdf_url': cached.get('pdf_url'), 'cached': True})}\n\n"
            return

        # ── Stream from Claude ────────────────────────────────────────────────
        try:
            rules_text    = rules_engine.get_all_rules_as_text()
            system_prompt = ADVISORY_SYSTEM_PROMPT.format(rules_context=rules_text)
            user_message  = _build_user_message(req.query, context_to_use)

            import httpx as _httpx
            client = _anthropic.Anthropic(
                api_key=ANTHROPIC_API_KEY,
                timeout=_httpx.Timeout(timeout=900.0, connect=10.0),  # 15-min ceiling; no ALB in this deployment
            )

            full_text = ""
            with client.messages.stream(
                model=CLAUDE_MAIN_MODEL,
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for text_chunk in stream.text_stream:
                    full_text += text_chunk
                    yield f"data: {json.dumps({'type': 'token', 'text': text_chunk})}\n\n"

            # ── PDF ───────────────────────────────────────────────────────────
            pdf_url = None
            try:
                reports_dir = os.path.join(DATA_DIR, "generated_reports")
                _pdf_gen = PDFReportGenerator(output_dir=reports_dir)
                filename = f"Advisory_{query_hash[:8]}.pdf"
                _pdf_gen.generate_report(full_text, filename=filename)
                pdf_url = f"/api/documents/view?category=reports&filename={filename}"
            except Exception as pe:
                logger.warning(f"PDF generation failed (non-fatal): {pe}")

            # ── Cache store ───────────────────────────────────────────────────
            if full_text and len(full_text) > 100:
                _cache[cache_key] = {
                    "content": full_text, "pdf_url": pdf_url, "cached": True
                }

            yield f"data: {json.dumps({'type': 'done', 'pdf_url': pdf_url, 'cached': False})}\n\n"

        except Exception as e:
            logger.error(f"Advisory stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )
