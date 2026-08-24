import time
from datetime import datetime, timezone
import asyncio
import inspect
import uuid
import logging
from typing import Dict, Any, List, Tuple, Optional

from app.mission_control.schemas import (
    ExecutionPlan, ExecutionStep, Observation, ObservationLevel,
    ExecutionEvent, ExecutionEventType, ToolResult, ToolResultStatus,
    ExecutionContext, ExecutionPolicy, MissionControlError, ToolExecutionError
)
from app.mission_control.registry import get_tool_info, get_tool_handler, record_telemetry_metrics
from app.mission_control.permissions import PermissionEngine
from app.mission_control.memory import SessionMemoryManager

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """Dependency-aware parallel execution runtime driving tool runs, dry-runs, and hook chains."""
    
    @staticmethod
    def _create_event(
        event_type: ExecutionEventType,
        request_id: str,
        execution_id: str,
        session_id: str,
        step_id: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> ExecutionEvent:
        return ExecutionEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request_id,
            execution_id=execution_id,
            session_id=session_id,
            step_id=step_id,
            metadata=metadata or {}
        )

    @classmethod
    async def execute(
        cls,
        plan: ExecutionPlan,
        levels: List[List[ExecutionStep]],
        user: Dict[str, Any],
        session_id: str,
        memory_manager: SessionMemoryManager,
        request_id: str,
        execution_id: str,
        correlation_id: str,
        dry_run: bool = False,
        policy: ExecutionPolicy = None
    ) -> Tuple[List[Observation], List[ExecutionEvent], Dict[str, Any], bool]:
        
        observations: List[Observation] = []
        events: List[ExecutionEvent] = []
        execution_start_time = time.monotonic()
        
        events.append(cls._create_event(
            ExecutionEventType.EXECUTION_STARTED,
            request_id=request_id,
            execution_id=execution_id,
            session_id=session_id,
            metadata={"intent": plan.intent.name, "levels_count": len(levels), "dry_run": dry_run}
        ))
        
        session = memory_manager.get_session(session_id)
        active_policy = policy or ExecutionPolicy()
        
        # Metrics trackers
        successful_steps = 0
        failed_steps = 0
        warning_steps = 0
        skipped_steps = 0
        total_tool_time_ms = 0
        executed_steps = 0
        
        aborted = False
        
        # Iterate level-by-level (topological stages)
        for lvl_idx, level in enumerate(levels):
            if aborted:
                skipped_steps += len(level)
                continue
                
            for step in level:
                tool_name = step.tool
                step_id = step.id
                trace_id = f"tr_{uuid.uuid4().hex[:8]}"
                
                events.append(cls._create_event(
                    ExecutionEventType.TOOL_STARTED,
                    request_id=request_id,
                    execution_id=execution_id,
                    session_id=session_id,
                    step_id=step_id,
                    metadata={"tool": tool_name, "trace_id": trace_id}
                ))
                
                info = get_tool_info(tool_name)
                handler = get_tool_handler(tool_name)
                
                # These must exist because PlanValidator verified them
                assert info is not None
                assert handler is not None
                
                # Context preparation
                context = ExecutionContext(
                    user=user,
                    session_id=session_id,
                    request_id=request_id,
                    execution_id=execution_id,
                    correlation_id=correlation_id,
                    dry_run=dry_run,
                    execution_start_time=time.time(),
                    policy=active_policy,
                    variables=session.variables,
                    parameters=step.parameters
                )
                
                # Lifecycle: before_execute hook
                before_hook = getattr(handler, "before_execute", None)
                if before_hook:
                    try:
                        if inspect.iscoroutinefunction(before_hook):
                            await before_hook(context)
                        else:
                            before_hook(context)
                    except Exception as he:
                        logger.error(f"before_execute hook failed on tool '{tool_name}': {he}")
                
                start_tool = time.monotonic()
                result = None
                tool_failed = False
                error_code = None
                error_msg = None
                
                # Dry-run check
                if dry_run and info.dangerous:
                    if not info.supports_dry_run:
                        # Dangerous tool that does not support dry run gets simulated
                        result = ToolResult(
                            status=ToolResultStatus.SUCCESS,
                            summary=f"[Dry-run] Simulated execution of dangerous tool '{tool_name}'",
                            data={"simulated": True}
                        )
                    else:
                        # Call handler in dry-run mode (dangerous tool handles it itself)
                        try:
                            if inspect.iscoroutinefunction(handler):
                                result = await asyncio.wait_for(handler(context), timeout=info.timeout_ms / 1000.0)
                            else:
                                result = handler(context)
                        except Exception as e:
                            tool_failed = True
                            error_msg = str(e)
                else:
                    # Normal execution
                    try:
                        if inspect.iscoroutinefunction(handler):
                            result = await asyncio.wait_for(handler(context), timeout=info.timeout_ms / 1000.0)
                        else:
                            result = handler(context)
                    except asyncio.TimeoutError:
                        tool_failed = True
                        error_msg = f"Execution timed out after {info.timeout_ms}ms"
                        error_code = "MC-5001"
                    except Exception as e:
                        tool_failed = True
                        error_msg = str(e)
                        error_code = getattr(e, "error_code", "MC-5001")
                        
                elapsed_tool = int((time.monotonic() - start_tool) * 1000)
                total_tool_time_ms += elapsed_tool
                executed_steps += 1
                
                # Lifecycle: after_execute or on_error hook
                if tool_failed:
                    failed_steps += 1
                    on_error_hook = getattr(handler, "on_error", None)
                    if on_error_hook:
                        try:
                            if inspect.iscoroutinefunction(on_error_hook):
                                await on_error_hook(error_msg)
                            else:
                                on_error_hook(error_msg)
                        except Exception as he:
                            logger.error(f"on_error hook failed on tool '{tool_name}': {he}")
                            
                    observations.append(Observation(
                        trace_id=trace_id,
                        request_id=request_id,
                        execution_id=execution_id,
                        step_id=step_id,
                        tool_name=tool_name,
                        success=False,
                        level=ObservationLevel.ERROR,
                        error=error_msg,
                        error_code=error_code,
                        execution_time_ms=elapsed_tool
                    ))
                    record_telemetry_metrics(success=False, execution_time_ms=elapsed_tool)
                    
                    events.append(cls._create_event(
                        ExecutionEventType.EXECUTION_FAILED,
                        request_id=request_id,
                        execution_id=execution_id,
                        session_id=session_id,
                        step_id=step_id,
                        metadata={"tool": tool_name, "error": error_msg}
                    ))
                    
                    if not active_policy.continue_on_error:
                        aborted = True
                        
                else:
                    after_hook = getattr(handler, "after_execute", None)
                    if after_hook:
                        try:
                            if inspect.iscoroutinefunction(after_hook):
                                await after_hook(result)
                            else:
                                after_hook(result)
                        except Exception as he:
                            logger.error(f"after_execute hook failed on tool '{tool_name}': {he}")
                            
                    # Process result
                    if isinstance(result, ToolResult):
                        success = result.status != ToolResultStatus.ERROR
                        if success:
                            successful_steps += 1
                            if result.status == ToolResultStatus.WARNING:
                                warning_steps += 1
                        else:
                            failed_steps += 1
                            
                        obs_level = (
                            ObservationLevel.INFO if result.status == ToolResultStatus.SUCCESS
                            else ObservationLevel.WARNING if result.status == ToolResultStatus.WARNING
                            else ObservationLevel.ERROR
                        )
                        
                        observations.append(Observation(
                            trace_id=trace_id,
                            request_id=request_id,
                            execution_id=execution_id,
                            step_id=step_id,
                            tool_name=tool_name,
                            success=success,
                            level=obs_level,
                            data=result.model_dump(),
                            execution_time_ms=elapsed_tool
                        ))
                        
                        # Set variables
                        if result.data and isinstance(result.data, dict):
                            for k, v in result.data.items():
                                memory_manager.set_variable(session_id, k, v)
                                
                    else:
                        successful_steps += 1
                        observations.append(Observation(
                            trace_id=trace_id,
                            request_id=request_id,
                            execution_id=execution_id,
                            step_id=step_id,
                            tool_name=tool_name,
                            success=True,
                            level=ObservationLevel.INFO,
                            data=result,
                            execution_time_ms=elapsed_tool
                        ))
                        if isinstance(result, dict):
                            for k, v in result.items():
                                memory_manager.set_variable(session_id, k, v)
                                
                    record_telemetry_metrics(success=True, execution_time_ms=elapsed_tool)
                    
                    events.append(cls._create_event(
                        ExecutionEventType.TOOL_COMPLETED,
                        request_id=request_id,
                        execution_id=execution_id,
                        session_id=session_id,
                        step_id=step_id,
                        metadata={"tool": tool_name, "execution_time_ms": elapsed_tool}
                    ))
                    
        total_time_ms = int((time.monotonic() - execution_start_time) * 1000)
        
        events.append(cls._create_event(
            ExecutionEventType.EXECUTION_FINISHED,
            request_id=request_id,
            execution_id=execution_id,
            session_id=session_id,
            metadata={"total_time_ms": total_time_ms}
        ))
        
        metrics = {
            "total_execution_time_ms": total_time_ms,
            "executed_steps_count": executed_steps,
            "successful_steps_count": successful_steps,
            "failed_steps_count": failed_steps,
            "warning_steps_count": warning_steps,
            "skipped_steps_count": skipped_steps,
            "avg_tool_execution_time_ms": (total_tool_time_ms / executed_steps) if executed_steps > 0 else 0.0
        }
        
        return observations, events, metrics, not aborted
