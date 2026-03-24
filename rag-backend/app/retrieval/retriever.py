import faiss
import json
import numpy as np
from pathlib import Path
import os
from app.retrieval.source_priority import source_priority
from rank_bm25 import BM25Okapi
from flashrank import Ranker
from app.config import RERANKING_MODEL, EMBEDDING_MODEL, VECTOR_DIM
from app.retrieval.reranker import LegalReranker
from app.retrieval.statute_retriever import StatuteRetriever
from app.retrieval.provision_graph import ProvisionGraphRetriever
import re

_model = None


def get_model():
    """Returns the embedding model, loading it if necessary."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"Loading Embedding Model ({EMBEDDING_MODEL})...")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_query(text: str):
    """Embeds a single query string."""
    model = get_model()
    return model.encode(text)


def tokenize_text(text: str):
    """Simple tokenizer for BM25."""
    return [word.lower() for word in re.findall(r'\b\w+\b', text)]


def _mmr_deduplicate(results, top_k: int, lambda_param: float = 0.7):
    """
    Maximal Marginal Relevance (MMR) deduplication.

    Prevents the top-k being dominated by near-duplicate chunks from the
    same document/paragraph.  Uses token-overlap (Jaccard) as a cheap
    proxy for similarity — avoids a second round of vector encoding.

    lambda_param: 1.0 = pure relevance (no dedup), 0.0 = pure diversity.
    0.7 is a good balance for legal RAG.
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

            # Max similarity to any already-selected chunk
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

        if not index_path.exists():
            print(f"Index not found at {index_path}. Search will fail.")
            self.index = None
            self.bm25 = None
            return

        # Load FAISS index
        print("Loading FAISS Index...")
        self.index = faiss.read_index(str(index_path))

        # Load Chunks and Metadata
        print("Loading Chunks & Building BM25 index...")
        tokenized_corpus = []
        with open(chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                self.chunks.append(chunk)
                self.metadata.append(chunk.get("metadata", {}))
                tokenized_corpus.append(tokenize_text(chunk.get("text", "")))

        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_corpus)
        print("BM25 Index Built Successfully.")

        # Initialize FlashRank (Accuracy Engine)
        print(f"Loading Reranker ({RERANKING_MODEL})...")
        self.ranker = Ranker(model_name=RERANKING_MODEL, cache_dir=".flashrank_cache")

        # Initialize Layer 1 (Statute-First)
        self.statute_retriever = StatuteRetriever()

        # Initialize Provision Graph
        graph_path = Path(chunks_path).parent.parent / "graph" / "edges.jsonl"
        self.graph_retriever = ProvisionGraphRetriever(graph_path)

        print("Retriever: 3-Layer Architecture + Provision Graph + MMR Initialized.")

    def search(self, query: str, top_k: int = 50, allowed_sources=None, advanced_queries=None):
        if not self.index or not self.bm25:
            return []

        # --- 1. Query Topic & Subtopic extraction ---
        from app.retrieval.query_refiner import extract_query_topic
        topic_info = extract_query_topic(query)
        topic = topic_info if isinstance(topic_info, str) else topic_info.get("topic", "General")
        subtopic = None if isinstance(topic_info, str) else topic_info.get("subtopic")

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
            """Add chunk by index if not already in pool."""
            if 0 <= idx < len(self.chunks):
                cid = self.chunks[idx].get("chunk_id")
                if cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    candidate_pool.append(self.chunks[idx].copy())

        # 1. Vector Search — primary query (wider pool to feed MMR dedup later)
        query_vec = embed_query(query)
        if self.index and query_vec is not None:
            D, I = self.index.search(np.array([query_vec]).astype('float32'), 150)
            for idx in I[0]:
                _add_to_pool(idx)

        # 1b. Vector Search — expanded queries + HyDE document
        if advanced_queries and self.index:
            extra_queries = advanced_queries.get("queries", [])[1:]  # skip first (already used as primary)
            hyde_doc = advanced_queries.get("hyde_document", "")
            if hyde_doc:
                extra_queries.append(hyde_doc)

            for eq in extra_queries:
                if not eq or not eq.strip():
                    continue
                eq_vec = embed_query(eq)
                if eq_vec is not None:
                    D2, I2 = self.index.search(np.array([eq_vec]).astype('float32'), 50)
                    for idx in I2[0]:
                        _add_to_pool(idx)

        # 2. BM25 Search
        if self.bm25:
            tokenized_query = tokenize_text(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_bm25_idxs = np.argsort(bm25_scores)[::-1][:100]
            for idx in top_bm25_idxs:
                _add_to_pool(idx)

        # Filter by allowed_sources
        if allowed_sources:
            candidate_pool = [
                c for c in candidate_pool
                if any(src.lower() in c.get("rel_path", "").lower() for src in allowed_sources)
            ]

        # Merge layers: Statute-First > Graph Expanded > Semantic
        combined_results = statute_results + graph_results
        existing_ids = {r.get("chunk_id") for r in combined_results}
        for r in candidate_pool:
            if r.get("chunk_id") not in existing_ids:
                combined_results.append(r)

        # --- Semantic Reranking (FlashRank) ---
        from flashrank import RerankRequest

        passages = [
            {"id": idx, "text": res["text"], "meta": res}
            for idx, res in enumerate(combined_results)
        ]

        reranked_results = []
        if passages:
            try:
                rank_request = RerankRequest(query=query, passages=passages)
                flash_results = self.ranker.rerank(rank_request)
                for r in flash_results:
                    item = r["meta"]
                    item["_rerank_score"] = r["score"]
                    reranked_results.append(item)
            except Exception as e:
                print(f"FlashRank Failed: {e}")
                reranked_results = combined_results

        # --- Layer 3: Legal Reranking (Composite Scoring) ---
        reranked_results = LegalReranker.rerank(query, reranked_results, query_topic=topic)

        # --- Layer 4: MMR Deduplication ---
        # Removes near-duplicate chunks from the same document so the LLM
        # sees diverse evidence rather than 5 paraphrases of the same paragraph.
        reranked_results = _mmr_deduplicate(reranked_results, top_k=top_k * 2)

        # Flatten metadata for final output
        final_results = []
        for res in reranked_results:
            if "metadata" in res:
                meta = res.pop("metadata")
                res.update(meta)
            final_results.append(res)

        return final_results[:top_k]
