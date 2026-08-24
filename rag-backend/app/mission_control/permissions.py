import logging
from typing import Dict, Any, List
from app.security import ROLE_USER, ROLE_ADMIN, ROLE_SUPER_ADMIN

logger = logging.getLogger(__name__)

ROLE_LEVELS: Dict[str, int] = {
    ROLE_USER: 1,
    ROLE_ADMIN: 2,
    ROLE_SUPER_ADMIN: 3
}

class PermissionEngine:
    """Deterministic security layer validating user clearance against tool permissions."""
    
    @staticmethod
    def check_permissions(user: Dict[str, Any], required_permissions: List[str]) -> bool:
        # If no permissions required, access is open
        if not required_permissions:
            return True
            
        user_role = user.get("role", ROLE_USER)
        user_level = ROLE_LEVELS.get(user_role, 0)
        
        # Explicit match or hierarchical clearance check
        for req in required_permissions:
            if user_role == req:
                return True
            req_level = ROLE_LEVELS.get(req, 99)
            if user_level >= req_level:
                return True
                
        logger.warning(f"Clearance rejected: user={user.get('username')} role={user_role} required={required_permissions}")
        return False
