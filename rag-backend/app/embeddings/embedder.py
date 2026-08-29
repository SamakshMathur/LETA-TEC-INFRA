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


def _get_model():
    global _model
    if _model is None:
        logger.info(f"Loading local embedding model: {EMBEDDING_MODEL}")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
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
