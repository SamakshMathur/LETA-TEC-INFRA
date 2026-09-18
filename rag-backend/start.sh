#!/bin/bash
set -e

echo "[START] DATA SYNC STARTING — cwd=$(pwd) force=${FORCE_DATA_DOWNLOAD:-0}"

# ── Download FAISS index + chunks from S3 via boto3 ────────────────────────────
# boto3 uses the ECS task role automatically — no credentials needed.
# Files are uploaded by: python scripts/rebuild_and_upload.py
#
# S3 paths:
#   s3://${S3_DATA_BUCKET}/vectordb/index.faiss
#   s3://${S3_DATA_BUCKET}/data/chunks/chunks.jsonl

python3 - <<'PYEOF'
import os, sys, boto3
from pathlib import Path

BUCKET = os.getenv("S3_DATA_BUCKET", "gst-rag-data-721082558531")
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
FORCE  = os.getenv("FORCE_DATA_DOWNLOAD", "0") == "1"

DATA_FILES = {
    "vectordb/index.faiss":          ("vectordb/index.faiss",          10 * 1024 * 1024),
    "data/chunks/chunks.jsonl":      ("data/chunks/chunks.jsonl",       5 * 1024 * 1024),
    "data/document_metadata.json":   ("data/document_metadata.json",    1 * 1024),
}

# These are always overwritten on every boot (hot-patch code without a full
# Docker rebuild) — kept in sync with git automatically by deploy.yml's own
# "Sync hot-patch files to S3" step, which uploads the current commit's copy
# of every one of these on every deploy. Before that step existed, this S3
# mirror could silently drift from what a merged PR actually shipped — a
# container reboot would then quietly revert a shipped fix with no error at
# all. Found and fixed 2026-09-16 after exactly that: an invoice feature
# merged and deployed correctly, but every fresh container kept overwriting
# database.py with a stale pre-feature copy from over a week earlier,
# breaking invoice downloads (ImportError: cannot import name
# 'get_invoice_collection') until the S3 mirror was manually resynced.
ALWAYS_FILES = {
    "app/api/auth.py":                 "scripts/auth.py",
    "app/api/documents.py":            "scripts/documents.py",
    "app/ingestion/legal_parser.py":   "scripts/legal_parser.py",
    "app/api/app.py":                  "scripts/app.py",
    "app/api/advisory.py":             "scripts/advisory.py",
    "app/retrieval/retriever.py":      "scripts/retriever.py",
    "app/api/sessions.py":             "scripts/sessions.py",
    "app/database.py":                 "scripts/database.py",
    # security.py deliberately NOT hot-patched — an earlier incident found
    # the deployed image's security.py had diverged from git (a require_roles
    # function that didn't exist in the checkout being worked from at the
    # time), and hot-patching it crashed every worker on import. require_roles
    # exists in git as of 2026-09-16, so the specific divergence that caused
    # that crash may be resolved — but that wasn't independently verified
    # against the actual running image's bytes, and the cost of being wrong
    # here is a total outage. Don't add this back without first confirming
    # (e.g. via a canary deploy) that the current git security.py is safe to
    # hot-patch, not just that the missing function now exists somewhere.
}

s3 = boto3.client("s3", region_name=REGION)

for local_path_str, (s3_key, min_bytes) in DATA_FILES.items():
    local = Path(local_path_str)
    size  = local.stat().st_size if local.exists() else 0

    print(f"[DATA] {local}: exists={local.exists()}, size={size/1e6:.1f}MB", flush=True)

    if FORCE or not local.exists() or size < min_bytes:
        local.parent.mkdir(parents=True, exist_ok=True)
        print(f"[DATA] Downloading s3://{BUCKET}/{s3_key} → {local} ...", flush=True)
        try:
            s3.download_file(BUCKET, s3_key, str(local))
            print(f"[DATA] Done: {local} ({local.stat().st_size/1e6:.1f}MB)", flush=True)
        except Exception as e:
            print(f"[WARN] S3 download failed: {e}", flush=True)
            sys.exit(1)
    else:
        print(f"[DATA] File OK — skipping download.", flush=True)

for local_path_str, s3_key in ALWAYS_FILES.items():
    local = Path(local_path_str)
    local.parent.mkdir(parents=True, exist_ok=True)
    print(f"[PATCH] Overwriting {local} from s3://{BUCKET}/{s3_key} ...", flush=True)
    try:
        s3.download_file(BUCKET, s3_key, str(local))
        print(f"[PATCH] Done: {local} ({local.stat().st_size} bytes)", flush=True)
    except Exception as e:
        print(f"[WARN] Patch download failed for {local}: {e} — continuing with baked version", flush=True)
PYEOF

echo "[START] DATA SYNC COMPLETE — starting gunicorn"

# Worker count: default 2. Each gunicorn worker independently loads the
# embedding model (~1.3 GB) + FAISS index (~230 MB) + FlashRank (~22 MB)
# = ~1.85 GB baseline per worker — the task's 8 GB memory comfortably fits 2.
# Override via WORKERS env var in the ECS task definition only if needed.
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
