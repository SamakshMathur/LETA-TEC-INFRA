# Database Schema Specification (DATABASE_SCHEMA.md)

## 1. `users` Collection
*   **Purpose**: Stores authentication credentials, active roles, and verified state.
*   **Indexes**: Unique index on `username`, index on `phone`, index on `email`.
*   **Validation Rules**: `role` must be in `["user", "admin", "super_admin"]`.
*   **Update Flow**: Modifications to administrative roles are permitted only by `super_admin` callers.
*   **Document Example**:
    ```json
    {
      "username": "user_983653",
      "full_name": "Aditya singh",
      "phone": "8619983653",
      "email": "counsel@letatec.com",
      "role": "super_admin",
      "verified": true,
      "created_at": "2026-05-05T16:48:19.703Z",
      "last_login": "2026-07-15T18:00:00.000Z"
    }
    ```

## 2. `knowledge_base` Collection
*   **Purpose**: Manages documents loaded into the hybrid RAG system.
*   **Indexes**: Index on `document_id`, index on `filename`, index on `category`.
*   **Validation Rules**: `status` must be in `["Completed", "Failed", "Archived"]`.
*   **Lifecycle**: Active documents (`is_active: true`) are included in vector queries. Archived documents (`is_active: false`) are ignored.
*   **Document Example**:
    ```json
    {
      "document_id": "doc_8f2a1b9c",
      "filename": "CGST_Circular_201_2026.pdf",
      "category": "circulars",
      "chunk_count": 18,
      "version": 1,
      "status": "Completed",
      "is_active": true,
      "uploaded_at": "2026-07-04T12:00:00.000Z"
    }
    ```

## 3. `ai_query_analytics` Collection
*   **Purpose**: Logs queries, execution latency, and token parameters.
*   **Document Example**:
    ```json
    {
      "query_id": "q_4b3e8c9d",
      "timestamp": "2026-07-04T12:05:00.000Z",
      "query": "CGST section 17(5) blocked credit rules",
      "total_latency_ms": 380.5,
      "cache_hit": false,
      "success": true
    }
    ```
