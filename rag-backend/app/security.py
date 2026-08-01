from datetime import datetime, timedelta, timezone
import os
import logging
import jwt

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

from typing import Optional

from app.database import get_user_collection

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# JWT CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-only-insecure-key-do-not-use-in-production"
)
ADMIN_MASTER_SECRET = os.getenv("ADMIN_MASTER_SECRET", "")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ─────────────────────────────────────────────────────────────────────────────
# TOKEN GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def create_refresh_token(data: dict) -> str:

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

# ─────────────────────────────────────────────────────────────────────────────
# TOKEN VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def verify_token(
    token: str,
    token_type: str = "access"
) -> dict:

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}"
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# ─────────────────────────────────────────────────────────────────────────────
# CURRENT USER
# ─────────────────────────────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> dict:

    logger.debug("Verifying JWT")
    payload = verify_token(token, "access")

    username = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    users_col = get_user_collection()

    if users_col is None:
        # DB not reachable — allow in dev with minimal identity
        if username == "admin" and ADMIN_MASTER_SECRET:
            return {
                "id": "admin",
                "username": "admin",
                "email": "admin@letatec.com",
                "role": "admin",
            }
        return {"username": username, "role": "user", "verified": True}

    user = users_col.find_one(
        {"username": username},
        {
            "_id": 0,
            "password": 0,
        }
    )

    if not user and username == "admin" and ADMIN_MASTER_SECRET:
        return {
            "id": "admin",
            "username": "admin",
            "email": "admin@letatec.com",
            "role": "admin",
        }

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Enforce plan-based session window (admin is exempt)
    if user.get("role") != "admin":
        session_end = user.get("session_end")
        if session_end is not None:
            # MongoDB returns naive datetimes; treat as UTC
            if session_end.tzinfo is None:
                session_end = session_end.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > session_end:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired. Please log in again."
                )

    return user

# ─────────────────────────────────────────────────────────────────────────────
# ROLE & PERMISSION DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"

ADMIN_ROLES = {ROLE_ADMIN, ROLE_SUPER_ADMIN}

# Role Hierarchy Definition:
# USER (low) -> ADMIN (mid) -> SUPER_ADMIN (high)

def has_role(user: dict, role: str) -> bool:
    """Check if the user is explicitly matching a given role."""
    return user.get("role") == role

def is_admin(user: dict) -> bool:
    """Check if the user holds admin or higher administrative privilege."""
    return user.get("role") in ADMIN_ROLES

def is_super_admin(user: dict) -> bool:
    """Check if the user holds super_admin privileges."""
    return user.get("role") == ROLE_SUPER_ADMIN

def require_roles(*allowed_roles: str):
    """Generic role verification dependency injection factory."""
    async def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            logger.warning(
                f"Access denied | user={current_user.get('username')} role={current_user.get('role')} "
                f"required={allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Action not authorized due to insufficient role permissions"
            )
        return current_user
    return dependency

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN AUTH
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin clearance required"
        )
    return current_user

async def get_jwt_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Like get_current_user but skips session_end check — used for payment verify
    so users with expired sessions can still renew by purchasing a new plan."""
    payload = verify_token(token, "access")
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    from app.database import get_user_collection
    users_col = get_user_collection()
    if users_col is not None:
        user = users_col.find_one({"username": username}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    return {"username": username, "role": "user", "verified": True}
