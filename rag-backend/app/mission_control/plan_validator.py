import logging
from typing import List, Dict, Set
from app.mission_control.schemas import (
    ExecutionPlan, ExecutionStep, ValidationError, DependencyError,
    ToolNotFoundError, ParameterError
)
from app.mission_control.registry import get_tool_info

logger = logging.getLogger(__name__)

class PlanValidator:
    """Validator layer confirming graph integrity, cycle-free dependencies, and parameter constraints."""
    
    @staticmethod
    def validate_and_sort(plan: ExecutionPlan) -> List[List[ExecutionStep]]:
        """
        Validates the plan and sorts execution steps into grouped parallel levels.
        Raises:
            ValidationError (MC-4001) on duplicate IDs or missing targets
            DependencyError (MC-1001) on cycle detections
            ToolNotFoundError (MC-3001) on referenced tools missing
            ParameterError (MC-4002) on missing required params
        """
        if not plan.steps:
            return []
            
        step_map: Dict[str, ExecutionStep] = {}
        adjacency: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}
        
        # 1. Check duplicate step IDs
        for step in plan.steps:
            if step.id in step_map:
                raise ValidationError(f"Duplicate step ID found: '{step.id}'")
            step_map[step.id] = step
            adjacency[step.id] = []
            in_degree[step.id] = 0
            
        # 2. Check missing tool reference and validate parameters
        for step in plan.steps:
            info = get_tool_info(step.tool)
            if not info:
                raise ToolNotFoundError(f"Referenced tool '{step.tool}' not found in registry.")
                
            for param in info.parameters:
                val = step.parameters.get(param.name, param.default)
                if param.required and val is None:
                    raise ParameterError(f"Missing required parameter '{param.name}' for tool '{step.tool}'.")
                    
        # 3. Check missing dependency references and build graph
        for step in plan.steps:
            for dep in step.depends_on:
                if dep not in step_map:
                    raise ValidationError(f"Step '{step.id}' references a missing dependency: '{dep}'")
                # Graph direction: dependency -> dependent (dep is executed BEFORE step)
                adjacency[dep].append(step.id)
                in_degree[step.id] += 1
                
        # 4. Topological Sort Grouped Execution Levels
        levels: List[List[ExecutionStep]] = []
        visited_count = 0
        
        # Level-by-level processing
        current_queue: List[str] = [sid for sid in step_map if in_degree[sid] == 0]
        
        while current_queue:
            next_queue: List[str] = []
            level_steps: List[ExecutionStep] = []
            
            for sid in current_queue:
                level_steps.append(step_map[sid])
                visited_count += 1
                
                for neighbor in adjacency[sid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
                        
            levels.append(level_steps)
            current_queue = next_queue
            
        # 5. Cycle Detection
        if visited_count != len(plan.steps):
            raise DependencyError("Circular dependency detected in execution plan.")
            
        return levels
