from app.mission_control.controller import MissionControlController
from app.mission_control.registry import discover_tools

# Auto discover all tool submodules inside tools folder on initialization
discover_tools(["app.mission_control.tools"])
