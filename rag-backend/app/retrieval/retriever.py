import faiss
import json
import logging
import threading
import numpy as np
from pathlib import Path
import re

from rank_bm25 import BM25Okapi
from flashrank import Ranker
from app.config import (
    RERANKING_MODEL, EMBEDDING_MODEL, VECTOR_DIM,
    VECTOR_SEARCH_TOP_K, VECTOR_EXPANDED_TOP_K, BM25_TOP_K, MMR_LAMBDA,
)
from app.retrieval.reranker import LegalReranker
from app.retrieval.statute_retriever import StatuteRetriever
from app.retrieval.provision_graph import ProvisionGraphRetriever

logger = logging.getLogger(__name__)

# ─── Pool classification — folder patterns per document category ───────────
_CASE_LAW_FOLDERS  = {"high court case laws", "supreme court case laws", "aar", "other app result"}
_STATUTE_FOLDERS   = {"act", "rules", "cgst", "igst", "utgst", "notification", "notifications", "export"}
_CIRCULAR_FOLDERS  = {"circulars", "circular", "icai", "brochures", "faqs"}


def _chunk_category(chunk: dict) -> str:
    path = (chunk.get("rel_path") or chunk.get("source") or
            chunk.get("metadata", {}).get("rel_path", "")).lower().replace("\\", "/")
    for folder in _CASE_LAW_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "case_law"
    for folder in _CIRCULAR_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "circular"
    for folder in _STATUTE_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "statute"
    return "other"

# ─── Thread-safe embedding model singleton ─────────────────────────────────
_model = None
_model_lock = threading.Lock()


def get_model():
    """Returns the embedding model, loading it once with thread safety."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # double-check after acquiring lock
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
                _model = SentenceTransformer(EMBEDDING_MODEL)
                logger.info("Embedding model loaded successfully")
    return _model


def embed_query(text: str):
    """
    Embeds a single query string (normalized for cosine similarity with IndexFlatIP).
    Results are cached in Redis by SHA-256(text) — saves 200-400ms per cache hit.
    """
    if not text or not text.strip():
        logger.warning("embed_query called with empty text")
        return None

    # L0: embedding cache (Redis)
    try:
        from app.cache import get_cached_embedding, set_cached_embedding
        cached = get_cached_embedding(text)
        if cached is not None:
            return cached
    except Exception:
        pass  # cache miss or unavailable — proceed to model

    model = get_model()
    vec = model.encode(text, normalize_embeddings=True)

    # Store for next time
    try:
        set_cached_embedding(text, vec)
    except Exception:
        pass

    return vec


def tokenize_text(text: str):
    """Simple tokenizer for BM25."""
    return [word.lower() for word in re.findall(r'\b\w+\b', text)]


def _mmr_deduplicate(results, top_k: int, lambda_param: float = MMR_LAMBDA):
    """
    Maximal Marginal Relevance (MMR) deduplication.

    Prevents the top-k being dominated by near-duplicate chunks from the
    same document/paragraph.  Uses token-overlap (Jaccard) as a cheap
    proxy for similarity — avoids a second round of vector encoding.

    lambda_param: 1.0 = pure relevance, 0.0 = pure diversity.
    """
    if not results:
        return results

    selected = []
    remaining = list(results)

    max_score = max(r.get("_final_legal_score", 0) for r in remaining) or 1.0

    def jaccard(a: str, b: str) -> float:
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    while remaining and len(selected) < top_k:
        best_item = None
        best_mmr = -1.0

        for candidate in remaining:
            relevance = candidate.get("_final_legal_score", 0) / max_score

            if selected:
                max_sim = max(
                    jaccard(candidate.get("text", ""), s.get("text", ""))
                    for s in selected
                )
            else:
                max_sim = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_item = candidate

        if best_item:
            selected.append(best_item)
            remaining.remove(best_item)

    return selected


class Retriever:
    def __init__(self, index_path: Path, chunks_path: Path):
        self.index_path = index_path
        self.chunks_path = chunks_path
        self.chunks = []
        self.metadata = []
        self.index = None
        self.bm25 = None

        if not index_path.exists():
            logger.error(f"FAISS index not found at {index_path} — search will return empty results")
            return

        # Load FAISS index
        logger.info("Loading FAISS index...")
        self.index = faiss.read_index(str(index_path))
        logger.info(f"FAISS index loaded: {self.index.ntotal} vectors, dim={self.index.d}")

        # Merge sidecar index if it exists (produced by incremental ingest scripts)
        sidecar_path = index_path.parent / "index_sidecar.faiss"
        if sidecar_path.exists():
            try:
                sidecar = faiss.read_index(str(sidecar_path))
                if sidecar.d == self.index.d and sidecar.ntotal > 0:
                    # Merge: extract all vectors from sidecar and add to main index
                    all_vecs = faiss.rev_swig_ptr(sidecar.get_xb(), sidecar.ntotal * sidecar.d)
                    import numpy as _np
                    all_vecs = _np.array(all_vecs).reshape(sidecar.ntotal, sidecar.d).astype('float32')
                    self.index.add(all_vecs)
                    # Persist merged index and remove sidecar
                    faiss.write_index(self.index, str(index_path))
                    sidecar_path.unlink()
                    logger.info(f"Sidecar merged: +{sidecar.ntotal} vectors → main index now {self.index.ntotal}")
            except Exception as e:
                logger.warning(f"Sidecar merge failed (non-fatal): {e}")

        # Validate dimension
        if self.index.d != VECTOR_DIM:
            logger.error(f"FAISS dimension mismatch: index has {self.index.d}, config expects {VECTOR_DIM}")

        # Load Chunks and Metadata
        logger.info("Loading chunks & building BM25 index...")
        tokenized_corpus = []
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        chunk = json.loads(line)
                        self.chunks.append(chunk)
                        self.metadata.append(chunk.get("metadata", {}))
                        tokenized_corpus.append(tokenize_text(chunk.get("text", "")))
                    except json.JSONDecodeError:
                        logger.warning(f"Malformed JSON at line {line_num} in chunks.jsonl — skipped")
        except FileNotFoundError:
            logger.error(f"Chunks file not found: {chunks_path}")
            return

        # Validate FAISS-chunk alignment
        if self.index.ntotal != len(self.chunks):
            logger.warning(
                f"FAISS/chunk count mismatch: {self.index.ntotal} vectors vs {len(self.chunks)} chunks — "
                "rebuild the index to fix"
            )

        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 index built: {len(tokenized_corpus)} documents")

        # Initialize FlashRank
        logger.info(f"Loading reranker: {RERANKING_MODEL}")
        try:
            self.ranker = Ranker(model_name=RERANKING_MODEL, cache_dir=".flashrank_cache")
        except Exception as e:
            logger.error(f"Failed to load FlashRank reranker: {e}", exc_info=True)
            self.ranker = None

        # Initialize Layer 1 (Statute-First)
        self.statute_retriever = StatuteRetriever()

        # Initialize Provision Graph
        graph_path = Path(chunks_path).parent.parent / "graph" / "edges.jsonl"
        self.graph_retriever = ProvisionGraphRetriever(graph_path)

        logger.info("Retriever initialized: 3-Layer Architecture + Provision Graph + MMR")

    def _enforce_pool_quotas(self, pool: list, query: str, quotas: dict) -> list:
        """
        Guarantee minimum chunks from each document category.
        When a category is underrepresented in the semantic pool, fills it
        with targeted BM25 results restricted to that category's folders.
        quotas = {"statute": N, "case_law": N, "circular": N}
        """
        by_cat = {"statute": [], "case_law": [], "circular": [], "other": []}
        for chunk in pool:
            by_cat[_chunk_category(chunk)].append(chunk)

        seen_ids = {c.get("chunk_id") for c in pool}
        result = list(pool)  # start with the full pool

        if self.bm25:
            tokenized_query = tokenize_text(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)

            for cat, quota in quotas.items():
                have = len(by_cat[cat])
                if have >= quota:
                    continue  # already enough — no action needed

                needed = quota - have
                # Build sorted list of (chunk_index, score) for this category
                cat_indices = [
                    (i, bm25_scores[i])
                    for i, c in enumerate(self.chunks)
                    if _chunk_category(c) == cat
                ]
                cat_indices.sort(key=lambda x: x[1], reverse=True)

                added = 0
                for idx, score in cat_indices:
                    if added >= needed:
                        break
                    chunk = self.chunks[idx].copy()
                    cid = chunk.get("chunk_id")
                    if cid and cid not in seen_ids:
                        chunk["_targeted_fill"] = True
                        chunk["_fill_category"] = cat
                        result.append(chunk)
                        seen_ids.add(cid)
                        added += 1

                if added:
                    logger.info(f"Pool quota fill: +{added} {cat} chunks (had {have}, needed {quota})")

        return result

    def search(self, query: str, top_k: int = 50, allowed_sources=None, advanced_queries=None, domain_paths=None, is_draft: bool = False):
        if not query or not query.strip():
            logger.warning("search() called with empty query")
            return []

        if not self.index or not self.bm25:
            logger.warning("search() called but retriever is not initialized (missing index/bm25)")
            return []

        # --- 1. Query Topic & Subtopic (from pre-computed advanced_queries, no extra LLM call) ---
        topic = "General"
        subtopic = None
        if advanced_queries:
            topic = advanced_queries.get("topic", "General")
            subtopic = advanced_queries.get("subtopic")

        # --- Layer 1: Statute-First Retrieval (Deterministic) ---
        statute_results = self.statute_retriever.search_statutes(self.chunks, topic, subtopic)

        # --- Provision Graph Expansion ---
        graph_results = []
        if statute_results:
            matched_provisions = []
            for res in statute_results:
                matched_provisions.extend(res.get("_matched_provisions", []))

            if matched_provisions:
                graph_results = self.graph_retriever.expand_results(self.chunks, matched_provisions)
                for res in graph_results:
                    res["_is_graph_expanded"] = True
                    res["_statute_priority"] = 0.8

        # --- Layer 2: Broad Semantic Retrieval (Vector + BM25) ---
        candidate_pool = []
        seen_chunk_ids = set()

        def _add_to_pool(idx):
            """Add chunk by index if not already in pool and index is valid."""
            if 0 <= idx < len(self.chunks):
                cid = self.chunks[idx].get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    candidate_pool.append(self.chunks[idx].copy())

        # 1. Vector Search — primary query
        query_vec = embed_query(query)
        if self.index and query_vec is not None:
            D, I = self.index.search(np.array([query_vec]).astype('float32'), VECTOR_SEARCH_TOP_K)
            for idx in I[0]:
                _add_to_pool(idx)

        # 1b. Vector Search — expanded queries + HyDE document
        if advanced_queries and self.index:
            extra_queries = advanced_queries.get("queries", [])[1:]
            hyde_doc = advanced_queries.get("hyde_document", "")
            if hyde_doc:
                extra_queries.append(hyde_doc)

            for eq in extra_queries:
                if not eq or not eq.strip():
                    continue
                eq_vec = embed_query(eq)
                if eq_vec is not None:
                    D2, I2 = self.index.search(np.array([eq_vec]).astype('float32'), VECTOR_EXPANDED_TOP_K)
                    for idx in I2[0]:
                        _add_to_pool(idx)

        # 2. BM25 Search
        if self.bm25:
            tokenized_query = tokenize_text(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_bm25_idxs = np.argsort(bm25_scores)[::-1][:BM25_TOP_K]
            for idx in top_bm25_idxs:
                _add_to_pool(idx)

        # Filter by allowed_sources (file extension)
        if allowed_sources:
            candidate_pool = [
                c for c in candidate_pool
                if any(src.lower() in c.get("rel_path", c.get("metadata", {}).get("rel_path", "")).lower()
                       for src in allowed_sources)
            ]

        # Filter by domain_paths (RAG_INFORMATION_DATABASE sub-folder names).
        # Only applied when the router detected a specific domain; empty = no filter.
        if domain_paths:
            full_path_key = "source"
            filtered = [
                c for c in candidate_pool
                if any(
                    dp.lower() in c.get(full_path_key, "").lower()
                    or dp.lower() in c.get("rel_path", c.get("metadata", {}).get("rel_path", "")).lower()
                    for dp in domain_paths
                )
            ]
            # Only apply the domain filter when it keeps a meaningful subset;
            # fall back to the unfiltered pool if the filter is too aggressive.
            if len(filtered) >= max(3, top_k // 3):
                candidate_pool = filtered
            else:
                logger.debug(
                    f"domain_paths filter too aggressive ({len(filtered)} results) — skipping"
                )

        # ── Phase 2A: Enforce pool quotas — guarantee case law + circulars ──────
        # Drafts need: statute ≥10, case_law ≥10, circular ≥5
        # Q&A needs:   statute ≥8,  case_law ≥6,  circular ≥4
        _quotas = (
            {"statute": 10, "case_law": 10, "circular": 5}
            if is_draft else
            {"statute": 8,  "case_law": 6,  "circular": 4}
        )
        candidate_pool = self._enforce_pool_quotas(candidate_pool, query, _quotas)

        # Merge layers: Statute-First > Graph Expanded > Semantic (+quota fills)
        combined_results = statute_results[:50] + graph_results[:30]
        existing_ids = {r.get("chunk_id") for r in combined_results}
        for r in candidate_pool:
            if r.get("chunk_id") not in existing_ids:
                combined_results.append(r)

        # Cap total candidates for reranker (FlashRank OOM above ~300)
        RERANK_MAX = 200
        reranker_input = combined_results[:RERANK_MAX]

        # --- Semantic Reranking (FlashRank) ---
        reranked_results = reranker_input
        if reranker_input and self.ranker:
            try:
                from flashrank import RerankRequest
                passages = [
                    {"id": idx, "text": res.get("text", ""), "meta": res}
                    for idx, res in enumerate(reranker_input)
                ]
                rank_request = RerankRequest(query=query, passages=passages)
                flash_results = self.ranker.rerank(rank_request)
                reranked_results = []
                for r in flash_results:
                    item = r["meta"]
                    item["_rerank_score"] = r["score"]
                    reranked_results.append(item)
                logger.info(f"FlashRank reranked {len(reranker_input)} -> top {len(reranked_results)} results")
            except Exception as e:
                logger.warning(f"FlashRank reranking failed (falling back to unranked): {e}")
                reranked_results = reranker_input

        # --- Layer 3: Legal Reranking (Composite Scoring) ---
        reranked_results = LegalReranker.rerank(query, reranked_results, query_topic=topic, is_draft=is_draft)

        # --- Layer 4: MMR Deduplication ---
        reranked_results = _mmr_deduplicate(reranked_results, top_k=top_k)

        # Flatten metadata for final output (safe merge avoiding key collisions)
        final_results = []
        for res in reranked_results:
            if "metadata" in res:
                meta = res.pop("metadata")
                for key, val in meta.items():
                    if key not in res:  # don't overwrite existing keys
                        res[key] = val
            final_results.append(res)

        logger.debug(
            f"search() complete: query='{query[:60]}' | "
            f"statute={len(statute_results)} graph={len(graph_results)} "
            f"semantic={len(candidate_pool)} final={len(final_results)}"
        )
        return final_results[:top_k]
