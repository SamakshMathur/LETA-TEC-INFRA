import os
import psutil
from pathlib import Path
from app.mission_control.registry import register_tool
from app.mission_control.schemas import (
    ToolInfo, ToolParameter, ToolResult, ToolResultStatus, ExecutionContext
)
from app.database import get_db

tool_info = ToolInfo(
    name="system.health",
    display_name="System Health Check",
    description="Check system health including Redis, MongoDB, FAISS index, CPU, and Memory usage.",
    category="system",
    permissions=["admin"],
    parameters=[],
    dangerous=False,
    read_only=True,
    supports_dry_run=True,
    estimated_runtime_ms=150
)

@register_tool(tool_info)
async def check_system_health(context: ExecutionContext) -> ToolResult:
    recommendations = []
    status = ToolResultStatus.SUCCESS
    metrics = {}
    
    # 1. MongoDB Status
    mongo_ok = False
    try:
        db = get_db()
        if db is not None:
            # Simple command run
            db.command("ping")
            mongo_ok = True
    except Exception as e:
        recommendations.append("Verify MongoDB connection settings and status.")
        status = ToolResultStatus.ERROR
        
    metrics["mongodb"] = "healthy" if mongo_ok else "unreachable"
    
    # 2. Redis Status
    # Since Redis is optional and might be offline in development:
    redis_ok = False
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        r.ping()
        redis_ok = True
    except Exception:
        recommendations.append("Check Redis server status; local caching fallback active.")
        # Don't fail the whole tool if Redis is offline, just set status to Warning
        if status != ToolResultStatus.ERROR:
            status = ToolResultStatus.WARNING
            
    metrics["redis"] = "healthy" if redis_ok else "offline"
    
    # 3. FAISS Status
    from app.config import VECTOR_DB_PATH
    faiss_path = Path(VECTOR_DB_PATH)
    faiss_ok = faiss_path.exists()
    if not faiss_ok:
        recommendations.append("FAISS index file missing. Trigger rebuilding of citation index.")
        status = ToolResultStatus.ERROR
        
    metrics["faiss_index"] = "present" if faiss_ok else "missing"
    
    # 4. OS System metrics
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    metrics["cpu_utilization_pct"] = cpu
    metrics["ram_utilization_pct"] = ram
    
    if cpu > 80.0:
        recommendations.append("CPU utilization is high. Verify background worker count.")
        if status == ToolResultStatus.SUCCESS:
            status = ToolResultStatus.WARNING
            
    if ram > 85.0:
        recommendations.append("Memory utilization is high. Consider vertical scaling.")
        if status == ToolResultStatus.SUCCESS:
            status = ToolResultStatus.WARNING

    summary = (
        "System is fully operational and healthy." if status == ToolResultStatus.SUCCESS
        else "System is online with warnings." if status == ToolResultStatus.WARNING
        else "System health check failed. Critical services unavailable."
    )
    
    return ToolResult(
        status=status,
        summary=summary,
        data=metrics,
        metrics=metrics,
        recommendations=recommendations,
        next_actions=["Restart Redis" if not redis_ok else "None"]
    )
