import json
import os
import re
from typing import Dict, Any, Optional, List

class TruthRules:
    """
    The Verification & Configuration Rules Engine.
    This validates LLM outputs and generated claims against fixed statutory parameters and citation registry.
    """

    def __init__(self, rules_file: str = "data/gst_rules.json", registry_file: str = "data/citation_registry.json"):
        # Resolve absolute path relative to this file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.rules_path = os.path.join(base_dir, "..", rules_file)
        self.registry_path = os.path.join(base_dir, "..", registry_file)

        self.rules = self._load_json(self.rules_path)
        self.registry = self._load_json(self.registry_path)

    def _load_json(self, path: str):
        """Loads a JSON file if it exists."""
        if not os.path.exists(path):
            print(f"[RulesEngine] Warning: File not found at {path}")
            return [] if "registry" in path else {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[RulesEngine] Error loading JSON from {path}: {e}")
            return [] if "registry" in path else {}

    def get_rule(self, rule_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific rule by key."""
        return self.rules.get(rule_key)

    def get_relevant_rules(self, query: str, chunks: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Returns a filtered string representation of rules and verified citations relevant to the query context.
        Bypasses massive context window bloat and zero-hardcoding rules.
        """
        q_lower = query.lower()
        matched_rules = {}
        matched_registry = []

        # Gather all citation numbers/identifiers from chunks metadata
        chunk_citations = set()
        if chunks:
            for c in chunks:
                meta = c.get("metadata", {})
                for cit in meta.get("citations", []):
                    nums = re.findall(r'\d+', cit)
                    chunk_citations.update(nums)
                for prov in meta.get("provisions", []):
                    nums = re.findall(r'\d+', prov)
                    chunk_citations.update(nums)

        # Also extract numbers from query
        query_nums = set(re.findall(r'\d+', q_lower))
        all_target_nums = chunk_citations.union(query_nums)

        # 1. Filter rules based on query keyword triggers
        for rule_key, rule_val in self.rules.items():
            trigger_matched = False

            key_words = rule_key.lower().replace("_", " ").split()
            if any(w in q_lower for w in key_words if len(w) > 2):
                trigger_matched = True

            rule_str = json.dumps(rule_val).lower()
            if any(num in rule_str for num in all_target_nums):
                trigger_matched = True

            if trigger_matched:
                matched_rules[rule_key] = rule_val

        # 2. Filter citation registry based on query and chunks citations
        for cit in self.registry:
            citation_str = cit.get("Citation", "").lower()
            text_str = cit.get("Text", "").lower()

            num_match = False
            for num in all_target_nums:
                if any(x in citation_str for x in [f"section {num}", f"sec {num}", f"rule {num}", f"sec. {num}"]):
                    num_match = True
                    break

            text_match = any(term in q_lower for term in ["itc", "input tax credit", "refund", "registration", "exempt"])

            if num_match or (text_match and any(w in citation_str or w in text_str for w in q_lower.split() if len(w) > 3)):
                matched_registry.append(cit)

        # Format output
        rules_text = "### 🛡️ VERIFICATION & CONFIGURATION CONSTRAINTS\n"
        rules_text += "These are configuration and validation parameters to check generated claims against:\n\n"

        if matched_rules:
            for key, value in matched_rules.items():
                rules_text += f"**{key.upper()}**:\n"
                for k, v in value.items():
                    rules_text += f"- {k}: {v}\n"
                rules_text += "\n"
        else:
            rules_text += "No matching validation rules for this query context.\n\n"

        rules_text += "### 🏛️ VERIFIED CITATION REGISTRY\n"
        rules_text += "Authoritative statutory text snippets to align citation formatting and verify exact wording:\n\n"

        if matched_registry:
            for cit in matched_registry:
                rules_text += f"**{cit.get('Citation', '')} - {cit.get('Title', '')} [{cit.get('Type', '')}]**\n"
                rules_text += f"{cit.get('Law', '')}\n"
                rules_text += f"TEXT: \"{cit.get('Text', '')}\"\n\n"
        else:
            rules_text += "No matching registered citations found for this query context.\n\n"

        return rules_text

    def get_all_rules_as_text(self) -> str:
        """Fallback to matching-all rules representation."""
        return self.get_relevant_rules("")

# Singleton Instance
rules_engine = TruthRules()
