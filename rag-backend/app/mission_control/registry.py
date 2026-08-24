import sys
import importlib
import pkgutil
import logging
from typing import Callable, Dict, List, Optional, Any
from app.mission_control.schemas import ToolInfo, ToolCategory, RegistryValidationError

logger = logging.getLogger(__name__)

# Registry databases
_registry: Dict[str, ToolInfo] = {}
_handlers: Dict[str, Callable] = {}
_telemetry_metrics: Dict[str, Any] = {
    "failures_count": 0,
    "success_count": 0,
    "avg_execution_time_ms": 0.0,
    "total_execution_time_ms": 0.0,
    "permission_denials": 0,
    "validator_failures": 0
}

def register_tool(info: ToolInfo):
    """Decorator to register a tool and its handler, failing fast on conflicts or invalid properties."""
    def decorator(handler: Callable):
        # 1. Reject duplicate registrations
        if info.name in _registry:
            raise RegistryValidationError(f"Duplicate tool name registration rejected: '{info.name}'")
            
        # 2. Validate basic metadata
        if not info.name or not info.display_name or not info.description:
            raise RegistryValidationError(f"Invalid tool metadata for '{info.name}'. Fields 'display_name' and 'description' must not be empty.")
            
        if not isinstance(info.category, ToolCategory):
            raise RegistryValidationError(f"Invalid category '{info.category}' for tool '{info.name}'. Must be a ToolCategory Enum.")
            
        # 3. Check version compatibility
        if info.framework_version != "v3":
            raise RegistryValidationError(f"Incompatible framework version '{info.framework_version}' for tool '{info.name}'. Expected 'v3'.")
            
        # 4. Save to registry
        _registry[info.name] = info
        _handlers[info.name] = handler
        logger.info(f"Registered tool: {info.name} ({info.display_name})")
        return handler
    return decorator

def get_tool_info(name: str) -> Optional[ToolInfo]:
    return _registry.get(name)

def get_tool_handler(name: str) -> Optional[Callable]:
    return _handlers.get(name)

def list_tools() -> List[ToolInfo]:
    return list(_registry.values())

def clear_registry():
    _registry.clear()
    _handlers.clear()
    _telemetry_metrics.update({
        "failures_count": 0,
        "success_count": 0,
        "avg_execution_time_ms": 0.0,
        "total_execution_time_ms": 0.0,
        "permission_denials": 0,
        "validator_failures": 0
    })

def discover_tools(package_names: List[str]):
    """Extensible tool auto-discovery scanning packages and all submodules recursively."""
    for package_name in package_names:
        try:
            package = importlib.import_module(package_name)
        except Exception as e:
            logger.error(f"Failed to import package for tool discovery {package_name}: {e}")
            continue

        if not hasattr(package, "__path__"):
            logger.warning(f"Package {package_name} does not have __path__, skipping recursive scan")
            continue

        for _, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
                logger.debug(f"Discovered and imported module: {module_name}")
            except Exception as e:
                # Re-raise RegistryValidationError to fail fast at startup
                if isinstance(e, RegistryValidationError):
                    raise
                logger.error(f"Error importing module {module_name} during tool discovery: {e}")

    # Self-validate whole registry integrity after discovery
    self_validate_registry()

def self_validate_registry():
    """Verify that every tool has an associated handler and correct configurations."""
    for name, info in _registry.items():
        if name not in _handlers:
            raise RegistryValidationError(f"Missing handler function for registered tool: '{name}'")
        for p in info.parameters:
            if not p.name or not p.type:
                raise RegistryValidationError(f"Invalid parameter configuration on tool: '{name}'")

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH & OBSERVABILITY TELEMETRY
# ─────────────────────────────────────────────────────────────────────────────

def get_mission_control_health() -> dict:
    """Internal health report for the orchestration framework."""
    loaded_capabilities = set()
    for tool in _registry.values():
        loaded_capabilities.update(tool.capabilities)
        
    return {
        "registered_tool_count": len(_registry),
        "loaded_capabilities": list(loaded_capabilities),
        "failures_count": _telemetry_metrics["failures_count"],
        "success_count": _telemetry_metrics["success_count"],
        "avg_execution_time_ms": _telemetry_metrics["avg_execution_time_ms"],
        "permission_denials": _telemetry_metrics["permission_denials"],
        "validator_failures": _telemetry_metrics["validator_failures"]
    }

def record_telemetry_metrics(success: bool, execution_time_ms: float, is_perm_denial: bool = False, is_val_failure: bool = False):
    if not success:
        _telemetry_metrics["failures_count"] += 1
    else:
        _telemetry_metrics["success_count"] += 1
        
    if is_perm_denial:
        _telemetry_metrics["permission_denials"] += 1
    if is_val_failure:
        _telemetry_metrics["validator_failures"] += 1
        
    _telemetry_metrics["total_execution_time_ms"] += execution_time_ms
    total_runs = _telemetry_metrics["failures_count"] + _telemetry_metrics["success_count"]
    if total_runs > 0:
        _telemetry_metrics["avg_execution_time_ms"] = _telemetry_metrics["total_execution_time_ms"] / total_runs
