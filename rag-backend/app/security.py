from datetime import datetime, timedelta, timezone
import os
import logging
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    _env = os.getenv("ENVIRONMENT", "development").lower()
    if _env in ("production", "prod", "staging"):
        raise RuntimeError(
            "FATAL: SECRET_KEY environment variable is not set. "
            "Refusing to start in production with an empty secret. "
            "Set SECRET_KEY to a strong random string (e.g. `openssl rand -hex 32`)."
        )
    # Development fallback — logged as warning so it's never silent
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    logger.warning(
        "SECRET_KEY not set — using insecure development default. "
        "Set SECRET_KEY env var before deploying."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7   # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/verify-otp")


# ── JWT helpers ────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT and returns the full user document from MongoDB.
    Raises 401 if token is missing, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identifier: str = payload.get("sub")
        if not identifier:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    from app.database import get_user_collection
    users_col = get_user_collection()
    if users_col is None:
        raise credentials_exception

    user = users_col.find_one(
        {"$or": [{"email": identifier}, {"phone": identifier}]},
        {"_id": 0}
    )
    if not user:
        raise credentials_exception

    return user


async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Requires the authenticated user to have role='admin'. Returns 403 otherwise."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
