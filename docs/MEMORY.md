# LetaTec Working Memory Registry (MEMORY.md)

## 1. Project Specifications
*   **Current Milestone**: Phase 5.2 (Mission Control Hardened Framework).
*   **Current Branch**: `main`
*   **Current Version**: `v2.5.2`
*   **Last Completed Task**: Optimized AdminUploadPortal.tsx by introducing TypeScript response interfaces, normalized telemetry object mapping, and lowered token verification logging to debug level.

---

## 2. Active Telemetry & Target Files
*   **Target Files**:
    *   Mission Control Controller: [controller.py](../rag-backend/app/mission_control/controller.py)
    *   Execution schemas: [schemas.py](../rag-backend/app/mission_control/schemas.py)
    *   Tool Registry: [registry.py](../rag-backend/app/mission_control/registry.py)
    *   Planning loops: [planner.py](../rag-backend/app/mission_control/planner.py)
    *   Reference tools: [health.py](../rag-backend/app/mission_control/tools/health.py), [knowledge.py](../rag-backend/app/mission_control/tools/knowledge.py)
*   **Active Configurations**:
    *   Vite base url: `http://localhost:8000`
    *   MongoDB collections count: 9 collections active.
    *   Orchestration structure: Dependency Graph

---

## 3. Active Risks & Technical Debt
*   **Downstream Anthropic Credit Limits**: Downstream Claude API requests trigger credit balance errors. Requires renewal of Anthropic API keys or replenishing credit limits.
*   **FAISS Index Alignment**: Chunks file counts must align with vectors indexed. Retriever check warnings are logged when mismatch runs occur.

---

## 4. Next Suggested Action
*   **Task**: Begin Sprint 2 (Tool Registry expansions) to migrate all capabilities (reindexing, cache refreshes, webhooks, audit timelines) into registered tools.
