import logging
from typing import List

import numpy as np

from app.config import EMBEDDING_MODEL, VECTOR_DIM

logger = logging.getLogger(__name__)

# Lazy-loaded — model is expensive to load (~15-20s on cold CPU).
# Previously loaded at module import time with bare print() calls, which meant
# ANY import of this module (even for unrelated purposes) would block for 20s
# and emit unstructured text outside the logging system.
_model = None


def _resolve_model_path(model_name: str) -> str:
    """Resolves a model identifier to a local cached snapshot directory if available."""
    from pathlib import Path
    import os

    p = Path(model_name)
    if p.exists():
        return str(p.resolve())

    cache_roots = []
    if os.environ.get("HF_HOME"):
        cache_roots.append(Path(os.environ["HF_HOME"]) / "hub")
    if os.environ.get("TRANSFORMERS_CACHE"):
        cache_roots.append(Path(os.environ["TRANSFORMERS_CACHE"]))
    if os.environ.get("HF_HUB_CACHE"):
        cache_roots.append(Path(os.environ["HF_HUB_CACHE"]))
    cache_roots.append(Path.home() / ".cache" / "huggingface" / "hub")

    repo_folder = f"models--{model_name.replace('/', '--')}"
    for root in cache_roots:
        snapshots_dir = root / repo_folder / "snapshots"
        if snapshots_dir.exists():
            snapshots = [s for s in snapshots_dir.iterdir() if s.is_dir()]
            if snapshots:
                snapshots.sort(key=lambda s: s.stat().st_mtime, reverse=True)
                return str(snapshots[0])

    return model_name


def _get_model():
    global _model
    if _model is None:
        logger.info(f"Loading local embedding model: {EMBEDDING_MODEL}")
        from sentence_transformers import SentenceTransformer

        resolved_path = _resolve_model_path(EMBEDDING_MODEL)
        try:
            _model = SentenceTransformer(resolved_path)
        except Exception:
            _model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)

        logger.info(f"Embedding model loaded: {EMBEDDING_MODEL}")
    return _model




def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate embeddings using local Sentence Transformers (CPU friendly).
    """
    embeddings = _get_model().encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    result = np.array(embeddings, dtype="float32")
    if result.ndim != 2 or result.shape[1] != VECTOR_DIM:
        raise ValueError(f"Embedding dimension {result.shape} != configured VECTOR_DIM {VECTOR_DIM}")
    return result
