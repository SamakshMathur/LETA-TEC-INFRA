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

import faiss
import numpy as np

from app.config import (
    REDIS_URL,
    CACHE_SIMILARITY_THRESHOLD,
    CACHE_MIN_CONFIDENCE,
    CACHE_TTL_SECONDS,
    VECTOR_DIM,
)

logger = logging.getLogger(__name__)

# ── Redis client (lazy, optional — app works without Redis) ──────────────────

_redis_client = None

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
    """Returns a connected Redis client, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=False, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        logger.info(f"Redis connected: {REDIS_URL}")
    except Exception as e:
        logger.warning(f"Redis unavailable — falling back to DiskCache: {e}")
        _redis_client = None
    return _redis_client


# ── Key helpers ──────────────────────────────────────────────────────────────

def _exact_key(query: str) -> str:
    normalized = " ".join(query.lower().strip().split())
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"leta:exact:{digest}"


def _embedding_key(query: str) -> str:
    digest = hashlib.sha256(query.lower().strip().encode()).hexdigest()
    return f"leta:emb:{digest}"


def _semantic_index_key() -> str:
    return "leta:semantic:index"


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


# ── Layer 1: Exact Hash Cache ────────────────────────────────────────────────

def get_exact(query: str) -> Optional[str]:
    key = _exact_key(query)
    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            data = r.get(key)
            if data:
                payload = json.loads(data)
                logger.info(f"Cache L1 HIT (Redis) | q={query[:60]}")
                return payload["answer"]
        except Exception as e:
            logger.warning(f"Cache L1 Redis get error: {e}")
    # Fallback to DiskCache
    dc = _get_disk_cache()
    if dc is not None:
        try:
            payload = dc.get(key)
            if payload:
                logger.info(f"Cache L1 HIT (DiskCache) | q={query[:60]}")
                return payload["answer"]
        except Exception as e:
            logger.warning(f"Cache L1 DiskCache get error: {e}")
    return None


def set_exact(query: str, answer: str, confidence: float) -> None:
    if confidence < CACHE_MIN_CONFIDENCE:
        logger.debug(f"Cache L1 SKIP (low confidence {confidence:.2f}) | q={query[:60]}")
        return
    key = _exact_key(query)
    payload = {"answer": answer, "confidence": confidence, "ts": time.time()}
    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, CACHE_TTL_SECONDS, json.dumps(payload).encode())
            logger.debug(f"Cache L1 SET (Redis) | q={query[:60]}")
            return
        except Exception as e:
            logger.warning(f"Cache L1 Redis set error: {e}")
    # Fallback to DiskCache
    dc = _get_disk_cache()
    if dc is not None:
        try:
            dc.set(key, payload, expire=CACHE_TTL_SECONDS)
            logger.debug(f"Cache L1 SET (DiskCache) | q={query[:60]}")
        except Exception as e:
            logger.warning(f"Cache L1 DiskCache set error: {e}")


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

def verify_cache_hit(query: str, cached_metadata: dict) -> bool:
    """
    Accuracy Guard: Ensures the cached answer is truly relevant.
    Checks for high-priority legal keyword overlap.
    """
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

import re

def get_semantic(query_vec: np.ndarray, query_text: str = "") -> Optional[str]:
    """
    Returns cached answer if any stored entry has cosine similarity
    >= CACHE_SIMILARITY_THRESHOLD and passes accuracy guard.
    """
    global _faiss_index
    if _faiss_index is None:
        _refresh_faiss_index()
    
    if _faiss_index is None:
        return None

    try:
        query_vec_np = np.array([query_vec]).astype('float32')
        D, I = _faiss_index.search(query_vec_np, 1) # Get top 1 result
        
        if len(I[0]) > 0:
            idx = I[0][0]
            similarity = D[0][0]
            
            if idx != -1 and similarity >= CACHE_SIMILARITY_THRESHOLD:
                meta = _faiss_metadata[idx]
                
                # Run Accuracy Guard
                if query_text and not verify_cache_hit(query_text, meta):
                    return None
                    
                logger.info(f"Cache L2 HIT (FAISS) | similarity={similarity:.3f}")
                return meta["answer"]

    except Exception as e:
        logger.warning(f"Cache L2 (FAISS) search error: {e}")
        # Fallback to slow Redis scan if FAISS fails
        return _get_semantic_slow(query_vec)
    return None

def _get_semantic_slow(query_vec: np.ndarray) -> Optional[str]:
    """Legacy slow scan as fallback."""
    r = _get_redis()
    if r is None: return None
    try:
        index_key = _semantic_index_key()
        all_entries = r.hgetall(index_key)
        for _, raw in all_entries.items():
            entry = json.loads(raw)
            sim = _cosine_similarity(query_vec, _bytes_to_vec(bytes.fromhex(entry["vec_hex"])))
            if sim >= CACHE_SIMILARITY_THRESHOLD:
                return entry["answer"]
    except: pass
    return None


def set_semantic(query_vec: np.ndarray, answer: str, confidence: float, query_text: str = "") -> None:
    if confidence < CACHE_MIN_CONFIDENCE:
        return
    r = _get_redis()
    if r is None:
        return
    try:
        index_key = _semantic_index_key()

        # Evict oldest entries if we're at the limit
        current_count = r.hlen(index_key)
        if current_count >= MAX_SEMANTIC_ENTRIES:
            keys_to_delete = list(r.hkeys(index_key))[:MAX_SEMANTIC_ENTRIES // 10]
            if keys_to_delete:
                r.hdel(index_key, *keys_to_delete)

        entry_key = hashlib.sha256(
            (answer[:100] + query_text[:50]).encode()
        ).hexdigest()[:16]

        entry = {
            "vec_hex": _vec_to_bytes(query_vec).hex(),
            "answer": answer,
            "query_text": query_text,
            "confidence": confidence,
            "ts": time.time(),
        }
        r.hset(index_key, entry_key, json.dumps(entry))
        r.expire(index_key, CACHE_TTL_SECONDS)
        
        # Incremental update to local index
        with _faiss_lock:
            if _faiss_index is not None:
                _faiss_index.add(np.array([query_vec]).astype('float32'))
                _faiss_metadata.append({
                    "answer": answer,
                    "query_text": query_text,
                    "confidence": confidence
                })
        
        logger.debug(f"Cache L2 SET | entries~={current_count + 1}")
    except Exception as e:
        logger.warning(f"Cache L2 set error: {e}")


# ── Combined lookup / store (used by retriever + app.py) ────────────────────

def cache_lookup(query: str, query_vec: Optional[np.ndarray] = None) -> Optional[str]:
    """
    Check L1 (exact) then L2 (semantic).
    Returns cached answer string or None on miss.
    """
    answer = get_exact(query)
    if answer:
        return answer

    if query_vec is not None:
        answer = get_semantic(query_vec, query_text=query)
        if answer:
            return answer

    return None


def cache_store(
    query: str,
    query_vec: Optional[np.ndarray],
    answer: str,
    confidence: float,
) -> None:
    """Store answer in both L1 (exact) and L2 (semantic) if confidence is sufficient."""
    set_exact(query, answer, confidence)
    if query_vec is not None:
        set_semantic(query_vec, answer, confidence, query_text=query)


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
