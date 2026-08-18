from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

# all-MiniLM-L6-v2 dimension
VECTOR_DIM = 384

# Initialize model once (globally or singleton)
print("Loading Local Embedding Model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2') 
print("Model loaded.")

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate embeddings using local Sentence Transformers (CPU friendly).
    """
    # SentenceTransformer handles batching internally, but we can explicit if needed.
    # It returns a numpy array by default if convert_to_numpy=True (default).
    
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    
    return np.array(embeddings, dtype="float32")