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

    def build_lookup(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Build a citation → [chunk_idx] lookup table once at startup.

        Call this from Retriever.__init__() after self.chunks is populated so that
        search_statutes() can use an O(unique_citations) scan instead of an O(n_chunks)
        linear scan on every request.  For a corpus of ~60 K chunks the linear scan
        costs ~5–15 ms/request; this lookup cuts it to < 1 ms.
        """
        self._chunks = chunks
        self._citation_to_indices: Dict[str, List[int]] = {}
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            for cit in (metadata.get("citations") or []):
                if cit not in self._citation_to_indices:
                    self._citation_to_indices[cit] = []
                self._citation_to_indices[cit].append(i)
        logger.info(
            f"StatuteRetriever: citation lookup built — "
            f"{len(self._citation_to_indices)} unique citations across {len(chunks)} chunks"
        )

    def search_statutes(self, chunks: List[Dict[str, Any]], topic: str, subtopic: str = None) -> List[Dict[str, Any]]:
        """
        Filters the full chunk list to find deterministic matches using normalized citations.

        Fast path (O(unique_citations × n_targets)): used when build_lookup() has been
        called at startup.  Falls back to the original O(n_chunks) linear scan when no
        index is available so the function is always safe to call.
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

        # ── Fast path: pre-built index ────────────────────────────────────────────
        if hasattr(self, '_citation_to_indices') and hasattr(self, '_chunks'):
            # Iterate over unique citations (typically O(10K)) rather than all chunks
            # (O(60K)).  For each raw citation that matches any target, record the
            # chunk indices; then build the result list from the matched indices.
            matched_indices: dict = {}  # idx → list of matched targets (for metadata)
            for raw_cit, idx_list in self._citation_to_indices.items():
                for target in normalized_targets:
                    if _provision_matches(raw_cit, target):
                        for idx in idx_list:
                            if idx not in matched_indices:
                                matched_indices[idx] = []
                            matched_indices[idx].append(target)
                        break  # this raw_cit matched; don't check more targets for it

            matched_chunks = []
            for idx, matched_targets in matched_indices.items():
                chunk_copy = self._chunks[idx].copy()
                chunk_copy["_is_statute_first"] = True
                chunk_copy["_statute_priority"] = 1.0
                chunk_copy["_matched_provisions"] = matched_targets
                matched_chunks.append(chunk_copy)

            logger.info(f"StatuteRetriever (indexed): {len(matched_chunks)} matches for topic='{topic}'")
            return matched_chunks

        # ── Slow path: linear scan (fallback when index not yet built) ────────────
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

        logger.info(f"StatuteRetriever (linear): {len(matched_chunks)} matches for topic='{topic}'")
        return matched_chunks
