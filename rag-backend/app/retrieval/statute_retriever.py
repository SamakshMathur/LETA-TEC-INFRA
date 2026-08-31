import json
import logging
import os
from typing import List, Dict, Any

from app.retrieval.quarantine import _is_quarantined

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

        # Try exact match first, then case-insensitive and space-normalized
        topic_data = self.index.get(topic)
        if topic_data is None:
            topic_norm = topic.lower().replace("_", " ").strip()
            for key, val in self.index.items():
                if key.lower().replace("_", " ").strip() == topic_norm:
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
                is_igst = "IGST" in p
                if "Section" in p:
                    val = p.replace("Section", "").strip()
                    normalized_targets.append((LegalParser.normalize_citation("section", val), is_igst))
                    if is_igst:
                        normalized_targets.append((LegalParser.normalize_citation("section", val.replace("IGST", "").strip()), is_igst))
                elif "Rule" in p:
                    val = p.replace("Rule", "").strip()
                    normalized_targets.append((LegalParser.normalize_citation("rule", val), is_igst))
                    if is_igst:
                        normalized_targets.append((LegalParser.normalize_citation("rule", val.replace("IGST", "").strip()), is_igst))
                elif "Schedule" in p:
                    val = p.replace("Schedule", "").strip()
                    normalized_targets.append((LegalParser.normalize_citation("schedule", val), is_igst))
                    if is_igst:
                        normalized_targets.append((LegalParser.normalize_citation("schedule", val.replace("IGST", "").strip()), is_igst))
            except Exception as e:
                logger.warning(f"Failed to normalize provision '{p}': {e}")

        if not normalized_targets:
            logger.debug(f"No normalizable provisions for topic '{topic}'")
            return []

        logger.debug(f"StatuteRetriever: targets={normalized_targets} for topic='{topic}'")

        matched_chunks = []
        for chunk in chunks:
            # Phase 3: quarantine gate — never return quarantined chunks from statute path
            if _is_quarantined(chunk):
                continue
            metadata = chunk.get("metadata", {})
            chunk_citations = metadata.get("citations", [])
            rel_path = metadata.get("rel_path", "").lower()

            for target, require_igst in normalized_targets:
                if require_igst and "igst" not in rel_path:
                    continue
                if any(_provision_matches(cit, target) for cit in chunk_citations):
                    chunk_copy = chunk.copy()
                    chunk_copy["_is_statute_first"] = True
                    chunk_copy["_statute_priority"] = 1.0
                    chunk_copy["_matched_provisions"] = [target]
                    matched_chunks.append(chunk_copy)
                    break

        logger.info(f"StatuteRetriever: {len(matched_chunks)} matches for topic='{topic}'")
        return matched_chunks
