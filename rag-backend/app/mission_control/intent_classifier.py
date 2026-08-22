from app.mission_control.schemas import Intent

class IntentClassifier:
    """Deterministic prompt classifier mapping keywords to execution intents."""
    
    @staticmethod
    def classify(prompt: str) -> Intent:
        prompt_lower = prompt.lower().strip()
        
        if "health" in prompt_lower or "platform health" in prompt_lower:
            return Intent(name="system.health", confidence=1.0)
            
        if "stats" in prompt_lower or "knowledge base" in prompt_lower:
            return Intent(name="knowledge.stats", confidence=1.0)
            
        return Intent(name="general", confidence=0.0)
