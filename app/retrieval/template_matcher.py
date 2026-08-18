"""
Template Matcher — Searches the litigation template database
and returns matching templates alongside LETA chat answers.

When a user asks a question on LETA, this module checks if any
litigation templates are relevant. If found, they are surfaced
as downloadable suggestions alongside the legal answer.
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def search_templates(
    query: str,
    top_k: int = 3,
    score_threshold: float = 0.25,
) -> List[Dict[str, Any]]:
    """
    Searches MongoDB template collection using hybrid scoring:
      1. Vector similarity (BGE embeddings in the template collection)
      2. Lexical match on title + keywords

    Returns top matching templates with id, title, category, score.
    Returns empty list if no templates match or DB unavailable.
    """
    try:
        from app.database import get_template_collection
        from app.embeddings.embedder import embed_texts

        collection = get_template_collection()
        if collection is None:
            return []

        # Count templates — skip if empty collection
        if collection.count_documents({}) == 0:
            return []

        # Generate query embedding
        query_vector = embed_texts([query])[0]
        query_np = np.array(query_vector)
        query_lower = query.lower()

        # Fetch templates with embeddings
        all_docs = list(collection.find(
            {},
            {
                "embedding": 1, "title": 1, "category": 1,
                "sub_category": 1, "stage": 1, "keywords": 1,
                "summary": 1,
            }
        ))

        if not all_docs:
            return []

        scored = []
        for doc in all_docs:
            doc_embedding = doc.get("embedding")
            if not doc_embedding:
                continue

            # Vector similarity (cosine via dot product — embeddings should be normalized)
            doc_np = np.array(doc_embedding)
            vector_score = float(np.dot(doc_np, query_np))

            # Lexical boost on title
            title = doc.get("title", "").lower()
            lexical_boost = 0.0
            if query_lower in title:
                lexical_boost = 0.7
            else:
                q_words = [w for w in query_lower.split() if len(w) > 2]
                if q_words:
                    matches = sum(1 for w in q_words if w in title)
                    lexical_boost = (matches / len(q_words)) * 0.5

            # Keyword boost
            keywords = [k.lower() for k in doc.get("keywords", [])]
            keyword_boost = 0.0
            for w in query_lower.split():
                if w in keywords:
                    keyword_boost = max(keyword_boost, 0.3)

            # Combined: 50% semantic + 30% title + 20% keyword
            final = (vector_score * 0.5) + (lexical_boost * 0.3) + (keyword_boost * 0.2)

            if final >= score_threshold:
                scored.append({
                    "id": str(doc["_id"]),
                    "title": doc.get("title", ""),
                    "category": doc.get("category", ""),
                    "sub_category": doc.get("sub_category", ""),
                    "stage": doc.get("stage", ""),
                    "summary": doc.get("summary", ""),
                    "score": round(final, 3),
                })

        # Sort by score, return top_k
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    except Exception as e:
        logger.warning(f"Template search failed (non-fatal): {e}")
        return []


def format_template_suggestions(templates: List[Dict[str, Any]]) -> str:
    """
    Formats matched templates as a markdown block to append to the
    streamed answer.
    """
    if not templates:
        return ""

    lines = [
        "\n\n" + "=" * 40,
        "RELEVANT LITIGATION TEMPLATES",
        "=" * 40,
        "The following pre-drafted legal templates match your query.",
        "Navigate to Templates section to view, customize, and download.\n",
    ]

    for i, t in enumerate(templates, 1):
        lines.append(
            f"{i}. **{t['title']}**\n"
            f"   Category: {t['category']} | Stage: {t['stage']}\n"
            f"   {t['summary'][:150]}\n"
        )

    lines.append("=" * 40)
    return "\n".join(lines)
