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

# ─── Data File Sync (runs at import time, before uvicorn starts) ────────────
from pathlib import Path
import requests

GDRIVE_FILES = {
    Path("vectordb/index.faiss"):     "1fehfdhPCh3jxc3TBWitAfb0dv8I1opUM",
    Path("data/chunks/chunks.jsonl"): "1u4EjWwNRz-tJaI8ifKPvpXxscNGiZ68V",
}
MIN_SIZES = {
    Path("vectordb/index.faiss"):     100 * 1024 * 1024,
    Path("data/chunks/chunks.jsonl"):  50 * 1024 * 1024,
}

def _download_gdrive(file_id: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[DATA] Downloading {dest} from Google Drive...", flush=True)
    session = requests.Session()
    url = "https://drive.usercontent.google.com/download"
    params = {"id": file_id, "export": "download", "confirm": "t"}
    response = session.get(url, params=params, stream=True)
    print(f"[DATA] HTTP {response.status_code} for {dest}", flush=True)
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    print(f"[DATA] Done: {dest} ({dest.stat().st_size / 1e6:.1f} MB)", flush=True)

print(f"[DATA] cwd={os.getcwd()}, FORCE={os.getenv('FORCE_DATA_DOWNLOAD','0')}", flush=True)
force = os.getenv("FORCE_DATA_DOWNLOAD", "0") == "1"
for _dest, _fid in GDRIVE_FILES.items():
    _size = _dest.stat().st_size if _dest.exists() else 0
    print(f"[DATA] {_dest}: exists={_dest.exists()}, size={_size/1e6:.1f}MB", flush=True)
    if force or not _dest.exists() or _size < MIN_SIZES[_dest]:
        try:
            _download_gdrive(_fid, _dest)
        except Exception as _e:
            print(f"[DATA] ERROR: {_e}", flush=True)

# ─── App ────────────────────────────────────────────────────────────────────
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
    logger.info("Starting uvicorn server on 0.0.0.0:8000")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.critical(f"Uvicorn crashed: {e}", exc_info=True)
        sys.exit(1)
