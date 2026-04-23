#!/bin/bash
set -e

echo "[START] DATA SYNC STARTING — cwd=$(pwd) force=${FORCE_DATA_DOWNLOAD:-0}"

python3 - <<'PYEOF'
import os, sys
from pathlib import Path

GDRIVE_FILES = {
    "vectordb/index.faiss":     "1u4EjWwNRz-tJaI8ifKPvpXxscNGiZ68V",
    "data/chunks/chunks.jsonl": "1fehfdhPCh3jxc3TBWitAfb0dv8I1opUM",
}
MIN_SIZES = {
    "vectordb/index.faiss":     100 * 1024 * 1024,
    "data/chunks/chunks.jsonl":  50 * 1024 * 1024,
}

force = os.getenv("FORCE_DATA_DOWNLOAD", "0") == "1"

import gdown

for path_str, file_id in GDRIVE_FILES.items():
    dest = Path(path_str)
    size = dest.stat().st_size if dest.exists() else 0
    print(f"[DATA] {dest}: exists={dest.exists()}, size={size/1e6:.1f}MB", flush=True)
    if force or not dest.exists() or size < MIN_SIZES[path_str]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"[DATA] Downloading {dest} via gdown...", flush=True)
        gdown.download(id=file_id, output=str(dest), quiet=False, fuzzy=True)
        print(f"[DATA] Done: {dest} ({dest.stat().st_size/1e6:.1f}MB)", flush=True)
    else:
        print(f"[DATA] File OK: {dest}", flush=True)
PYEOF

echo "[START] DATA SYNC COMPLETE — starting gunicorn"

# Worker count: default 2 (each worker loads ~600 MB of models).
# Increase WORKERS if your instance has ≥ 4 GB free RAM per extra worker.
WORKERS=${WORKERS:-2}

exec gunicorn main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WORKERS}" \
  --bind "0.0.0.0:${PORT:-8080}" \
  --timeout 180 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --log-level info \
  --access-logfile - \
  --error-logfile -
