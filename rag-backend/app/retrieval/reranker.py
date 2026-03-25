import logging
from typing import List, Dict, Any, Optional
from app.retrieval.source_priority import source_priority

logger = logging.getLogger(__name__)

# Topic aliases for fuzzy matching (common variations → canonical name)
_TOPIC_ALIASES = {
    "input tax credit": "itc",
    "input_tax_credit": "itc",
    "reverse charge": "rcm",
    "reverse_charge": "rcm",
    "reverse charge mechanism": "rcm",
    "place of supply": "place_of_supply",
    "works contract": "works_contract",
    "works_contract": "works_contract",
    "composite supply": "composite_supply",
    "composite_supply": "composite_supply",
    "time of supply": "time_of_supply",
    "time_of_supply": "time_of_supply",
}


def _normalize_topic(topic: str) -> str:
    """Normalize topic string for comparison."""
    if not topic:
        return ""
    lower = topic.strip().lower()
    return _TOPIC_ALIASES.get(lower, lower)


class LegalReranker:
    """
    Stage-2 Reranking for Legal RAG.
    Composite Score = (0.5 * Semantic) + (0.3 * Legal Weight) + (0.2 * Topic Match) + Layer1 Boost
    """

    @staticmethod
    def rerank(query: str, chunks: List[Dict[str, Any]], query_topic: Optional[str] = None) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        # Min-max normalization for semantic scores (with epsilon to avoid division by zero)
        scores = [c.get("_rerank_score", c.get("_debug_score", 0)) for c in chunks]
        min_semantic = min(scores)
        max_semantic = max(scores)
        score_range = (max_semantic - min_semantic) or 1.0

        normalized_query_topic = _normalize_topic(query_topic) if query_topic else ""

        reranked_chunks = []
        for chunk in chunks:
            # 1. Normalize semantic to 0-1 (min-max)
            semantic_raw = chunk.get("_rerank_score", chunk.get("_debug_score", 0))
            semantic_score = (semantic_raw - min_semantic) / score_range

            # 2. Legal authority weight (1-5 scale → 0-1)
            metadata = chunk.get("metadata", {})
            rel_path = chunk.get("rel_path", metadata.get("rel_path", chunk.get("source", metadata.get("source", ""))))
            legal_weight_raw = source_priority(rel_path)
            legal_weight = legal_weight_raw / 5.0

            # 3. Topic match (fuzzy-normalized comparison)
            topic_match = 0.0
            chunk_topic = chunk.get("topic", metadata.get("topic", ""))
            if normalized_query_topic and chunk_topic:
                normalized_chunk_topic = _normalize_topic(str(chunk_topic))
                if normalized_chunk_topic == normalized_query_topic:
                    topic_match = 1.0

            # 4. Statute-First boost (Layer 1 bias)
            layer1_boost = 0.5 if chunk.get("_is_statute_first", False) else 0.0

            # Composite scoring
            # Base components sum to 1.0, layer1_boost is additive for statute priority
            final_score = (0.5 * semantic_score) + (0.3 * legal_weight) + (0.2 * topic_match) + layer1_boost

            chunk["_is_statute_first"] = chunk.get("_is_statute_first", False)
            chunk["_final_legal_score"] = final_score
            chunk["_debug_components"] = {
                "semantic": round(semantic_score, 4),
                "legal": round(legal_weight, 4),
                "topic": topic_match,
                "layer1_boost": layer1_boost,
            }
            reranked_chunks.append(chunk)

        reranked_chunks.sort(key=lambda x: x["_final_legal_score"], reverse=True)

        logger.debug(
            f"Reranked {len(reranked_chunks)} chunks | "
            f"top_score={reranked_chunks[0]['_final_legal_score']:.3f} | "
            f"topic='{query_topic}'"
        )
        return reranked_chunks
