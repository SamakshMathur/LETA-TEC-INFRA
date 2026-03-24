from typing import List, Dict, Any, Optional


def estimate_confidence(
    context: str,
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """
    Estimates answer confidence using actual retrieval signals:
      1. Context volume — is there enough retrieved text?
      2. Rerank scores — how semantically relevant are the top chunks?
      3. Source authority — are we citing Acts/Rules vs brochures?
      4. Citation density — do the chunks contain legal provisions?
    """
    if not context or len(context.strip()) < 50:
        return 0.3

    signals = []

    # --- Signal 1: Context volume (do we have enough material?) ---
    ctx_len = len(context.strip())
    if ctx_len > 5000:
        signals.append(1.0)
    elif ctx_len > 2000:
        signals.append(0.8)
    elif ctx_len > 500:
        signals.append(0.6)
    else:
        signals.append(0.4)

    if chunks:
        # --- Signal 2: Rerank score of top chunks ---
        rerank_scores = [c.get("_rerank_score", 0) for c in chunks if c.get("_rerank_score")]
        if rerank_scores:
            avg_top3 = sum(sorted(rerank_scores, reverse=True)[:3]) / min(len(rerank_scores), 3)
            signals.append(min(avg_top3, 1.0))
        else:
            signals.append(0.5)

        # --- Signal 3: Source authority (higher = more authoritative sources) ---
        from app.retrieval.source_priority import source_priority
        authority_scores = []
        for c in chunks[:10]:  # top 10 chunks
            rel_path = c.get("rel_path", c.get("source", ""))
            authority_scores.append(source_priority(rel_path))
        if authority_scores:
            max_authority = max(authority_scores)
            # Normalize: 5 (Act) = 1.0, 1 (brochure) = 0.2
            signals.append(max_authority / 5.0)
        else:
            signals.append(0.4)

        # --- Signal 4: Citation density (do chunks contain legal refs?) ---
        chunks_with_citations = sum(
            1 for c in chunks[:10]
            if any(kw in c.get("text", "").lower() for kw in ["section", "rule", "notification", "circular"])
        )
        citation_ratio = chunks_with_citations / min(len(chunks), 10) if chunks else 0
        signals.append(citation_ratio)

        # --- Signal 5: Chunk count (enough diverse evidence?) ---
        n_chunks = len(chunks)
        if n_chunks >= 10:
            signals.append(1.0)
        elif n_chunks >= 5:
            signals.append(0.8)
        elif n_chunks >= 2:
            signals.append(0.6)
        else:
            signals.append(0.3)

    # Weighted average of all signals
    if not signals:
        return 0.5

    confidence = sum(signals) / len(signals)
    # Clamp to [0.3, 0.98] — never report 0 or 100%
    return max(0.3, min(0.98, round(confidence, 2)))
