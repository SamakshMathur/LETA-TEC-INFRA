"""Run during Docker build to cache AI models into the image layer.

All models are downloaded once at build time so containers start in
seconds rather than spending time downloading from HuggingFace.
"""
print("=== Baking AI models into Docker image ===")

print("1/2  BAAI/bge-large-en-v1.5 (~1.3 GB) — embedding model...")
from sentence_transformers import SentenceTransformer
SentenceTransformer("BAAI/bge-large-en-v1.5")
print("     Done.")

print("2/2  BAAI/bge-reranker-v2-m3 (~568 MB) — CrossEncoder reranker...")
from sentence_transformers import CrossEncoder
CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
print("     Done.")

# Verify scikit-learn is installed (used for TF-IDF 3rd RRF signal).
# No download needed — TF-IDF matrix is built at startup from chunks.jsonl.
# This import check catches any install failure at build time, not runtime.
print("3/3  scikit-learn — TF-IDF vectorizer (no download, install check only)...")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
print("     Done.")

print("=== Model bake complete ===")
