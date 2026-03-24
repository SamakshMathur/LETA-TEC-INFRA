from typing import List, Union
import numpy as np
import os
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from app.config import (
    OPENAI_API_KEY, 
    EMBEDDING_PROVIDER, 
    EMBEDDING_MODEL, 
    VECTOR_DIM
)

# Global clients
openai_client = None
local_model = None

def get_openai_client():
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return openai_client

def get_local_model():
    global local_model
    if local_model is None:
        print(f"Loading Local Embedding Model ({EMBEDDING_MODEL})...")
        local_model = SentenceTransformer(EMBEDDING_MODEL)
        print("Model loaded.")
    return local_model

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate embeddings using the configured provider (OpenAI or Local).
    """
    try:
        if EMBEDDING_PROVIDER == "openai":
            client = get_openai_client()
            # OpenAI text-embedding-3-large
            # Batch processing to avoid token limits
            embeddings = []
            batch_size = 50 
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                try:
                    response = client.embeddings.create(
                        input=batch,
                        model=EMBEDDING_MODEL,
                        dimensions=VECTOR_DIM 
                    )
                    batch_embeddings = [data.embedding for data in response.data]
                    embeddings.extend(batch_embeddings)
                    print(f"  -> Embedded batch {i}/{len(texts)}")
                except Exception as e:
                    print(f"Error on batch {i}: {e}")
                    # Basic retry or skip? For now, re-raise to fail fast or verify data
                    raise e
                    
            return np.array(embeddings, dtype='float32')
            
        else:
            # Fallback to Local — multi-core optimized
            import torch
            import os
            num_cores = os.cpu_count() or 8
            torch.set_num_threads(num_cores)
            os.environ["OMP_NUM_THREADS"] = str(num_cores)
            os.environ["MKL_NUM_THREADS"] = str(num_cores)
            model = get_local_model()
            embeddings = model.encode(
                texts,
                batch_size=128,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
            return np.array(embeddings, dtype='float32')

    except Exception as e:
        print(f"Embedding Error ({EMBEDDING_PROVIDER}): {e}")
        # Fallback to local if OpenAI fails? Or raise?
        # For now, let's fallback to local just in case, but dimension mismatch will occur.
        # So better to just raise or return empty.
        # Actually given the dimension difference (3072 vs 384), fallback is dangerous without re-indexing.
        # We will assume if configured for OpenAI, we must use OpenAI.
        raise e