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

import os, sys

GDRIVE_FILES = {
    Path("vectordb/index.faiss"):      "1fehfdhPCh3jxc3TBWitAfb0dv8I1opUM",
    Path("data/chunks/chunks.jsonl"):  "1u4EjWwNRz-tJaI8ifKPvpXxscNGiZ68V",
}

MIN_SIZES = {
    Path("vectordb/index.faiss"):     100 * 1024 * 1024,
    Path("data/chunks/chunks.jsonl"):  50 * 1024 * 1024,
}

def download_gdrive(file_id: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[DOWNLOAD] Starting download of {dest} ...", flush=True)
    session = requests.Session()
    url = "https://drive.usercontent.google.com/download"
    params = {"id": file_id, "export": "download", "confirm": "t"}
    response = session.get(url, params=params, stream=True)
    print(f"[DOWNLOAD] HTTP {response.status_code} for {dest}", flush=True)
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    size_mb = dest.stat().st_size / 1e6
    print(f"[DOWNLOAD] Done: {dest} ({size_mb:.1f} MB)", flush=True)

def ensure_data_files():
    force = os.getenv("FORCE_DATA_DOWNLOAD", "0") == "1"
    print(f"[DATA] Checking data files (force={force}, cwd={os.getcwd()})", flush=True)
    for dest, file_id in GDRIVE_FILES.items():
        min_size = MIN_SIZES.get(dest, 1024)
        exists = dest.exists()
        size = dest.stat().st_size if exists else 0
        print(f"[DATA] {dest}: exists={exists}, size={size/1e6:.1f}MB, min={min_size/1e6:.0f}MB", flush=True)
        if force or not exists or size < min_size:
            try:
                download_gdrive(file_id, dest)
            except Exception as e:
                print(f"[DATA] ERROR downloading {dest}: {e}", flush=True, file=sys.stderr)

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
