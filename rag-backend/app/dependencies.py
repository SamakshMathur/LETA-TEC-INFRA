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

def preload_all_models():
    """Trigger eager-loading of all models (Retriever + Embedding)."""
    import os
    pid = os.getpid()

    global _retriever
    if _retriever is not None and _retriever.index is not None:
        logger.info(f"MODEL_INIT process={pid} model=Retriever action=reused")
    else:
        logger.info(f"MODEL_INIT process={pid} model=Retriever action=loaded")
        get_retriever()

    from app.retrieval.retriever import _model, get_model
    if _model is not None:
        logger.info(f"MODEL_INIT process={pid} model=Embedding action=reused")
    else:
        logger.info(f"MODEL_INIT process={pid} model=Embedding action=loaded")
        try:
            get_model()
        except Exception as e:
            logger.error(f"❌ Failed to pre-load embedding model: {e}", exc_info=True)

def reload_retriever():
    """Force-reload the retriever after incremental ingestion."""
    global _retriever
    logger.info("Hot-reloading Retriever after new document ingestion...")
    _retriever = Retriever(
        index_path=FAISS_INDEX_PATH,
        chunks_path=CHUNKS_PATH,
    )
    return _retriever
