import logging
import os
from pathlib import Path

from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

# ── FAISS index paths — configurable via env vars for EFS / S3 mounts ────────
# In production (ECS + EFS): set FAISS_INDEX_PATH=/mnt/efs/vectordb/index.faiss
# In local dev: falls back to the path relative to the project root.
_APP_ROOT = Path(__file__).resolve().parent.parent   # rag-backend/

_DEFAULT_INDEX  = str(_APP_ROOT / "vectordb" / "index.faiss")
_DEFAULT_CHUNKS = str(_APP_ROOT / "data" / "chunks" / "chunks.jsonl")

FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", _DEFAULT_INDEX))
CHUNKS_PATH      = Path(os.getenv("CHUNKS_PATH",      _DEFAULT_CHUNKS))

# ---------- Lazy Load Retriever ----------
_retriever = None

def get_retriever():
    global _retriever
    if _retriever is None or _retriever.index is None:
        logger.info(
            f"Initializing Retriever (lazy load) | "
            f"index={FAISS_INDEX_PATH} | chunks={CHUNKS_PATH}"
        )
        _retriever = Retriever(
            index_path=FAISS_INDEX_PATH,
            chunks_path=CHUNKS_PATH,
        )
    return _retriever

def reload_retriever():
    """Force-reload the retriever after incremental ingestion."""
    global _retriever
    logger.info("Hot-reloading Retriever after new document ingestion...")
    _retriever = Retriever(
        index_path=FAISS_INDEX_PATH,
        chunks_path=CHUNKS_PATH,
    )
    return _retriever
