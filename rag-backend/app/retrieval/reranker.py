import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.retrieval.source_priority import source_priority

logger = logging.getLogger(__name__)

_CASE_LAW_FOLDERS = {"high court case laws", "supreme court case laws", "aar", "other app result"}

def _is_case_law(rel_path: str) -> bool:
    path = rel_path.lower().replace("\\", "/")
    return any(f"/{folder}/" in path or path.startswith(folder + "/") for folder in _CASE_LAW_FOLDERS)

def _is_circular_or_notification(rel_path: str) -> bool:
    path = rel_path.lower().replace("\\", "/")
    return "circular" in path or "notification" in path

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


_CURRENT_YEAR = datetime.now().year

def _year_recency(chunk: dict) -> float:
    """
    Returns 0.0–1.0 recency score for circular/notification chunks.
    Acts and Rules are year-invariant; return neutral 0.6 for them.
    Only boosts documents where freshness genuinely matters (CBIC circulars,
    notifications), which change frequently in GST.
    """
    metadata = chunk.get("metadata", {})
    rel_path = (chunk.get("rel_path") or metadata.get("rel_path", "")).lower()
    doc_type = (metadata.get("document_type") or "").lower()

    is_temporal = (
        "circular" in rel_path or "circular" in doc_type
        or "notification" in rel_path or "notification" in doc_type
    )
    if not is_temporal:
        return 0.6  # neutral — no recency concept for statutes/case law

    raw_year = metadata.get("year") or chunk.get("year")
    if not raw_year:
        return 0.55  # unknown year — slight below-neutral

    try:
        year = int(str(raw_year).strip()[:4])
    except (ValueError, TypeError):
        return 0.55

    age = _CURRENT_YEAR - year
    if age <= 0:
        return 1.00
    elif age == 1:
        return 0.92
    elif age == 2:
        return 0.84
    elif age == 3:
        return 0.76
    elif age <= 5:
        return 0.65
    elif age <= 7:
        return 0.50
    else:
        return 0.35


class LegalReranker:
    """
    Stage-2 Reranking for Legal RAG.
    Scoring weights are configurable in app/retrieval/scoring_policy.py.
    """

    @staticmethod
    def rerank(query: str, chunks: List[Dict[str, Any]], query_topic: Optional[str] = None, is_draft: bool = False) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        from app.retrieval.scoring_policy import scoring_policy

        # Min-max normalization for semantic scores (with epsilon to avoid division by zero)
        scores = [c.get("_rerank_score", c.get("_debug_score", 0)) for c in chunks]
        min_semantic = min(scores)
        max_semantic = max(scores)
        score_range = (max_semantic - min_semantic) or 1.0

        normalized_query_topic = _normalize_topic(query_topic) if query_topic else ""

        # Pre-extract query keyword tokens for component 4 (shared across all chunks)
        _query_kw = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))

        reranked_chunks = []
        for chunk in chunks:
            # 1. Normalize semantic to 0-1 (min-max)
            semantic_raw = chunk.get("_rerank_score", chunk.get("_debug_score", 0))
            semantic_score = (semantic_raw - min_semantic) / score_range

            # 2. Configurable Legal authority weight (scale → 0-1)
            metadata = chunk.get("metadata", {})
            rel_path = chunk.get("rel_path", metadata.get("rel_path", chunk.get("source", metadata.get("source", ""))))

            doc_type = metadata.get("canonical_document_type", metadata.get("document_type", "REFERENCE"))
            legal_weight_raw = scoring_policy.get_weight(doc_type, query)
            legal_weight = legal_weight_raw / 5.0

            # 3. Topic match (fuzzy-normalized comparison)
            _RELATED_TOPICS = {
                "place_of_supply": {"export", "itc"},
                "export": {"place_of_supply", "refund"},
                "refund": {"export", "itc"},
                "itc": {"place_of_supply", "valuation", "refund"},
            }
            topic_match = 0.0
            chunk_topic = chunk.get("topic") or metadata.get("topic") or ""
            if normalized_query_topic and chunk_topic:
                normalized_chunk_topic = _normalize_topic(str(chunk_topic))
                if normalized_chunk_topic == normalized_query_topic:
                    topic_match = 1.0
                elif normalized_chunk_topic in _RELATED_TOPICS.get(normalized_query_topic, set()):
                    topic_match = 0.5

            # 4. Keyword overlap: fraction of query terms present in chunk text.
            chunk_text_lower = chunk.get("text", "").lower()
            kw_hits = sum(1 for t in _query_kw if t in chunk_text_lower)
            kw_match = min(kw_hits / max(len(_query_kw), 1), 1.0)

            # 5. Statute-First boost (Layer 1 bias)
            layer1_boost = 0.5 if chunk.get("_is_statute_first", False) else 0.0

            # 6. Year recency — boosts recent circulars/notifications over older ones;
            recency = _year_recency(chunk)

            # Composite scoring loaded from ScoringPolicy:
            w_semantic = scoring_policy.weights.get("semantic", 0.40)
            w_authority = scoring_policy.weights.get("authority", 0.18)
            w_keyword = scoring_policy.weights.get("keyword", 0.18)
            w_topic = scoring_policy.weights.get("topic", 0.14)
            w_recency = scoring_policy.weights.get("recency", 0.10)

            final_score = (
                (w_semantic * semantic_score)
                + (w_authority * legal_weight)
                + (w_keyword * kw_match)
                + (w_topic * topic_match)
                + (w_recency * recency)
                + layer1_boost
            )

            # Generic Legal Evidence Protection Boost Tiers
            ref_boost = 0.0
            if chunk.get("_pinned_by_ref", False):
                pinned_tier = chunk.get("_pinned_tier", "SECONDARY")
                if pinned_tier == "PRIMARY":
                    ref_boost = 2.5   # Tier 1: Canonical explicit primary authority
                else:
                    ref_boost = 1.2   # Tier 2: Strong direct secondary reference
            elif chunk.get("_statute_priority", 0) > 0:
                ref_boost = 0.6 * chunk.get("_statute_priority", 0)  # Tier 3: Related statutory matches

            final_score += ref_boost

            # Draft mode: boost case laws, circulars, and notifications so they compete with statutes
            if is_draft and (_is_case_law(rel_path) or _is_circular_or_notification(rel_path)):
                final_score *= 1.3

            chunk["_is_statute_first"] = chunk.get("_is_statute_first", False)
            chunk["_final_legal_score"] = final_score
            chunk["_debug_components"] = {
                "semantic": round(semantic_score, 4),
                "legal": round(legal_weight, 4),
                "kw_match": round(kw_match, 4),
                "topic": topic_match,
                "recency": round(recency, 4),
                "layer1_boost": layer1_boost,
                "ref_boost": ref_boost
            }
            reranked_chunks.append(chunk)

        reranked_chunks.sort(key=lambda x: x["_final_legal_score"], reverse=True)


        logger.debug(
            f"Reranked {len(reranked_chunks)} chunks | "
            f"top_score={reranked_chunks[0]['_final_legal_score']:.3f} | "
            f"topic='{query_topic}'"
        )
        return reranked_chunks
