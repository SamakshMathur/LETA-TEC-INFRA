import logging
import sys

# ─── Logging Configuration (must be first) ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Reduce noise from third-party libraries
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("flashrank").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

import uvicorn
from pathlib import Path
import requests
from app.api.app import app
from app.config import validate_config

GDRIVE_FILES = {
    Path("vectordb/index.faiss"):      "1fehfdhPCh3jxc3TBWitAfb0dv8I1opUM",
    Path("data/chunks/chunks.jsonl"):  "1u4EjWwNRz-tJaI8ifKPvpXxscNGiZ68V",
}

def download_gdrive(file_id: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading {dest} from Google Drive...")
    session = requests.Session()
    url = "https://drive.google.com/uc"
    params = {"export": "download", "id": file_id}
    response = session.get(url, params=params, stream=True)
    # Handle large-file confirmation token
    token = next((v for k, v in response.cookies.items() if k.startswith("download_warning")), None)
    if token:
        params["confirm"] = token
        response = session.get(url, params=params, stream=True)
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    logger.info(f"Downloaded {dest} ({dest.stat().st_size / 1e6:.1f} MB)")

def ensure_data_files():
    for dest, file_id in GDRIVE_FILES.items():
        if not dest.exists() or dest.stat().st_size < 1024:
            try:
                download_gdrive(file_id, dest)
            except Exception as e:
                logger.error(f"Failed to download {dest}: {e}")
        else:
            logger.info(f"Data file already present: {dest}")

@app.on_event("startup")
async def startup_event():
    logger.info("LETA/Sentinel.AI starting up...")
    ensure_data_files()
    config_ok = validate_config()
    if not config_ok:
        logger.error("Configuration validation failed — check warnings above")
    else:
        logger.info("Configuration validated successfully")


if __name__ == "__main__":
    logger.info("Starting uvicorn server on 0.0.0.0:8000")
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
        )
    except Exception as e:
        logger.critical(f"Uvicorn crashed: {e}", exc_info=True)
        sys.exit(1)
