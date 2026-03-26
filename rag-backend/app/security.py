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
    BYPASSED FOR TESTING: Returns a dummy admin user.
    """
    return {
        "username": "guest_admin",
        "email": "admin@example.com",
        "role": "admin",
        "verified": True
    }


async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """BYPASSED: Everyone is admin."""
    return current_user
