import json
import os
from typing import List, Dict, Any

class StatuteRetriever:
    """
    Layer 1: Deterministic Statute Retrieval.
    Uses a predefined index to pull primary law chunks based on the detected topic.
    """
    def __init__(self, index_path: str = None):
        if index_path is None:
            # Default path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            index_path = os.path.join(current_dir, "statute_index.json")
        
        self.index_path = index_path
        self.index = {}
        self.load_index()

    def load_index(self):
        try:
            if os.path.exists(self.index_path):
                with open(self.index_path, "r") as f:
                    self.index = json.load(f)
            else:
                print(f"Statute Index not found at {self.index_path}")
        except Exception as e:
            print(f"Error loading Statute Index: {e}")

    def get_provisions(self, topic: str, subtopic: str = None) -> List[str]:
        """Returns a list of prioritized provisions for a topic."""
        provisions = []
        topic_data = self.index.get(topic, {})
        
        if topic_data:
            # Add primary provisions
            provisions.extend(topic_data.get("primary", []))
            
            # Add subtopic provisions if matched
            if subtopic and "subtopics" in topic_data:
                sub_provisions = topic_data["subtopics"].get(subtopic, [])
                # Prepend subtopical provisions to prioritize them if they are more specific
                provisions = sub_provisions + [p for p in provisions if p not in sub_provisions]
                
        return provisions

    def search_statutes(self, chunks: List[Dict[str, Any]], topic: str, subtopic: str = None) -> List[Dict[str, Any]]:
        """
        Filters the full chunk list to find deterministic matches for the statute using normalized citations.
        """
        priority_provisions = self.get_provisions(topic, subtopic)
        # Canonicalize priority provisions (e.g., "Section 17" -> "CGST_SEC_17")
        from app.ingestion.legal_parser import LegalParser
        normalized_targets = []
        for p in priority_provisions:
            if "Section" in p:
                normalized_targets.append(LegalParser.normalize_citation("section", p.replace("Section", "").strip()))
            elif "Rule" in p:
                normalized_targets.append(LegalParser.normalize_citation("rule", p.replace("Rule", "").strip()))
                
        print(f"StatuteRetriever: Looking for targets {normalized_targets} for topic '{topic}'")
        if not normalized_targets:
            return []

        matched_chunks = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            chunk_citations = metadata.get("citations", [])
            
            # Match if any citation in chunk starts with any normalized target
            for target in normalized_targets:
                if any(cit.startswith(target) for cit in chunk_citations):
                    chunk_copy = chunk.copy()
                    chunk_copy["_is_statute_first"] = True
                    chunk_copy["_statute_priority"] = 1.0
                    matched_chunks.append(chunk_copy)
                    # Use extracted primary provisions for graph expansion later
                    chunk_copy["_matched_provisions"] = [target] 
                    break
        
        print(f"StatuteRetriever: Found {len(matched_chunks)} prioritized matches.")
        return matched_chunks
