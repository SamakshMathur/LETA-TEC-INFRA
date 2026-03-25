import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class StatuteRetriever:
    """
    Layer 1: Deterministic Statute Retrieval.
    Uses a predefined index to pull primary law chunks based on the detected topic.
    """
    def __init__(self, index_path: str = None):
        if index_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            index_path = os.path.join(current_dir, "statute_index.json")

        self.index_path = index_path
        self.index: Dict[str, Any] = {}
        self._loaded = False
        self.load_index()

    def load_index(self):
        try:
            if os.path.exists(self.index_path):
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self.index = json.load(f)
                self._loaded = True
                logger.info(f"Statute index loaded: {len(self.index)} topics from {self.index_path}")
            else:
                logger.warning(f"Statute index not found at {self.index_path} — Layer 1 disabled")
        except json.JSONDecodeError as e:
            logger.error(f"Malformed statute index JSON at {self.index_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load statute index: {e}", exc_info=True)

    def get_provisions(self, topic: str, subtopic: str = None) -> List[str]:
        """Returns a list of prioritized provisions for a topic."""
        if not self._loaded:
            return []

        # Try exact match first, then case-insensitive
        topic_data = self.index.get(topic)
        if topic_data is None:
            topic_lower = topic.lower()
            for key, val in self.index.items():
                if key.lower() == topic_lower:
                    topic_data = val
                    break

        if not topic_data:
            logger.debug(f"No provisions found for topic '{topic}'")
            return []

        provisions = list(topic_data.get("primary", []))

        if subtopic and "subtopics" in topic_data:
            sub_provisions = topic_data["subtopics"].get(subtopic, [])
            provisions = sub_provisions + [p for p in provisions if p not in sub_provisions]

        return provisions

    def search_statutes(self, chunks: List[Dict[str, Any]], topic: str, subtopic: str = None) -> List[Dict[str, Any]]:
        """
        Filters the full chunk list to find deterministic matches using normalized citations.
        """
        priority_provisions = self.get_provisions(topic, subtopic)
        if not priority_provisions:
            return []

        from app.ingestion.legal_parser import LegalParser
        from app.retrieval.provision_graph import _provision_matches

        normalized_targets = []
        for p in priority_provisions:
            try:
                if "Section" in p:
                    normalized_targets.append(LegalParser.normalize_citation("section", p.replace("Section", "").strip()))
                elif "Rule" in p:
                    normalized_targets.append(LegalParser.normalize_citation("rule", p.replace("Rule", "").strip()))
                elif "Schedule" in p:
                    normalized_targets.append(LegalParser.normalize_citation("schedule", p.replace("Schedule", "").strip()))
            except Exception as e:
                logger.warning(f"Failed to normalize provision '{p}': {e}")

        if not normalized_targets:
            logger.debug(f"No normalizable provisions for topic '{topic}'")
            return []

        logger.debug(f"StatuteRetriever: targets={normalized_targets} for topic='{topic}'")

        matched_chunks = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            chunk_citations = metadata.get("citations", [])

            for target in normalized_targets:
                if any(_provision_matches(cit, target) for cit in chunk_citations):
                    chunk_copy = chunk.copy()
                    chunk_copy["_is_statute_first"] = True
                    chunk_copy["_statute_priority"] = 1.0
                    chunk_copy["_matched_provisions"] = [target]
                    matched_chunks.append(chunk_copy)
                    break

        logger.info(f"StatuteRetriever: {len(matched_chunks)} matches for topic='{topic}'")
        return matched_chunks
