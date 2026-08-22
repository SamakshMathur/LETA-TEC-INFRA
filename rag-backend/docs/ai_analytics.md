# AI Query Analytics System Documentation

## Overview
The AI Query Analytics system is a production-grade query instrumentation and metrics gathering infrastructure designed for the LETA Backend. It logs detailed telemetry data for every AI-driven request (e.g. STATUTE searches, legal text synthetically generated or routed via Claude/OpenAI) to MongoDB without blocking execution or introducing user-facing latency.

---

## Architecture & Lifecycle
For each request context, the lifecycle operates asynchronously and thread-safely:
1. **Initialize Analytics Context**: A ContextVar (`ai_log_context`) is initialized inside `app/config.py` at the entry-points (`/api/ask`, `/api/ask-sync`, and `/api/ask-with-file`). The initial query characteristics, JWT details (user ID and username), endpoint identifier, client IP, and query ID are stored.
2. **Retriever Timings**: The `search()` method in `retriever.py` captures Layer 1-3 broad searches (`retrieval_time_ms`), FlashRank/MMR deduplication processes (`reranker_time_ms`), and retrieved chunk statistics.
3. **Synthesizer Metrics**: The model chosen (routed via Sonnet or Haiku), draft type settings, and estimated prompt/completion tokens (using character-based fallback approximations) are tracked during LLM responses.
4. **Execution & Committing**: Once streaming concludes or response JSON is serialized, `commit_ai_log` is called exactly once. On failure, the log is persisted with `success=False` and the associated `error_message`. Structured JSON logs are printed to console output streams concurrently.

---

## MongoDB Schema Details (`ai_query_analytics`)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `query_id` | String | Unique ID mapped to the API transaction. |
| `timestamp` | Date | Timestamp (UTC) indicating when the query started. |
| `user_id` | String | Unique user ID extracted from JWT payload. |
| `username` | String | User's username payload extracted from JWT. |
| `endpoint` | String | API endpoint called (`/api/ask`, `/api/ask-sync`, etc.). |
| `query` | String | User query input text. |
| `query_length` | Integer | Character length of the user query. |
| `draft_type` | String | Type of draft matched ("draft" or `None`). |
| `model_used` | String | LLM Model Name routed to (e.g. `claude-3-5-sonnet-20241022`). |
| `retrieved_chunks` | Integer | Total count of retrieved chunks returned from the retriever. |
| `citations_count` | Integer | Total count of uniquely formatted source citations. |
| `retrieval_time_ms` | Float | Millisecond duration of Layer 1 & 2 semantic retrievals. |
| `reranker_time_ms` | Float | Millisecond duration of FlashRank reranking & MMR. |
| `generation_time_ms` | Float | Millisecond duration of synthetic generation streaming loop. |
| `total_latency_ms` | Float | Total millisecond latency of the request context. |
| `estimated_prompt_tokens` | Integer | Estimated token footprint of prompt context (characters / 4). |
| `estimated_completion_tokens` | Integer | Estimated token footprint of generated responses (characters / 4). |
| `response_length` | Integer | Character length of generated content. |
| `cache_hit` | Boolean | True if served from semantic memory caches directly. |
| `success` | Boolean | Execution status flag. |
| `http_status` | Integer | HTTP Status Code returned to the client. |
| `error_message` | String | Stack trace excerpt or exception string if failed. |
| `session_id` | String | Session identifier. |
| `request_id` | String | Request identifier matching local UUID. |
| `client_ip` | String | Originating client host IP address. |

---

## Token Estimation Logic
To avoid blocking request processing and maintain high throughput, prompt and response tokens are approximated:
- `estimated_prompt_tokens` = `(len(system_prompt) + len(question)) // 4`
- `estimated_completion_tokens` = `len(full_answer) // 4`

---

## MongoDB Indexes
Indexes are initialized on application startup within `app/database.py`:
- **Single Field Indexes**:
  - `timestamp` (DESCENDING)
  - `user_id` (ASCENDING)
  - `draft_type` (ASCENDING)
  - `model_used` (ASCENDING)
  - `success` (ASCENDING)
  - `query_id` (ASCENDING, UNIQUE)
- **Compound Production Indexes**:
  - `user_id` + `timestamp`
  - `success` + `timestamp`
  - `draft_type` + `timestamp`
  - `model_used` + `timestamp`
  - `cache_hit` + `timestamp`

---

## Structured Log Example
```json
{"query_id": "6ea4d23e", "user": "test_user", "latency_ms": 3280, "retrieval_ms": 420, "generation_ms": 2860, "tokens": 1284, "cache_hit": false, "success": true}
```

---

## Example Queries

### Latest Requests
```javascript
db.ai_query_analytics.find().sort({timestamp: -1})
```

### Most Active Users
```javascript
db.ai_query_analytics.aggregate([
  { $group: { _id: "$user_id", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])
```

### Average Latency
```javascript
db.ai_query_analytics.aggregate([
  { $group: { _id: null, avgLatency: { $avg: "$total_latency_ms" } } }
])
```
