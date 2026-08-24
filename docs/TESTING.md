# Comprehensive Testing Protocol (TESTING.md)

## 1. Unit Testing
*   **Focus**: Pure logic functions (e.g. `_sanitize_json_types()`, `verify_cache_hit()`).
*   **Method**: Validate with inputs including numpy float32 arrays, NaNs, infs, and verify they map to clean JSON objects.

## 2. Integration Testing
*   **Focus**: Inter-module pipelines (e.g. Ingestion → Chunking → Embedding).
*   **Method**: Test ingestion scripts on standard test files and confirm chunks are generated and merged successfully.

## 3. End-to-End (E2E) Testing
*   **Focus**: Client-to-server operations flow.
*   **Method**: Walk through login, document uploads, index refreshes, and query chats.

## 4. Load & Performance Testing
*   **Focus**: Retrieval latencies and concurrent request throughput.
*   **Criteria**: Retrieval step must complete in <450ms. Cache hits must return in <5ms.

## 5. Security Testing
*   **Focus**: RBAC boundaries and token verification.
*   **Matrix**:
    *   Missing/Invalid token must return `401`.
    *   User attempting admin routes must return `403`.
    *   Self role modification must return `400`.
    *   Modifying super_admin role must return `400`.
