import os
import faiss
from app.mission_control.registry import register_tool
from app.mission_control.schemas import (
    ToolInfo, ToolParameter, ToolResult, ToolResultStatus, ExecutionContext
)
from app.database import get_db
from app.config import VECTOR_DB_PATH

tool_info = ToolInfo(
    name="knowledge.stats",
    display_name="Knowledge Base Stats",
    description="Retrieve dynamic statistics about the registered knowledge base files and indexed chunks.",
    category="knowledge",
    permissions=["admin"],
    parameters=[],
    dangerous=False,
    read_only=True,
    supports_dry_run=False,
    estimated_runtime_ms=200
)

@register_tool(tool_info)
async def get_knowledge_stats(context: ExecutionContext) -> ToolResult:
    metrics = {}
    recommendations = []
    
    # 1. MongoDB Document Count
    db = get_db()
    if db is not None:
        total_docs = db["knowledge_base"].count_documents({})
        active_docs = db["knowledge_base"].count_documents({"is_active": True})
        failed_docs = db["knowledge_base"].count_documents({"status": "Failed"})
        completed_docs = db["knowledge_base"].count_documents({"status": "Completed"})
        
        metrics["total_documents"] = total_docs
        metrics["active_documents"] = active_docs
        metrics["failed_documents"] = failed_docs
        metrics["completed_documents"] = completed_docs
    else:
        metrics["total_documents"] = 0
        metrics["active_documents"] = 0
        metrics["failed_documents"] = 0
        metrics["completed_documents"] = 0
        
    # 2. FAISS Index Count
    vector_count = 0
    try:
        if os.path.exists(VECTOR_DB_PATH):
            index = faiss.read_index(VECTOR_DB_PATH)
            vector_count = index.ntotal
    except Exception as e:
        recommendations.append(f"Failed to read FAISS index from disk: {e}")
        
    metrics["vector_count"] = vector_count
    
    # Validation mismatch warning
    # Standard check: completed document chunks should equal vector counts
    mismatch = False
    if db is not None:
        chunk_count = sum(doc.get("chunk_count", 0) or 0 for doc in db["knowledge_base"].find({"is_active": True}, {"chunk_count": 1}))
        metrics["chunk_count"] = chunk_count
        if chunk_count != vector_count:
            mismatch = True
            metrics["alignment_warning"] = True
            recommendations.append(f"FAISS index count ({vector_count}) does not match MongoDB chunks count ({chunk_count}). Reindexing recommended.")
            
    summary = (
        "Knowledge base is healthy and aligned." if not mismatch
        else "Knowledge base exhibits indexing mismatches."
    )
    status = ToolResultStatus.SUCCESS if not mismatch else ToolResultStatus.WARNING
    
    return ToolResult(
        status=status,
        summary=summary,
        data=metrics,
        metrics=metrics,
        recommendations=recommendations,
        next_actions=["Rebuild FAISS index" if mismatch else "None"]
    )
