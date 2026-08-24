from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ObservationLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ToolResultStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class ExecutionEventType(str, Enum):
    EXECUTION_STARTED = "ExecutionStarted"
    TOOL_STARTED = "ToolStarted"
    TOOL_COMPLETED = "ToolCompleted"
    PERMISSION_DENIED = "PermissionDenied"
    EXECUTION_FAILED = "ExecutionFailed"
    EXECUTION_FINISHED = "ExecutionFinished"

class ToolCategory(str, Enum):
    SYSTEM = "system"
    KNOWLEDGE = "knowledge"
    ANALYTICS = "analytics"
    AUDIT = "audit"
    CACHE = "cache"
    TEAM = "team"
    BILLING = "billing"
    TEST = "test"

# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURED ERRORS
# ─────────────────────────────────────────────────────────────────────────────

class MissionControlError(Exception):
    """Base exception class for LetaTec Mission Control."""
    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

class DependencyError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-1001")

class PermissionDeniedError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-2001")

class ToolNotFoundError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-3001")

class ValidationError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-4001")

class ParameterError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-4002")

class ToolExecutionError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-5001")

class RegistryValidationError(MissionControlError):
    def __init__(self, message: str):
        super().__init__(message, "MC-6001")

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None

class ToolInfo(BaseModel):
    name: str
    display_name: str
    description: str
    category: ToolCategory
    permissions: List[str]
    parameters: List[ToolParameter] = Field(default_factory=list)
    version: str = "1.0.0"
    api_version: str = "v1"
    framework_version: str = "v3"
    timeout_ms: int = 5000
    tags: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    dangerous: bool = False
    read_only: bool = True
    supports_dry_run: bool = False
    estimated_runtime_ms: int = 100

class ExecutionPolicy(BaseModel):
    continue_on_error: bool = False
    rollback_on_failure: bool = False
    timeout_ms: int = 10000
    max_retries: int = 0

class ExecutionContext(BaseModel):
    user: Dict[str, Any]
    session_id: str
    request_id: str
    execution_id: str
    correlation_id: str
    dry_run: bool = False
    execution_start_time: float
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    variables: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)

class ExecutionStep(BaseModel):
    id: str
    tool: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)

class Intent(BaseModel):
    name: str
    confidence: float
    entities: Dict[str, Any] = Field(default_factory=dict)

class ExecutionPlan(BaseModel):
    steps: List[ExecutionStep] = Field(default_factory=list)
    intent: Intent
    complexity: float = 0.0

class Observation(BaseModel):
    trace_id: str
    request_id: str
    execution_id: str
    step_id: str
    tool_name: str
    success: bool
    level: ObservationLevel = ObservationLevel.INFO
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    execution_time_ms: int = 0

class ToolResult(BaseModel):
    status: ToolResultStatus = ToolResultStatus.SUCCESS
    summary: str
    data: Optional[Any] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)

class ExecutionEvent(BaseModel):
    event_type: ExecutionEventType
    timestamp: str
    request_id: str
    execution_id: str
    session_id: str
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MissionControlResult(BaseModel):
    plan: ExecutionPlan
    observations: List[Observation] = Field(default_factory=list)
    events: List[ExecutionEvent] = Field(default_factory=list)
    success: bool = True
    
    # Detailed execution metrics
    planning_duration_ms: int = 0
    validation_duration_ms: int = 0
    permission_check_duration_ms: int = 0
    execution_duration_ms: int = 0
    observation_generation_duration_ms: int = 0
