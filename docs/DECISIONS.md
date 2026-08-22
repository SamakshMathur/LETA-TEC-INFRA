# Architecture Decision Records (DECISIONS.md)

## ADR 1: Stateful MongoDB Role Lookup
*   **Decision #**: 01
*   **Status**: Accepted
*   **Context**: JWT access tokens are signed on login, but user roles must adapt instantly to admin role updates or suspensions.
*   **Options Considered**: 
    1.  Embed roles in JWT claims (requires client relogin on role updates).
    2.  Query MongoDB for role lookup on every incoming request.
*   **Decision**: Option 2.
*   **Reasoning**: Preserves immediate admin privileges revocation and suspension enforcement.
*   **Trade-offs**: Adds a minor database read query overhead.
*   **Consequences**: Increases system reactivity and security compliance.

---

## ADR 2: Local FAISS Index FlatIP for Semantic Caching
*   **Decision #**: 02
*   **Status**: Accepted
*   **Context**: Fast RAG semantic searches are required to reduce OpenAI/Anthropic token generation overhead.
*   **Options Considered**:
    1.  Direct database keyword search.
    2.  Redis-based vector lookups.
    3.  In-memory FAISS flat inner product (FlatIP) cache index.
*   **Decision**: Option 3 (with option 2 as persistent sync store).
*   **Reasoning**: FlatIP is exceptionally fast for vector dimensions <= 1024.
*   **Trade-offs**: Higher RAM load on the API container.
*   **Consequences**: Bypasses full RAG execution for repeated semantic queries in <10ms.
