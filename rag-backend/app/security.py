from datetime import datetime, timedelta, timezone
import os
import logging
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )
SECRET_KEY: str = _secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ── JWT helpers ────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, token_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
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

    # DB not reachable — allow in dev with minimal identity
    return {"username": username, "role": "user", "verified": True}

async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin clearance required")
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
