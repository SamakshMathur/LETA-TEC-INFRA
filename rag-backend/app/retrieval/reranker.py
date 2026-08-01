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


# GST-specific stopwords to exclude from keyword-match scoring.
# These words appear in almost every legal chunk and would falsely boost unrelated results.
_KW_STOPWORDS = frozenset([
    "the", "and", "for", "are", "was", "has", "had", "not", "but", "this", "that",
    "with", "from", "its", "any", "all", "can", "may", "will", "such", "said",
    "also", "than", "then", "when", "where", "which", "who", "their", "they",
    "been", "have", "shall", "said", "under", "upon", "into", "out", "per",
    "act", "rule", "sub", "clause", "proviso", "section", "gst", "tax",
])


class LegalReranker:
    """
    Stage-2 Reranking for Legal RAG.
    Composite Score = (0.42 * Semantic) + (0.20 * Legal Weight) + (0.22 * KW Match)
                    + (0.06 * Topic Match) + (0.10 * Year Recency) + Layer1 Boost

    Changes from v1:
    - KW match uses legal stopword filter (removes generic words that inflate scores)
    - Topic match uses keyword overlap instead of binary equality (was always 0)
    - Semantic: sigmoid-normalized instead of min-max (prevents all-zero edge case)
    - Weights rebalanced: KW match raised 0.18→0.22, topic lowered 0.14→0.06
    """

    @staticmethod
    def rerank(query: str, chunks: List[Dict[str, Any]], query_topic: Optional[str] = None, is_draft: bool = False) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        # Sigmoid normalization for semantic scores — handles FlashRank failure gracefully.
        # Unlike min-max, sigmoid doesn't collapse when all scores are equal (returns ~0.5)
        # and still spreads scores well when they differ.
        import math as _math
        def _sigmoid(x: float) -> float:
            try:
                return 1.0 / (1.0 + _math.exp(-x * 5.0))
            except OverflowError:
                return 0.0 if x < 0 else 1.0

        scores = [c.get("_rerank_score", c.get("_debug_score", 0)) for c in chunks]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = (max_score - min_score) or 1.0

        normalized_query_topic = _normalize_topic(query_topic) if query_topic else ""

        # Pre-extract query keyword tokens — strip stopwords and short tokens.
        # Also extract GST-specific compound tokens (section numbers, form codes).
        _raw_kw = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
        _query_kw = _raw_kw - _KW_STOPWORDS

        # Extract numeric tokens separately (section 16, rule 89, etc.) — these are
        # highly discriminative and must not be lost to the 3-char filter.
        _query_nums = set(re.findall(r'\b\d+[a-z]?\b', query.lower()))

        # Pre-extract query topic keywords for partial topic matching
        _query_topic_kw = set(re.findall(r'\b[a-z]{3,}\b', normalized_query_topic)) - _KW_STOPWORDS if normalized_query_topic else set()

        reranked_chunks = []
        for chunk in chunks:
            # 1. Normalize semantic to 0-1 (sigmoid of normalized raw score)
            semantic_raw = chunk.get("_rerank_score", chunk.get("_debug_score", 0))
            # Centre-normalize then sigmoid: score relative to midpoint of range
            centered = (semantic_raw - min_score) / score_range - 0.5
            semantic_score = _sigmoid(centered)

            # 2. Legal authority weight (1-5 scale → 0-1)
            metadata = chunk.get("metadata", {})
            rel_path = chunk.get("rel_path", metadata.get("rel_path", chunk.get("source", metadata.get("source", ""))))
            legal_weight_raw = source_priority(rel_path)
            legal_weight = legal_weight_raw / 5.0

            # 3. Topic match — keyword overlap between query topic and chunk topic.
            # Binary equality (old approach) almost always scored 0; overlap scores partial matches.
            topic_match = 0.0
            chunk_topic_raw = chunk.get("topic", metadata.get("topic", ""))
            if _query_topic_kw and chunk_topic_raw:
                chunk_topic_kw = set(re.findall(r'\b[a-z]{3,}\b', _normalize_topic(str(chunk_topic_raw)))) - _KW_STOPWORDS
                if chunk_topic_kw:
                    overlap = len(_query_topic_kw & chunk_topic_kw)
                    topic_match = min(overlap / max(len(_query_topic_kw), 1), 1.0)

            # 4. Keyword overlap: fraction of meaningful query terms in chunk text.
            # Uses stopword-filtered tokens + numeric tokens to avoid generic word inflation.
            chunk_text_lower = (chunk.get("context_text") or chunk.get("text", "")).lower()
            kw_hits = sum(1 for t in _query_kw if t in chunk_text_lower)
            num_hits = sum(1 for n in _query_nums if n in chunk_text_lower)
            total_meaningful = max(len(_query_kw) + len(_query_nums), 1)
            kw_match = min((kw_hits + num_hits * 2) / total_meaningful, 1.0)  # nums weighted 2x

            # 5. Statute-First boost (Layer 1 bias)
            layer1_boost = 0.5 if chunk.get("_is_statute_first", False) else 0.0

            # 6. Year recency — boosts recent circulars/notifications over older ones;
            # returns neutral 0.6 for Acts/Rules/case-law (no recency concept there).
            recency = _year_recency(chunk)

            # Composite scoring (weights rebalanced from v1):
            # 0.42 semantic  — FlashRank cross-encoder relevance (primary signal)
            # 0.20 legal     — Authority hierarchy (Acts > Rules > Circulars > AARs)
            # 0.22 kw_match  — Direct keyword+number overlap (stopword-filtered)
            # 0.06 topic     — Topic/subtopic keyword overlap (was 0.14 binary)
            # 0.10 recency   — Year recency for circulars/notifications
            # +layer1_boost  — Additive boost for Statute-First Layer 1 results
            final_score = (
                (0.42 * semantic_score)
                + (0.20 * legal_weight)
                + (0.22 * kw_match)
                + (0.06 * topic_match)
                + (0.10 * recency)
                + layer1_boost
            )

            # Draft mode: boost case law so judgments compete with statutes
            if is_draft and _is_case_law(rel_path):
                final_score *= 1.3
            # Q&A: no penalty — legal_weight (30% of score) already naturally
            # ranks Acts/Circulars above AARs; let semantic relevance decide

            chunk["_is_statute_first"] = chunk.get("_is_statute_first", False)
            chunk["_final_legal_score"] = final_score
            chunk["_debug_components"] = {
                "semantic": round(semantic_score, 4),
                "legal": round(legal_weight, 4),
                "kw_match": round(kw_match, 4),
                "topic": topic_match,
                "recency": round(recency, 4),
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
