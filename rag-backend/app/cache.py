"""
4-Layer Query Cache
===================
Layer 1 — Exact hash cache  : SHA-256(normalized_query) → answer  (<5ms)
Layer 2 — Semantic cache    : embed(query) → cosine search in Redis (<50ms)
Layer 3 — Anthropic prompt  : handled in synthesizer.py via cache_control
Layer 4 — Full RAG pipeline : fallback, result stored back into L1+L2

Accuracy guarantee:
  - Cached answers only served when similarity >= CACHE_SIMILARITY_THRESHOLD
  - Answers only stored when confidence >= CACHE_MIN_CONFIDENCE
  - Legal content TTL = 48h (GST/tax rules change; stale answers are dangerous)
"""

import hashlib
import json
import logging
import re
import struct
import threading
import time
from typing import Optional

try:
    import faiss
except ImportError:
    faiss = None  # type: ignore  # CI env; only fails if SemanticCache is instantiated
import numpy as np

from app.config import (
    REDIS_URL,
    CACHE_SIMILARITY_THRESHOLD,
    CACHE_MIN_CONFIDENCE,
    CACHE_TTL_SECONDS,
    VECTOR_DIM,
    PROMPT_VERSION,
)

logger = logging.getLogger(__name__)

# ── Redis client (lazy, optional — app works without Redis) ──────────────────

_redis_client = None
_redis_failed_until: float = 0.0  # circuit-breaker timestamp

# ── DiskCache fallback (used when Redis is unavailable) ──────────────────────
# Works with the local filesystem — ephemeral per container session but still
# saves repeated calls within the same deployment (team asking the same query).
_disk_cache = None

def _get_disk_cache():
    global _disk_cache
    if _disk_cache is not None:
        return _disk_cache
    try:
        import diskcache
        _disk_cache = diskcache.Cache(".diskcache_v5")
        logger.info("DiskCache fallback active (Redis unavailable)")
    except Exception as e:
        logger.warning(f"DiskCache also unavailable: {e}")
        _disk_cache = None
    return _disk_cache


def _get_redis():
    """Returns a connected Redis client, or None if Redis is unavailable.

    Circuit-breaker: after a connection failure, waits 60 s before retrying
    so the 2-second socket_connect_timeout is not paid on every call within
    the same request (would add ~16 s when Redis is down).
    """
    global _redis_client, _redis_failed_until
    if _redis_client is not None:
        return _redis_client
    if time.monotonic() < _redis_failed_until:
        return None
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=False, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        logger.info(f"Redis connected: {REDIS_URL}")
    except Exception as e:
        logger.warning(f"Redis unavailable — falling back to DiskCache: {e}")
        _redis_client = None
        _redis_failed_until = time.monotonic() + 60.0
    return _redis_client


# ── Key helpers ──────────────────────────────────────────────────────────────

def _exact_key(query: str, provider: Optional[str] = None, model: Optional[str] = None) -> str:
    normalized = " ".join(query.lower().strip().split())
    prov_str = f":{provider.lower()}" if provider else ""
    mod_str = f":{model.lower()}" if model else ""
    digest_input = f"{normalized}{prov_str}{mod_str}"
    digest = hashlib.sha256(digest_input.encode()).hexdigest()
    return f"leta:{PROMPT_VERSION}:exact:{digest}"


def _embedding_key(query: str) -> str:
    digest = hashlib.sha256(query.lower().strip().encode()).hexdigest()
    return f"leta:{PROMPT_VERSION}:emb:{digest}"


def _semantic_index_key() -> str:
    return f"leta:{PROMPT_VERSION}:semantic:index"


# ── Vector serialization (compact binary, no extra deps) ────────────────────

def _vec_to_bytes(vec: np.ndarray) -> bytes:
    arr = vec.astype(np.float32).flatten()
    return struct.pack(f"{len(arr)}f", *arr)


def _bytes_to_vec(data: bytes) -> np.ndarray:
    n = len(data) // 4
    return np.array(struct.unpack(f"{n}f", data), dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _sanitize_json_types(obj):
    """Recursively converts NumPy numeric types and NaNs/Infs to standard JSON-compatible Python types."""
    if isinstance(obj, dict):
        return {k: _sanitize_json_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_json_types(x) for x in obj]
    elif isinstance(obj, (np.float32, np.float64)):
        val = float(obj)
        return 0.0 if np.isnan(val) or np.isinf(val) else val
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, float):
        return 0.0 if np.isnan(obj) or np.isinf(obj) else obj
    elif hasattr(obj, "item") and callable(getattr(obj, "item")):
        return obj.item()
    return obj


def get_exact(query: str, provider: str = None, model: str = None):
    key = _exact_key(query, provider=provider, model=model)

    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            t_start = time.monotonic()
            data = r.get(key)
            latency = (time.monotonic() - t_start) * 1000.0
            if data:
                payload = json.loads(data)
                logger.info(f"CACHE redis_hit | latency_ms={latency:.2f} | q={query[:60]}")
                return (payload["answer"], payload.get("sources", []))
            else:
                logger.info(f"CACHE redis_miss | latency_ms={latency:.2f} | q={query[:60]}")
                # Healthy Redis miss — do NOT fall back to DiskCache
                return None
        except Exception as e:
            logger.warning(f"CACHE redis_error during get: {e}")

    # Fallback to DiskCache ONLY when Redis is unavailable or errors
    dc = _get_disk_cache()
    if dc is not None:
        try:
            t_start = time.monotonic()
            payload = dc.get(key)
            latency = (time.monotonic() - t_start) * 1000.0
            if payload:
                logger.info(f"CACHE disk_hit | latency_ms={latency:.2f} | q={query[:60]}")
                return (payload["answer"], payload.get("sources", []))
            else:
                logger.info(f"CACHE fallback | latency_ms={latency:.2f} | q={query[:60]}")
        except Exception as e:
            logger.warning(f"CACHE disk_error: {e}")
    return None


def set_exact(query: str, answer: str, confidence: float, sources: list = None, provider: str = None, model: str = None) -> None:
    if confidence < CACHE_MIN_CONFIDENCE:
        logger.debug(f"Cache L1 SKIP (low confidence {confidence:.2f}) | q={query[:60]}")
        return
    key = _exact_key(query, provider=provider, model=model)
    payload = _sanitize_json_types({"answer": answer, "confidence": confidence, "sources": sources or [], "ts": time.time(), "provider": provider, "model": model})

    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            t_start = time.monotonic()
            r.setex(key, CACHE_TTL_SECONDS, json.dumps(payload).encode())
            latency = (time.monotonic() - t_start) * 1000.0
            logger.info(f"CACHE redis_set | latency_ms={latency:.2f} | q={query[:60]}")
            return
        except Exception as e:
            logger.warning(f"CACHE redis_error during set: {e}")

    # Fallback to DiskCache ONLY when Redis is unavailable or errors
    dc = _get_disk_cache()
    if dc is not None:
        try:
            t_start = time.monotonic()
            dc.set(key, payload, expire=CACHE_TTL_SECONDS)
            latency = (time.monotonic() - t_start) * 1000.0
            logger.info(f"CACHE disk_set | latency_ms={latency:.2f} | q={query[:60]}")
        except Exception as e:
            logger.warning(f"CACHE disk_set_error: {e}")


# ── Embedding Cache (query text → embedding vector) ─────────────────────────

def get_cached_embedding(query: str) -> Optional[np.ndarray]:
    r = _get_redis()
    if r is None:
        return None
    try:
        data = r.get(_embedding_key(query))
        if data:
            vec = _bytes_to_vec(data)
            if len(vec) == VECTOR_DIM:
                return vec
    except Exception as e:
        logger.warning(f"Embedding cache get error: {e}")
    return None


def set_cached_embedding(query: str, vec: np.ndarray) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        # Embedding TTL = 7 days (vectors don't become stale)
        r.setex(_embedding_key(query), 7 * 24 * 3600, _vec_to_bytes(vec))
    except Exception as e:
        logger.warning(f"Embedding cache set error: {e}")


# ── Layer 2: Semantic Cache ──────────────────────────────────────────────────
# We use a 2-Tiered Semantic Cache:
# Tier 1: Local FAISS Index (In-memory, O(log N) search)
# Tier 2: Redis Hash Index (Persistent storage, O(N) but used for sync)

MAX_SEMANTIC_ENTRIES = 2000  # keep memory bounded
_faiss_index = None
_faiss_metadata = []         # Stores [answer, query_text, confidence]
_faiss_lock = threading.Lock()

def _refresh_faiss_index():
    """Syncs the local FAISS index from Redis data."""
    global _faiss_index, _faiss_metadata
    r = _get_redis()
    if r is None:
        return

    try:
        index_key = _semantic_index_key()
        all_entries = r.hgetall(index_key)
        if not all_entries:
            return

        vectors = []
        metadata = []
        for _, raw in all_entries.items():
            try:
                entry = json.loads(raw)
                vec = _bytes_to_vec(bytes.fromhex(entry["vec_hex"]))
                vectors.append(vec)
                metadata.append({
                    "answer": entry["answer"],
                    "query_text": entry.get("query_text", ""), # for guard check
                    "confidence": entry["confidence"]
                })
            except Exception:
                continue

        if vectors:
            with _faiss_lock:
                # Use IndexFlatIP for Cosine Similarity (vectors are normalized in Retriever)
                dim = len(vectors[0])
                new_index = faiss.IndexFlatIP(dim)
                new_index.add(np.array(vectors).astype('float32'))
                _faiss_index = new_index
                _faiss_metadata = metadata
                logger.info(f"FAISS Cache Index rebuilt: {len(metadata)} entries")
    except Exception as e:
        logger.error(f"Failed to refresh FAISS cache: {e}")

def verify_cache_hit(query: str, cached_metadata: dict, provider: str = None, model: str = None) -> bool:
    """
    Accuracy Guard: Ensures the cached answer is truly relevant.
    Checks for high-priority legal keyword overlap and provider/model match (Fix 14).
    """
    if provider and cached_metadata.get("provider") != provider:
        return False
    if model and cached_metadata.get("model") != model:
        return False

    q_lower = query.lower()
    # Extract sections like "Sec 17", "Section 17(5)"
    q_sections = set(re.findall(r'\bsec(?:tion)?\s*\d+', q_lower))

    if not q_sections:
        return True # General query, rely on embedding similarity

    ans_text = (cached_metadata.get("answer", "") + " " + cached_metadata.get("query_text", "")).lower()

    # If the query specifies a section, the answer MUST contain it
    for sec in q_sections:
        # Normalize: "Sec 17" -> "17"
        sec_num = re.search(r'\d+', sec).group()
        if sec_num not in ans_text:
            logger.warning(f"Accuracy Guard REJECTED cache hit: Query mentions Sec {sec_num} but answer does not.")
            return False

    return True


def get_semantic(query_vec: np.ndarray, query_text: str = "", provider: str = None, model: str = None):
    """
    Returns (answer, sources) tuple if cosine similarity >= threshold and passes accuracy guard.
    """
    global _faiss_index
    if _faiss_index is None:
        _refresh_faiss_index()

    if _faiss_index is None:
        return None

    try:
        query_vec_np = np.array([query_vec]).astype('float32')
        D, I = _faiss_index.search(query_vec_np, 1)

        if len(I[0]) > 0:
            idx = I[0][0]
            similarity = D[0][0]

            if idx != -1 and similarity >= CACHE_SIMILARITY_THRESHOLD:
                meta = _faiss_metadata[idx]

                if not verify_cache_hit(query_text, meta, provider=provider, model=model):
                    return None

                logger.info(f"Cache L2 HIT (FAISS) | similarity={similarity:.3f}")
                return (meta["answer"], meta.get("sources", []))

    except Exception as e:
        logger.warning(f"Cache L2 (FAISS) search error: {e}")
        return _get_semantic_slow(query_vec, provider=provider, model=model)
    return None

def _get_semantic_slow(query_vec: np.ndarray, provider: str = None, model: str = None):
    """Legacy slow scan as fallback."""
    r = _get_redis()
    if r is None: return None
    try:
        index_key = _semantic_index_key()
        all_entries = r.hgetall(index_key)
        for _, raw in all_entries.items():
            entry = json.loads(raw)
            if provider and entry.get("provider") != provider:
                continue
            if model and entry.get("model") != model:
                continue
            sim = _cosine_similarity(query_vec, _bytes_to_vec(bytes.fromhex(entry["vec_hex"])))
            if sim >= CACHE_SIMILARITY_THRESHOLD:
                return (entry["answer"], entry.get("sources", []))
    except: pass
    return None


def set_semantic(query_vec: np.ndarray, answer: str, confidence: float, query_text: str = "", sources: list = None, provider: str = None, model: str = None) -> None:
    if confidence < CACHE_MIN_CONFIDENCE:
        return
    r = _get_redis()
    if r is None:
        return
    try:
        index_key = _semantic_index_key()

        current_count = r.hlen(index_key)
        if current_count >= MAX_SEMANTIC_ENTRIES:
            keys_to_delete = list(r.hkeys(index_key))[:MAX_SEMANTIC_ENTRIES // 10]
            if keys_to_delete:
                r.hdel(index_key, *keys_to_delete)

        entry_key = hashlib.sha256(
            (answer[:100] + query_text[:50]).encode()
        ).hexdigest()[:16]

        entry = _sanitize_json_types({
            "vec_hex": _vec_to_bytes(query_vec).hex(),
            "answer": answer,
            "query_text": query_text,
            "confidence": confidence,
            "sources": sources or [],
            "ts": time.time(),
            "provider": provider,
            "model": model,
        })
        r.hset(index_key, entry_key, json.dumps(entry))
        r.expire(index_key, CACHE_TTL_SECONDS)

        with _faiss_lock:
            if _faiss_index is not None:
                _faiss_index.add(np.array([query_vec]).astype('float32'))
                _faiss_metadata.append({
                    "answer": answer,
                    "query_text": query_text,
                    "confidence": confidence,
                    "sources": sources or [],
                    "provider": provider,
                    "model": model,
                })

        logger.debug(f"Cache L2 SET | entries~={current_count + 1}")
    except Exception as e:
        logger.warning(f"Cache L2 set error: {e}")


# ── Combined lookup / store (used by retriever + app.py) ────────────────────

def cache_lookup(query: str, query_vec: Optional[np.ndarray] = None, provider: str = None, model: str = None):
    """
    Check L1 (exact) then L2 (semantic).
    Returns (answer, sources) tuple or None on miss.
    sources is a list of {title, page, url, score} dicts (may be empty list).
    """
    result = get_exact(query, provider=provider, model=model)
    if result:
        return result

    if query_vec is not None:
        result = get_semantic(query_vec, query_text=query, provider=provider, model=model)
        if result:
            return result

    return None


def cache_store(
    query: str,
    query_vec: Optional[np.ndarray],
    answer: str,
    confidence: float,
    sources: list = None,
    provider: str = None,
    model: str = None,
) -> None:
    """Store answer + sources in both L1 (exact) and L2 (semantic) if confidence is sufficient."""
    set_exact(query, answer, confidence, sources=sources or [], provider=provider, model=model)
    if query_vec is not None:
        set_semantic(query_vec, answer, confidence, query_text=query, sources=sources or [], provider=provider, model=model)


# ── Health check ─────────────────────────────────────────────────────────────

def cache_health() -> dict:
    r = _get_redis()
    if r is None:
        return {"status": "unavailable", "url": REDIS_URL}
    try:
        info = r.info("memory")
        semantic_entries = r.hlen(_semantic_index_key())
        return {
            "status": "connected",
            "url": REDIS_URL,
            "used_memory_human": info.get("used_memory_human", "?"),
            "semantic_entries": semantic_entries,
            "similarity_threshold": CACHE_SIMILARITY_THRESHOLD,
            "min_confidence_to_cache": CACHE_MIN_CONFIDENCE,
            "ttl_hours": CACHE_TTL_SECONDS // 3600,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

def close_redis():
    global _redis_client
    if _redis_client is not None:
        logger.info("Closing Redis cache connection pool...")
        try:
            _redis_client.close()
        except Exception as e:
            logger.warning(f"Error closing Redis: {e}")
        _redis_client = None
