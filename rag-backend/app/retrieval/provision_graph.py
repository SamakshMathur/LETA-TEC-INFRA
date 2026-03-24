import json
from pathlib import Path
from typing import List, Dict, Set

class ProvisionGraphRetriever:
    """
    Handles Provision-Graph Retrieval (Neighbor Expansion).
    Models relationships between statutes, rules, circulars, and case law.
    """
    def __init__(self, edges_path: Path):
        self.edges_path = edges_path
        self.adj_list = {}
        self.load_graph()

    def load_graph(self):
        if not self.edges_path.exists():
            print(f"Warning: Provision Graph edges not found at {self.edges_path}")
            return
            
        with open(self.edges_path, 'r', encoding='utf-8') as f:
            for line in f:
                edge = json.loads(line)
                src = edge["source"]
                tgt = edge["target"]
                
                # Bi-directional expansion for RELATED_TO, but directional for others
                if src not in self.adj_list: self.adj_list[src] = []
                self.adj_list[src].append({"target": tgt, "relation": edge["relation"]})
                
                # For basic relation, also add reverse to allow discovery
                if edge["relation"] in ["RELATED_TO", "CO_IMPLEMENTED"]:
                    if tgt not in self.adj_list: self.adj_list[tgt] = []
                    self.adj_list[tgt].append({"target": src, "relation": edge["relation"]})

    def get_related_provisions(self, provision_ids: List[str], max_depth: int = 1) -> Set[str]:
        """
        Finds neighbor provisions in the graph for a given set of input provisions.
        Includes base-provision matching (e.g., CGST_SEC_17_5 triggers lookups for CGST_SEC_17).
        """
        related = set()
        queue = list(set(provision_ids))
        
        visited = set(queue)
        for _ in range(max_depth):
            next_queue = []
            for node in queue:
                # 1. Direct Neighbor Lookup
                neighbors = self.adj_list.get(node, []).copy()
                
                # 2. Base Provision Lookup (if node is SEC_17_5, look up SEC_17)
                if "_SEC_" in node or "_RUL_" in node:
                    parts = node.split("_")
                    if len(parts) > 3: # Has sub-parts
                        base_node = "_".join(parts[:3])
                        neighbors.extend(self.adj_list.get(base_node, []))
                
                for n in neighbors:
                    if n["target"] not in visited:
                        visited.add(n["target"])
                        related.add(n["target"])
                        next_queue.append(n["target"])
            queue = next_queue
            
        return related

    def expand_results(self, chunks: List[Dict], provision_ids: List[str], max_depth: int = 1) -> List[Dict]:
        """
        Expands the search set by finding chunks that match related provisions in the graph.
        """
        if not provision_ids:
            return []
            
        related_ids = self.get_related_provisions(provision_ids, max_depth)
        if not related_ids:
            return []
            
        # Find chunks in the corpus that match these related IDs
        expanded_chunks = self.search_by_provisions(chunks, related_ids)
        return expanded_chunks

    def search_by_provisions(self, chunks: List[Dict[str, Any]], target_provisions: Set[str]) -> List[Dict[str, Any]]:
        """
        Filters chunks based on target provision presence using prefix matching.
        """
        results = []
        for chunk in chunks:
            # Check if any citation matches a related ID using prefix match
            chunk_citations = chunk.get("metadata", {}).get("citations", [])
            # Match if any citation starts with any target provision
            # This ensures SEC_17_5 matches a request for SEC_17 expansion
            if any(any(cit.startswith(target) for target in target_provisions) for cit in chunk_citations):
                results.append(chunk)
        return results
