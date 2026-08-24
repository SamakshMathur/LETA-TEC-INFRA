# LetaTec Development Roadmap (ROADMAP.md)

## 1. Completed
*   **Engineering Governance v2.0**: Deployed a complete documentation framework, standard session lifecycles, and self-review checklists.
*   **Centralized RBAC**: Integrated unified role constants, check helpers, and secured administration boundaries.
*   **Production Telemetry**: Connected all dashboard metrics to live MongoDB, Redis, and FAISS index checks, resolving NumPy float32 serialization errors.

## 2. Current (Milestone 5)
*   **Mission Control Intent-based Orchestrator**: Shift strategic focus toward implementing the Admin AI intent classification, planning layer, dynamic tool executing bindings, and database telemetry correlators.

## 3. Next
*   **Multi-tenant Organization Scopes**: Isolation layers ensuring organization memberships are bound strictly to private database documents.

## 4. Future
*   **Hierarchical Vector Search (HNSW)**: Transitioning from FlatIP to HNSW indices to maintain speed under heavy document catalogs.
*   **System Event Bus (Structured System Events)**: Build a structured event stream (e.g. `DocumentUploaded`, `DocumentIndexed`, `RedisDisconnected`, `MongoRecovered`, `UserLogin`, `RoleChanged`, `CacheCleared`) that feeds audit logs, dashboard notifications, real-time WebSockets, and Mission Control planning loops.

## 5. Research
*   **Retrieval Evaluation Frameworks (Ragas)**: Quantitative scoring of RAG outputs on live circular additions.

## 6. Technical Debt Backlog
*   **Audit Logger Isolation**: Local logger is file/syslog backed; needs a unified async database storage adapter.
*   **Local FAISS Sync Limits**: Multi-process worker threads must reload index files on disk whenever updates occur to keep queries synchronized.
