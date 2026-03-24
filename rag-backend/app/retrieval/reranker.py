from typing import List, Dict, Any, Optional
from app.retrieval.source_priority import source_priority

class LegalReranker:
    """
    Implements a Stage-2 Reranking logic for Legal RAG.
    Composite Score = (0.6 * Semantic) + (0.3 * Legal Weight) + (0.1 * Topic Match)
    """

    @staticmethod
    def rerank(query: str, chunks: List[Dict[str, Any]], query_topic: Optional[str] = None) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        # 1. Normalize Semantic Scores (FlashRank/RRF)
        # We assume _rerank_score or _debug_score is available
        max_semantic = max([c.get("_rerank_score", c.get("_debug_score", 0)) for c in chunks]) or 1.0
        
        reranked_chunks = []
        for chunk in chunks:
            # Normalize semantic to 0-1
            semantic_raw = chunk.get("_rerank_score", chunk.get("_debug_score", 0))
            semantic_score = semantic_raw / max_semantic
            
            # 2. Legal Authority Weight (1-5 scale)
            metadata = chunk.get("metadata", {})
            rel_path = chunk.get("rel_path", metadata.get("rel_path", chunk.get("source", metadata.get("source", ""))))
            legal_weight_raw = source_priority(rel_path)
            legal_weight = legal_weight_raw / 5.0
            
            # 3. Topic Match (0 or 1)
            topic_match = 0.0
            chunk_topic = chunk.get("topic", metadata.get("topic", ""))
            if query_topic and chunk_topic:
                if str(chunk_topic).lower() == query_topic.lower():
                    topic_match = 1.0
            
            # 4. Statute-First Boost (Layer 1)
            # If it was found by StatuteRetriever, it gets an automatic massive boost
            layer1_boost = 0.5 if chunk.get("_is_statute_first", False) else 0.0

            # Composite Scoring (Now with Layer 1 Bias)
            # Base score is 0-1. Boost adds 0.5 to ensure it jumps the line if relevant.
            final_score = (0.5 * semantic_score) + (0.3 * legal_weight) + (0.2 * topic_match) + layer1_boost
            
            chunk["_is_statute_first"] = chunk.get("_is_statute_first", False) # Ensure it's explicitly there
            chunk["_final_legal_score"] = final_score
            chunk["_debug_components"] = {
                "semantic": semantic_score,
                "legal": legal_weight,
                "topic": topic_match,
                "layer1_boost": layer1_boost
            }
            reranked_chunks.append(chunk)

        # Sort by final legal score
        reranked_chunks.sort(key=lambda x: x["_final_legal_score"], reverse=True)
        return reranked_chunks
