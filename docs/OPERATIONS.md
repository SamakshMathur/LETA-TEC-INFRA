# Operations & Maintenance Guide (OPERATIONS.md)

## 1. Database Backups
All core collections (`users`, `knowledge_base`, `ai_query_analytics`, `knowledge_audit_logs`) must be backed up daily:
```bash
# Export all MongoDB databases to a local archive
mongodump --uri="mongodb://localhost:27017/leta" --archive=/var/backups/leta_daily_$(date +%F).archive --gzip
```

## 2. Telemetry & Monitoring
*   **System Diagnostics**: FastAPI exposes CPU/RAM/Disk states via `/api/admin/control-center/health`.
*   **Microservice Health Checks**: Periodically validates local FAISS path files and Mongo connectivity.
*   **Structured Logs**: Standard out logs are captured in JSON format:
    `{"timestamp": "...", "level": "...", "logger": "...", "message": "..."}`

## 3. Container Recovery Procedures
If the backend process terminates or becomes unresponsive:
1.  **Readiness Probe Failures**: Uvicorn will exit. System monitoring (e.g. systemd or Docker container restart policies) must restart the container.
2.  **State Recovery**: Upon boot, the server loads the static FAISS index from `vectordb/index.faiss` and attempts to connect to MongoDB. If MongoDB is unavailable, startup fails early.
3.  **Cache Reconstruction**: The local FAISS semantic cache index automatically rebuilds from the Redis hash map on the first query hit.
