import time
import logging
import uuid
from typing import Dict, Any, List
from app.mission_control.schemas import (
    MissionControlResult, Intent, ExecutionPlan, Observation, ObservationLevel,
    PermissionDeniedError, ValidationError, MissionControlError
)
from app.mission_control.intent_classifier import IntentClassifier
from app.mission_control.planner import ExecutionPlanner
from app.mission_control.plan_validator import PlanValidator
from app.mission_control.permissions import PermissionEngine
from app.mission_control.executor import ExecutionEngine
from app.mission_control.registry import get_tool_info, list_tools, record_telemetry_metrics
from app.mission_control.memory import SessionMemoryManager

logger = logging.getLogger(__name__)

# Single instance session manager for application scope
session_memory_manager = SessionMemoryManager()

class MissionControlController:
    """Core entry point executing Pipeline: Classification -> Planner -> Validator -> Preflight -> Executor."""
    
    @classmethod
    async def process_request(
        cls,
        prompt: str,
        user: Dict[str, Any],
        session_id: str,
        correlation_id: str = None,
        dry_run: bool = False
    ) -> MissionControlResult:
        
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        corr_id = correlation_id or f"corr_{uuid.uuid4().hex[:8]}"
        
        start_overall = time.monotonic()
        
        # 1. Intent Classification
        start_planning = time.monotonic()
        intent = IntentClassifier.classify(prompt)
        
        # 2. Build Plan
        plan = ExecutionPlanner.plan(intent)
        planning_duration = int((time.monotonic() - start_planning) * 1000)
        
        # Unknown intent handling
        if intent.name == "general" or not plan.steps:
            all_tools = [t.name for t in list_tools()]
            words = prompt.lower().split()
            first_word = words[0] if words else ""
            suggestions = [t for t in all_tools if t.startswith(first_word) or first_word in t]
            if not suggestions:
                suggestions = all_tools[:3]
                
            overall_duration = int((time.monotonic() - start_overall) * 1000)
            
            # Record validator failure telemetry
            record_telemetry_metrics(success=False, execution_time_ms=0.0, is_val_failure=True)
            
            # Return structured skipped plan
            trace_id = f"tr_{uuid.uuid4().hex[:8]}"
            obs = Observation(
                trace_id=trace_id,
                request_id=request_id,
                execution_id=execution_id,
                step_id="unknown",
                tool_name="unknown",
                success=False,
                level=ObservationLevel.WARNING,
                error=f"Unknown intent classified for prompt: '{prompt}'",
                error_code="MC-4001",
                data={"suggested_commands": suggestions, "prompt": prompt, "confidence": intent.confidence}
            )
            
            return MissionControlResult(
                plan=plan,
                observations=[obs],
                events=[],
                success=False,
                planning_duration_ms=planning_duration,
                validation_duration_ms=0,
                execution_duration_ms=0,
                observation_generation_duration_ms=overall_duration - planning_duration
            )

        # 3. Plan Validation (Topological Sort execution levels)
        start_validation = time.monotonic()
        try:
            levels = PlanValidator.validate_and_sort(plan)
        except MissionControlError as e:
            overall_duration = int((time.monotonic() - start_overall) * 1000)
            record_telemetry_metrics(success=False, execution_time_ms=0.0, is_val_failure=True)
            
            trace_id = f"tr_{uuid.uuid4().hex[:8]}"
            obs = Observation(
                trace_id=trace_id,
                request_id=request_id,
                execution_id=execution_id,
                step_id="validation",
                tool_name="validator",
                success=False,
                level=ObservationLevel.ERROR,
                error=e.message,
                error_code=e.error_code
            )
            return MissionControlResult(
                plan=plan,
                observations=[obs],
                events=[],
                success=False,
                planning_duration_ms=planning_duration,
                validation_duration_ms=int((time.monotonic() - start_validation) * 1000),
                execution_duration_ms=0,
                observation_generation_duration_ms=overall_duration - planning_duration
            )
            
        validation_duration = int((time.monotonic() - start_validation) * 1000)
        
        # 4. Permission Preflight Clearance Verification
        start_preflight = time.monotonic()
        for step in plan.steps:
            info = get_tool_info(step.tool)
            # Checked in validator
            assert info is not None
            
            allowed = PermissionEngine.check_permissions(user, info.permissions)
            if not allowed:
                preflight_duration = int((time.monotonic() - start_preflight) * 1000)
                overall_duration = int((time.monotonic() - start_overall) * 1000)
                record_telemetry_metrics(success=False, execution_time_ms=0.0, is_perm_denial=True)
                
                trace_id = f"tr_{uuid.uuid4().hex[:8]}"
                obs = Observation(
                    trace_id=trace_id,
                    request_id=request_id,
                    execution_id=execution_id,
                    step_id=step.id,
                    tool_name=step.tool,
                    success=False,
                    level=ObservationLevel.ERROR,
                    error=f"Permission preflight check failed for tool '{step.tool}'. User is unauthorized.",
                    error_code="MC-2001"
                )
                return MissionControlResult(
                    plan=plan,
                    observations=[obs],
                    events=[],
                    success=False,
                    planning_duration_ms=planning_duration,
                    validation_duration_ms=validation_duration,
                    permission_check_duration_ms=preflight_duration,
                    execution_duration_ms=0,
                    observation_generation_duration_ms=overall_duration - planning_duration - validation_duration - preflight_duration
                )
                
        preflight_duration = int((time.monotonic() - start_preflight) * 1000)
        
        # 5. Graph Execution Engine runs
        start_execution = time.monotonic()
        observations, events, execution_metrics, success = await ExecutionEngine.execute(
            plan=plan,
            levels=levels,
            user=user,
            session_id=session_id,
            memory_manager=session_memory_manager,
            request_id=request_id,
            execution_id=execution_id,
            correlation_id=corr_id,
            dry_run=dry_run
        )
        execution_duration = int((time.monotonic() - start_execution) * 1000)
        
        # 6. Save results to Session Memory
        session = session_memory_manager.get_session(session_id)
        session.last_plan = plan
        session.last_observations = observations
        session.conversation_history.append({
            "prompt": prompt,
            "success": success,
            "observations_count": len(observations)
        })
        
        overall_duration = int((time.monotonic() - start_overall) * 1000)
        
        return MissionControlResult(
            plan=plan,
            observations=observations,
            events=events,
            success=success,
            planning_duration_ms=planning_duration,
            validation_duration_ms=validation_duration,
            permission_check_duration_ms=preflight_duration,
            execution_duration_ms=execution_duration,
            observation_generation_duration_ms=overall_duration - planning_duration - validation_duration - preflight_duration - execution_duration,
            **execution_metrics
        )
