import json
import os
from typing import Dict, Any, Optional

class TruthRules:
    """
    The Single Source of Truth for Hard Coded Legal Facts.
    This works as a 'Rule Engine' to validate LLM outputs against fixed statutory numbers.
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
            # If it's the registry, return empty list, if rules, return empty dict.
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

    def get_all_rules_as_text(self) -> str:
        """
        Returns a string representation of all rules and verified citations to inject into the LLM context.
        This forces the LLM to 'see' the absolute mathematical and legal truth before generating.
        """
        rules_text = "### 🛡️ TRUTH RULES (STATUTORY FACTS & NUMBERS) \n"
        rules_text += "You MUST adhere to these hard-coded numbers over any other source:\n\n"
        
        if self.rules:
            for key, value in self.rules.items():
                rules_text += f"**{key.upper()}**:\n"
                for k, v in value.items():
                    rules_text += f"- {k}: {v}\n"
                rules_text += "\n"
                
        rules_text += "### 🏛️ VERIFIED CITATION REGISTRY (STATUTORY TEXT) \n"
        rules_text += "If the user query relates to any of the specific sections or notifications below, YOU MUST ONLY QUOTE THE TEXT BELOW EXACTLY AS WRITTEN. NO PARAPHRASING IS ALLOWED.\n\n"
        
        if self.registry:
            for cit in self.registry:
                rules_text += f"**{cit.get('Citation', '')} - {cit.get('Title', '')} [{cit.get('Type', '')}]**\n"
                rules_text += f"{cit.get('Law', '')}\n"
                rules_text += f"TEXT: \"{cit.get('Text', '')}\"\n\n"
                
        return rules_text

# Singleton Instance
rules_engine = TruthRules()
