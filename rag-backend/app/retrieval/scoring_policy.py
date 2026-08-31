import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ScoringPolicy:
    """
    Configurable, non-hardcoded retrieval scoring policy defining weights
    and dynamic query-intent boosts.
    """
    def __init__(self):
        # Default weight matrix — calibrated to match main's tuned reranker values.
        # semantic + authority + keyword + topic + recency must sum to 1.0.
        # Change here; deploy — no code change needed.
        self.weights = {
            "semantic":   0.42,   # CrossEncoder cosine similarity (primary signal)
            "authority":  0.20,   # Legal hierarchy weight (Act > Rule > Circular > AAR)
            "keyword":    0.22,   # BM25 keyword overlap (raised from 0.18 — boosts exact-term recall)
            "topic":      0.06,   # Ontology topic match (lowered from 0.14 — avoids topic over-bias)
            "recency":    0.10,   # Year recency for circulars/notifications
        }

        # Extensible typology base weights loaded from config
        from app.config import AUTHORITY_WEIGHTS
        self.authority_weights = AUTHORITY_WEIGHTS

    def get_weight(self, document_type: str, query: str) -> float:
        """
        Dynamically calculates the authority weight for a document type based on query intent.
        Bypasses hardcoded universal truth ranking.
        """
        doc_type_upper = (document_type or "REFERENCE").upper()

        # Map old layout categories to canonical ones for safety
        if doc_type_upper in ["STATUTE", "ACT"]:
            doc_type_upper = "PRIMARY_LAW"
        elif doc_type_upper == "RULE":
            doc_type_upper = "RULES"

        base_weight = self.authority_weights.get(doc_type_upper, 0.5)
        q_lower = query.lower()

        # Intent Boost 1: If query explicitly asks for judicial precedents or court rulings
        if doc_type_upper == "CASE_LAW" and any(k in q_lower for k in ["court", "judgment", "held", "vs", "versus", "precedent", "ruling"]):
            logger.info("ScoringPolicy: Boosting CASE_LAW authority weight based on judicial intent.")
            return 5.0

        # Intent Boost 2: If query explicitly asks for circulars/clarifications
        if doc_type_upper == "CIRCULAR" and any(k in q_lower for k in ["circular", "clarification", "cbic", "clarified"]):
            logger.info("ScoringPolicy: Boosting CIRCULAR authority weight based on circular/clarification intent.")
            return 5.0

        # Intent Boost 3: If query explicitly asks for notifications/exemptions
        if doc_type_upper == "NOTIFICATION" and any(k in q_lower for k in ["notification", "exempt", "rate"]):
            logger.info("ScoringPolicy: Boosting NOTIFICATION authority weight based on notification/exemption intent.")
            return 4.5

        return base_weight

# Global instance for thread-safe access
scoring_policy = ScoringPolicy()
