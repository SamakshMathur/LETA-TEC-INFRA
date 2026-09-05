import logging
import sys
import os

# ─── Logging Configuration (must be first) ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("flashrank").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

import uvicorn
from app.api.app import app
from app.config import validate_config


@app.on_event("startup")
async def startup_event():
    logger.info("LETA/Sentinel.AI starting up...")
    config_ok = validate_config()
    if not config_ok:
        logger.error("Configuration validation failed — check warnings above")
    else:
        logger.info("Configuration validated successfully")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting uvicorn server on 0.0.0.0:{port}")
    try:
        # Using import string "app.api.app:app" is required for reload=True to work
        uvicorn.run("app.api.app:app", host="0.0.0.0", port=port, reload=True)
    except Exception as e:
        logger.critical(f"Uvicorn crashed: {e}", exc_info=True)
        sys.exit(1)
