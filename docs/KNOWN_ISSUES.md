# Technical Debt & Active Limitations (KNOWN_ISSUES.md)

## 1. High Priority

### Local FAISS In-Memory Limits
*   **Description**: FAISS index modifications are merged locally in memory inside each worker process. On high concurrent loads, index updates must propagate to all running uvicorn worker threads.
*   **Impact**: Mismatches between document counts and query results when multiple worker nodes are active.
*   **Temporary Workaround**: Trigger local reload of the FAISS index file on query operations.
*   **Long-Term Resolution**: Transition to an external vector database cluster (e.g. Qdrant or Milvus).

---

## 2. Medium Priority

### Inbound File Size Boundary
*   **Description**: Local server memory buffers raw files up to 5MB before saving. Large PDFs (above 100 pages) may cause temporary CPU spikes during local BGE embedding model calculations.
*   **Impact**: Memory spikes and slower query ingestion latency during concurrent large uploads.
*   **Temporary Workaround**: Restrict file upload boundaries on the client to 5MB.
*   **Long-Term Resolution**: Offload file parsing and embedding to Celery/Redis workers.

---

## 3. Low Priority

### Audit Logger Database Adapter
*   **Description**: Administration events are currently logged locally.
*   **Impact**: Telemetry logs are not aggregated inside MongoDB database records.
*   **Temporary Workaround**: Parse local uvicorn logs.
*   **Long-Term Resolution**: Implement a unified database-backed audit log adapter.
