# Security & Cryptographic Boundaries (SECURITY.md)

## 1. Secrets Management
*   JWT signing keys are loaded from environmental `SECRET_KEY` variables.
*   Master admin credentials rely on `ADMIN_MASTER_SECRET` check loops.

## 2. Ingestion Conflict Verification
*   We check file uniqueness at the client and database boundary by computing SHA-256 hashes of PDF buffers before saving:
    ```javascript
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    ```

## 3. Strict Audit Trails
*   All administrative alterations (suspending users, modifying roles, creating webhooks) write audit trails to `knowledge_audit_logs` including actor identity, target, and transaction outcome.
