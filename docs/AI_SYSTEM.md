# AI System Architecture & RAG Pipeline (AI_SYSTEM.md)

## 1. Retrieval-Augmented Generation (RAG) Architecture
LETATEC employs a dual-channel hybrid retriever combining dense vector representations and lexical keywords.

```
Query
  │
  ├─► Dense Embedding Channel (BAAI/bge-large-en-v1.5) ─► FAISS Index Lookup (FlatIP) ──┐
  │                                                                                      ├─► Hybrid Merger & MMR Reranker ─► LLM (Claude)
  └─► Lexical Channel (BM25 Engine) ───────────────────► Statutory Keyword Search ───────┘
```

## 2. Ingestion & Embedding Pipeline
*   **Parser & Segmenter**: Uploaded documents are parsed based on layout boundaries. Content is broken into semantic chunks of **1000 characters** with an overlap of **200 characters**.
*   **Embedding Model**: We use **BAAI/bge-large-en-v1.5** loaded locally, mapping chunks into **1024-dimensional dense vectors**.
*   **Vector Storage**: Indexing is handled by a local **FAISS Index** utilizing **IndexFlatIP** (Inner Product) to calculate cosine similarities.

## 3. Caching Hierarchy
*   **Layer 1 (Exact Hash)**: SHA-256 hash of the normalized query is checked first. Backed by **Redis** (primary) with local **DiskCache** as fallback.
*   **Layer 2 (Semantic Cache)**: Cosine similarity of embedding vectors checked against local FAISS cache records. Served only if similarity score is **>= 0.92**.
*   **Layer 3 (Context Control)**: Native Anthropic API cache controls to optimize token counts on repeated system prompts.

## 4. Prompt Engineering & Routing
*   **Complexity Gate**: Queries are calculated for syntactic complexity:
    *   *Complexity < 0.20*: Routed to `claude-haiku-4-5-20251001` (Utility Model).
    *   *Complexity >= 0.20*: Routed to `claude-sonnet-4-6` (Main Model).
*   **Thinking Gate**: Sonnet's extended-thinking capabilities are toggled ON only when complexity score is **>= 0.65** (e.g. litigation drafts).

---

## 5. Mission Control Orchestrator Architecture
The Admin AI assistant is designed to evolve beyond basic keyword matching to an intent-driven operations console.

```
User Query / Command
        │
        ▼
  Intent Detection
        │
        ▼
Intent Classification
        │
        ▼
    Planner
        │
        ▼
  Tool Selection
        │
        ▼
   Tool Execution (Backend Services: MongoDB, Redis, FAISS, Ingestion Jobs, Logs)
        │
        ▼
Evidence Collection
        │
        ▼
 Reasoning Engine
        │
        ▼
Response Generation (Explains "WHY" a state exists using data correlations)
        │
        ▼
  Audit Logging (Persists command and status outcomes)
```

### Data Correlation Targets
The Reasoning Engine dynamically retrieves and correlates metrics from:
*   **MongoDB**: Document states, audit history log entries.
*   **Redis**: Key-value cache hits and namespace sizes.
*   **FAISS**: Indexed vector segment counts (`idx.ntotal`).
*   **Analytics**: Average system latencies and monthly queries.
*   **Jobs**: Statuses of background document pipeline tasks.
*   **Configuration**: Model sizes, chunking parameters, and LLM temperature overrides.
*   **Audit Logs**: Privileged action metadata.
