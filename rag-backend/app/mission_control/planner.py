import uuid
from app.mission_control.schemas import Intent, ExecutionPlan, ExecutionStep

class ExecutionPlanner:
    """Orchestrator resolving intents into dependency-mapped execution plans."""
    
    @staticmethod
    def plan(intent: Intent) -> ExecutionPlan:
        steps = []
        complexity = 0.0
        
        if intent.name == "system.health":
            step_id = f"step_{uuid.uuid4().hex[:6]}"
            steps.append(ExecutionStep(
                id=step_id,
                tool="system.health",
                parameters={},
                depends_on=[]
            ))
            complexity = 1.0
            
        elif intent.name == "knowledge.stats":
            step_id = f"step_{uuid.uuid4().hex[:6]}"
            steps.append(ExecutionStep(
                id=step_id,
                tool="knowledge.stats",
                parameters={},
                depends_on=[]
            ))
            complexity = 1.0
            
        return ExecutionPlan(
            steps=steps,
            intent=intent,
            complexity=complexity
        )
