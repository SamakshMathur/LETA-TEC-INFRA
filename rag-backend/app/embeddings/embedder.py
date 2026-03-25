import logging
import threading
import time
from typing import List

import numpy as np
from app.config import (
    OPENAI_API_KEY,
    EMBEDDING_PROVIDER,
    EMBEDDING_MODEL,
    VECTOR_DIM,
)

logger = logging.getLogger(__name__)

# ─── Thread-safe singletons ───────────────────────────────────────────────
_openai_client = None
_openai_lock = threading.Lock()
_local_model = None
_local_model_lock = threading.Lock()
_torch_configured = False


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        with _openai_lock:
            if _openai_client is None:
                from openai import OpenAI
                _openai_client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("OpenAI embedding client initialized")
    return _openai_client


def get_local_model():
    global _local_model, _torch_configured
    if _local_model is None:
        with _local_model_lock:
            if _local_model is None:
                # Configure torch threading once
                if not _torch_configured:
                    import torch
                    import os
                    num_cores = os.cpu_count() or 4
                    torch.set_num_threads(num_cores)
                    os.environ["OMP_NUM_THREADS"] = str(num_cores)
                    os.environ["MKL_NUM_THREADS"] = str(num_cores)
                    _torch_configured = True
                    logger.info(f"PyTorch configured: {num_cores} threads, CUDA={'available' if torch.cuda.is_available() else 'not available'}")

                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading local embedding model: {EMBEDDING_MODEL}")
                _local_model = SentenceTransformer(EMBEDDING_MODEL)
                logger.info("Local embedding model loaded")
    return _local_model


def embed_texts(texts: List[str], max_retries: int = 3) -> np.ndarray:
    """
    Generate embeddings using the configured provider (OpenAI or Local).
    Includes retry logic for OpenAI API calls.
    """
    if not texts:
        logger.warning("embed_texts called with empty text list")
        return np.array([], dtype='float32').reshape(0, VECTOR_DIM)

    if EMBEDDING_PROVIDER == "openai":
        return _embed_openai(texts, max_retries)
    else:
        return _embed_local(texts)


def _embed_openai(texts: List[str], max_retries: int = 3) -> np.ndarray:
    """OpenAI embedding with batch processing and exponential backoff retry."""
    client = get_openai_client()
    embeddings = []
    batch_size = 50

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        last_error = None

        for attempt in range(max_retries):
            try:
                response = client.embeddings.create(
                    input=batch,
                    model=EMBEDDING_MODEL,
                    dimensions=VECTOR_DIM,
                )
                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
                logger.debug(f"Embedded batch {i}/{len(texts)} ({len(batch)} texts)")
                break
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"OpenAI embed batch {i} attempt {attempt + 1}/{max_retries} failed: {e} — retrying in {wait}s")
                time.sleep(wait)
        else:
            logger.error(f"OpenAI embed batch {i} failed after {max_retries} retries: {last_error}")
            raise last_error

    result = np.array(embeddings, dtype='float32')

    # Validate dimensions
    if result.shape[1] != VECTOR_DIM:
        logger.error(f"OpenAI embedding dimension mismatch: got {result.shape[1]}, expected {VECTOR_DIM}")
        raise ValueError(f"Embedding dimension {result.shape[1]} != configured VECTOR_DIM {VECTOR_DIM}")

    return result


def _embed_local(texts: List[str]) -> np.ndarray:
    """Local SentenceTransformer embedding with normalization for cosine similarity."""
    model = get_local_model()
    embeddings = model.encode(
        texts,
        batch_size=128,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    result = np.array(embeddings, dtype='float32')

    # Validate dimensions
    if result.shape[1] != VECTOR_DIM:
        logger.error(f"Local embedding dimension mismatch: got {result.shape[1]}, expected {VECTOR_DIM}")
        raise ValueError(f"Embedding dimension {result.shape[1]} != configured VECTOR_DIM {VECTOR_DIM}")

    logger.info(f"Embedded {len(texts)} texts → shape {result.shape}")
    return result
