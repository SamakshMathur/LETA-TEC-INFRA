import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Any

logger = logging.getLogger(__name__)


def _provision_matches(citation: str, target: str) -> bool:
    """
    Checks if a citation matches a target provision without greedy prefix overlap.

    SEC_17 should match SEC_17, SEC_17_5, SEC_17A — but NOT SEC_170, SEC_179.
    Uses boundary-aware matching: target must be followed by end-of-string, '_', or
    a letter (for subsection suffixes like 17A).
    """
    if citation == target:
        return True
    if not citation.startswith(target):
        return False
    # Character after the target must be '_' (subsection separator) or a letter (e.g. 17A)
    suffix = citation[len(target):]
    return suffix[0] in ('_',) or (suffix[0].isalpha() and not suffix[0].isdigit())


class ProvisionGraphRetriever:
    """
    Handles Provision-Graph Retrieval (Neighbor Expansion).
    Models relationships between statutes, rules, circulars, and case law.
    """
    def __init__(self, edges_path: Path):
        self.edges_path = edges_path
        self.adj_list: Dict[str, List[Dict[str, str]]] = {}
        self._edge_count = 0
        self.load_graph()

    def load_graph(self):
        if not self.edges_path.exists():
            logger.warning(f"Provision Graph edges not found at {self.edges_path} — graph expansion disabled")
            return

        try:
            with open(self.edges_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        edge = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(f"Malformed JSON at line {line_num} in edges.jsonl — skipped")
                        continue

                    src = edge.get("source")
                    tgt = edge.get("target")
                    relation = edge.get("relation", "RELATED_TO")

                    if not src or not tgt:
                        logger.warning(f"Edge missing source/target at line {line_num} — skipped")
                        continue

                    self.adj_list.setdefault(src, []).append({"target": tgt, "relation": relation})
                    self._edge_count += 1

                    # Bi-directional for symmetric relations
                    if relation in ("RELATED_TO", "CO_IMPLEMENTED"):
                        self.adj_list.setdefault(tgt, []).append({"target": src, "relation": relation})

            logger.info(f"Provision Graph loaded: {self._edge_count} edges, {len(self.adj_list)} nodes")
        except Exception as e:
            logger.error(f"Failed to load provision graph: {e}", exc_info=True)

    def get_related_provisions(self, provision_ids: List[str], max_depth: int = 1) -> Set[str]:
        """
        BFS neighbor expansion with cycle prevention.
        Includes base-provision matching (e.g., CGST_SEC_17_5 triggers lookups for CGST_SEC_17).
        """
        if not provision_ids or not self.adj_list:
            return set()

        related = set()
        queue = list(set(provision_ids))
        visited = set(queue)

        for depth in range(max_depth):
            next_queue = []
            for node in queue:
                # 1. Direct neighbor lookup
                neighbors = list(self.adj_list.get(node, []))

                # 2. Base provision lookup (SEC_17_5 → also check SEC_17)
                if "_SEC_" in node or "_RUL_" in node:
                    parts = node.split("_")
                    if len(parts) > 3:
                        base_node = "_".join(parts[:3])
                        if base_node != node:
                            neighbors.extend(self.adj_list.get(base_node, []))

                for n in neighbors:
                    target = n["target"]
                    if target not in visited:
                        visited.add(target)
                        related.add(target)
                        next_queue.append(target)

            queue = next_queue
            if not queue:
                break  # No more nodes to expand

        logger.debug(f"Graph expansion: {provision_ids} → {len(related)} related provisions (depth={max_depth})")
        return related

    def expand_results(self, chunks: List[Dict], provision_ids: List[str], max_depth: int = 1) -> List[Dict]:
        """Expands the search set by finding chunks that match related provisions."""
        if not provision_ids:
            return []

        related_ids = self.get_related_provisions(provision_ids, max_depth)
        if not related_ids:
            return []

        expanded_chunks = self.search_by_provisions(chunks, related_ids)
        logger.debug(f"Graph expansion found {len(expanded_chunks)} additional chunks")
        return expanded_chunks

    def search_by_provisions(self, chunks: List[Dict[str, Any]], target_provisions: Set[str]) -> List[Dict[str, Any]]:
        """
        Filters chunks based on target provision presence using boundary-aware matching.
        SEC_17 matches SEC_17, SEC_17_5, SEC_17A — but NOT SEC_170 or SEC_179.
        """
        results = []
        for chunk in chunks:
            chunk_citations = chunk.get("metadata", {}).get("citations", [])
            if any(
                _provision_matches(cit, target)
                for cit in chunk_citations
                for target in target_provisions
            ):
                results.append(chunk)
        return results
