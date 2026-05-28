from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.generation.advisory import generate_legal_advisory
# We might need to import retriever/context builder if we want to re-fetch context
# But for simplicity, we'll ask the frontend to pass the context OR re-run retrieval.
# Better approach: Re-run retrieval to ensure fresh context or allow passing "context_id" (too complex).
# Simplest: The frontend passes the original query, we re-run retrieval, OR frontend passes the "answer" text.
# ACTUALLY: The user might want to generate advisory on a NEW manual case.
# Let's support both.

from app.routing.router import route_query
from app.dependencies import get_retriever # FIX: Use safe dependencies module
from app.generation.context_builder import build_context
from app.security import get_current_user
from fastapi import Depends

router = APIRouter()


def _extract_subject(query: str) -> str:
    """
    Derive a meaningful subject line from the raw query text.
    Priority:
      1. First line that contains "advisory on" / "GST implication" / "provide advisory"
      2. First sentence that mentions a recognisable legal keyword
      3. Fallback: first 120 chars of the query
    """
    import re

    lines = [l.strip() for l in query.splitlines() if l.strip()]

    # Look for lines that state the topic directly
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
                subject = m.group(1).rstrip(".,;:")
                return subject[:160]

    # Fallback: first non-trivial line, capped at 160 chars
    for line in lines:
        if len(line) > 20:
            return line[:160]

    return "GST Implications on the Specified Transaction"


class AdvisoryRequest(BaseModel):
    query: str # The core question or facts
    context_text: Optional[str] = None # Optional: If frontend already has context/answer
    manual_case: bool = False # If true, treat query as "Facts of the Case"

@router.post("/generate")
async def create_advisory(req: AdvisoryRequest, current_user: dict = Depends(get_current_user)):
    try:
        context_to_use = req.context_text
        
        # If no context provided/manual case -> Retrieve fresh context (Standard RAG)
        # Even for manual cases, we want to find relevant LAW.
        if not context_to_use or len(context_to_use) < 50:
            # Retrieve fresh statutory context.
            # Advisory queries are often long multi-issue queries — use top_k=30
            # to pull provisions, circulars, rules, and case law for every issue.
            retriever = get_retriever()

            # For very long queries (full facts pasted), extract a compact search
            # string from the first 500 chars to keep embedding quality high.
            search_query = req.query[:500] if len(req.query) > 500 else req.query

            chunks = retriever.search(query=search_query, top_k=30)
            context_to_use = build_context(chunks)

        # Generate! (Run in threadpool to avoid blocking event loop)
        from fastapi.concurrency import run_in_threadpool
        result = await run_in_threadpool(
            generate_legal_advisory,
            user_input=req.query,
            context=context_to_use,
            subject=_extract_subject(req.query),   # used for PDF filename / cache key only
        )
        
        return {
            "advisory": result["content"],
            "pdf_url": result["pdf_url"],
            "status": "success",
            "cached": result.get("cached", False)
        }

    except Exception as e:
        print(f"Advisory Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
