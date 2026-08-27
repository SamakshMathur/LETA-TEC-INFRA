from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL, VECTOR_DIM

print(f"Loading Local Embedding Model ({EMBEDDING_MODEL})...")
model = SentenceTransformer(EMBEDDING_MODEL)
print("Model loaded.")

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate embeddings using local Sentence Transformers (CPU friendly).
    """
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    result = np.array(embeddings, dtype="float32")
    if result.ndim != 2 or result.shape[1] != VECTOR_DIM:
        raise ValueError(f"Embedding dimension {result.shape} != configured VECTOR_DIM {VECTOR_DIM}")
    return result