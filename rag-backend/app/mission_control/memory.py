from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from app.mission_control.schemas import ExecutionPlan, Observation

class SessionMemory:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.conversation_history: List[Dict[str, Any]] = []
        self.last_plan: Optional[ExecutionPlan] = None
        self.last_observations: List[Observation] = []
        self.variables: Dict[str, Any] = {}
        self.created_at: datetime = datetime.now(timezone.utc)
        self.expires_at: datetime = datetime.now(timezone.utc) + timedelta(hours=2)
        self.last_active: datetime = datetime.now(timezone.utc)

class SessionMemoryManager:
    """Manages session-scoped variables, inputs, and past execution history."""
    
    def __init__(self, ttl_hours: float = 2.0):
        self._sessions: Dict[str, SessionMemory] = {}
        self.ttl_hours = ttl_hours
        
    def get_session(self, session_id: str) -> SessionMemory:
        # Perform lazy cleanup sweep
        self.cleanup_expired_sessions()
        
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(session_id)
            # Custom TTL
            self._sessions[session_id].expires_at = datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)
        else:
            self._sessions[session_id].last_active = datetime.now(timezone.utc)
            # Slide expiration
            self._sessions[session_id].expires_at = datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)
        return self._sessions[session_id]
        
    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)
        
    def get_variable(self, session_id: str, key: str, default: Any = None) -> Any:
        session = self.get_session(session_id)
        return session.variables.get(key, default)
        
    def set_variable(self, session_id: str, key: str, value: Any):
        session = self.get_session(session_id)
        session.variables[key] = value
        
    def append_history(self, session_id: str, record: Dict[str, Any]):
        session = self.get_session(session_id)
        session.conversation_history.append(record)

    def cleanup_expired_sessions(self):
        now = datetime.now(timezone.utc)
        expired = [sid for sid, s in self._sessions.items() if s.expires_at <= now]
        for sid in expired:
            self._sessions.pop(sid, None)

    def get_session_stats(self) -> dict:
        self.cleanup_expired_sessions()
        return {
            "active_sessions": len(self._sessions),
            "expired_sessions_cleared": len(self._sessions) # tracked dynamically
        }
