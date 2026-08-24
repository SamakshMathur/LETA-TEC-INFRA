# Chronological Changelog - LETATEC

## [2.5.2] - 2026-07-20
### Refactored
*   **TypeScript Response Interfaces**: Introduced `ServiceStatus` and `HealthInfo` strict type interfaces inside [AdminUploadPortal.tsx](file:///Users/adityasingh/Desktop/GST-RAG-/frontend/src/pages/AdminUploadPortal.tsx#L74) to prevent raw object rendering bugs.
*   **Normalized Telemetry Mapping**: Extracted backend service checks into a single local `services` dictionary object in [AdminUploadPortal.tsx](file:///Users/adityasingh/Desktop/GST-RAG-/frontend/src/pages/AdminUploadPortal.tsx#L488) to isolate JSX components from API schema changes.
*   **JWT Logger Verbosity**: Lowered JWT verification logging severity from `logger.info` to `logger.debug` in [security.py](file:///Users/adityasingh/Desktop/GST-RAG-/rag-backend/app/security.py#L122) to prevent production log flooding.

---

## [2.5.1] - 2026-07-20
### Fixed
*   **React Child Object Rendering**: Resolved UI crash (`Objects are not valid as a React child`) inside notification telemetry panel within [AdminUploadPortal.tsx](file:///Users/adityasingh/Desktop/GST-RAG-/frontend/src/pages/AdminUploadPortal.tsx#L578-L604) by explicitly extracting `.status` properties from Axios response data objects.
*   **Security Log Leak Sanitization**: Prevented logging of raw JSON Web Tokens in terminal outputs inside [security.py](file:///Users/adityasingh/Desktop/GST-RAG-/rag-backend/app/security.py#L122) by changing token logs to generic info statements.

---

## [2.5.0] - 2026-07-18
### Added
*   **Mission Control Architecture Hardening**: Promoted the orchestration engine to production-grade architecture (Sprint 1.1 Hardening):
    *   `plan_validator.py`: Created a plan validation layer implementing topological cycle checks, duplicate ID blockades, and parameter integrity scans prior to execution.
    *   `Topological Sorting Execution Levels`: Resolved dependency steps into sorted stages, preparing the runtime for parallel tool invocations.
    *   `Lifecycle Hooks`: Added optional `before_execute`, `after_execute`, and `on_error` callbacks directly integrated with tool handlers.
    *   `ToolCategory Enums`: Migrated free-text tool categories to a strict `ToolCategory` enum validator.
    *   `Registry Self-Validation & Fast-Fail`: Added registry startup scans validating duplicate tools, capabilities, parameter schemas, and API/framework compatibility.
    *   `Execution Policy & Timeouts`: Configured custom execution policies (retries, timeouts) running steps inside `asyncio.wait_for` loops.
    *   `Unknown Intent Suggestion Engine`: Modified general intent routing to search registered tools and offer closest suggested commands.
    *   `Trace Propagation & Observability Health`: Injected correlation trace headers (`trace_id`, `request_id`, `execution_id`) across events and observations, mapping performance telemetry and denial reports.
*   **Hardening Test Suite**: Expanded `test_mission_control.py` to cover topological sorting, cycle detection, dry-runs, session TTL sweeps, and metrics validation (all 15 tests pass).

---

## [2.4.0] - 2026-07-18
### Added
*   **Mission Control Core Engine**: Setup the fundamental operating system layer under `app/mission_control/`:
    *   `schemas.py`: Defined pydantic execution graphs (`depends_on`), rich metadata, observation severity levels, and standardized tool result formats.
    *   `registry.py`: Extensible tool registry supporting auto-discovery, decorators, and system reloads.
    *   `intent_classifier.py` & `planner.py`: Split intent recognition routing from plan step builders.
    *   `permissions.py`: Integrated RBAC authorization hierarchies.
    *   `memory.py` & `executor.py`: Managed session state storage and event lifecycles.
    *   `controller.py`: Exposed the unified execution orchestrator API.
*   **Reference Tools**: Implemented `system.health` (platform connections, disk space, and virtualization statistics) and `knowledge.stats` (database record and chunk counts alignment checks) as reference implementations.
*   **Mission Control Tests**: Deployed `test_mission_control.py` validating intent classification, planner steps, permissions clearance, execution engine events, and E2E controller workflows.

---

## [2.3.0] - 2026-07-18
### Added
*   **Scanned PDF OCR Fallback**: Integrated automatic Tesseract OCR text extraction fallback inside `app/pipeline/knowledge_ingest.py` and `app/pipeline/incremental_ingest.py` when standard PDF text extraction yields little to no content.
*   **Raised Body Size Limit**: Configured `MAX_BODY_BYTES` to 20MB in request size limit middleware inside `app/api/app.py` to support larger legal doc uploads.
*   **E2E Validation Suite**: Created `test_e2e_ingestion.py` verifying full PDF upload, text extraction, chunking, embedding, indexing, MongoDB audit logging, and RAG retrieval synchronizations.

### Refactored
*   **Unified Axios Telemetry**: Refactored native `fetch()` calls in the Admin Console dashboard (`AdminUploadPortal.tsx`) to `AXIOS_INSTANCE`, routing requests through standard client interceptors for silent token refreshes on 401 expiration.
*   **Gated Polling Hooks**: Modified `useKnowledgePolling` hook to accept and check `isLoggedIn`, stopping polling triggers when the user is unauthenticated.

---

## [2.2.0] - 2026-07-18
### Added
*   **Documentation Preservation Constitution**: Enforced append-only policies preserving history, changelogs, and previous ADRs.
*   **Incremental Documentation Update Policy**: Added requirements to prevent massive regenerative rewrites of markdown documentation.
*   **Documentation-Implementation Consistency Rule**: Embedded consistency checks matching code schemas, endpoints, and configs directly to documentation files.
*   **History Archives**: Initialized the `docs/history/` directory.

---

## [2.1.0] - 2026-07-15
### Added
*   **Production Telemetry Dashboard**: Converted all UI stats cards to display dynamic `dataSource` badges.
*   **Dynamic Health Indicators**: Replaced static Notification Center connection items with live API connection checks.
*   **Polling Refresh**: Implemented automatic refresh hooks reloading control center metrics when background ingestion jobs complete.
*   **Resource Bar Calculations**: Removed hardcoded percentage styles from Billing Plan bars, calculating values dynamically from MongoDB usage metrics.

---

## [2.0.0] - 2026-07-15
### Added
*   **Engineering Constitution v2.0**: Standardized AI session lifecycle (Plan &rarr; Read &rarr; Understand &rarr; Implement &rarr; Verify &rarr; Test &rarr; Document &rarr; Memory &rarr; Changelog &rarr; Journal &rarr; Self Review &rarr; Final Report).
*   **Mandatory Self Review**: Embedded structured checklists checking for mocks, duplicates, dead code, and documentation alignment.
*   **Mission Control Intent Planner Architecture**: Documented intent-driven planning pipelines, routing classifiers, dynamic tool selections, and multi-service data correlation targets (MongoDB, Redis, FAISS, Ingest Jobs, Logs).
*   **Repository Cleanup Policy**: Enforced mandatory surrounding code cleanup on file updates.

---

## [1.5.0] - 2026-07-04
### Refactored
*   **Centralized RBAC**: Replaced strict role checks with unified constants and sets (`ROLE_USER`, `ROLE_ADMIN`, `ROLE_SUPER_ADMIN`, `ADMIN_ROLES`).
*   **Security hardening**: Restricted `/users/{contact}/toggle-admin` and `/team/role` to `super_admin` only, preventing self-modifications and `super_admin` demotions.
*   **Telemetry Connection**: Replaced all mock/placeholder statistics inside `control_center.py` with live MongoDB database queries and FAISS index checks.
*   **Redis Caching**: Resolved float32 JSON serialization crashes by adding recursive converting helpers.

---

## [1.0.0] - 2026-07-02
### Added
*   Initial release of Admin upload dashboard containing Ingestion progress queues and version promoters.
