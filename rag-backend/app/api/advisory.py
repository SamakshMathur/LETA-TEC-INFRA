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
             # 1. Retrieve relevant law based on the query/facts
            retriever = get_retriever()
            # If manual case, maybe query is long. We might need to extract keywords.
            # For now, let's use the query as is.
            chunks = retriever.search(query=req.query, top_k=20) 
            context_to_use = build_context(chunks)

        subject_line = "GST Applicability and Compliance" 
        # Trivial subject extraction, can be improved.
        if len(req.query) < 50:
            subject_line = req.query
        else:
            subject_line = "Query regarding GST implications on specified transaction"

        # Generate! (Run in threadpool to avoid blocking event loop)
        from fastapi.concurrency import run_in_threadpool
        result = await run_in_threadpool(
            generate_legal_advisory,
            user_input=req.query,
            context=context_to_use,
            subject=subject_line
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
