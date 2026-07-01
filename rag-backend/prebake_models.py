"""Run during Docker build to cache AI models into the image layer.

Both models are downloaded once at build time so containers start in
seconds rather than spending 5-10 minutes downloading from HuggingFace.
"""
print("=== Baking AI models into Docker image ===")

print("1/2  BAAI/bge-large-en-v1.5 (~1.3 GB)...")
from sentence_transformers import SentenceTransformer
SentenceTransformer("BAAI/bge-large-en-v1.5")
print("     Done.")

print("2/2  ms-marco-MiniLM-L-12-v2 (~22 MB via flashrank)...")
from flashrank import Ranker
Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/root/.flashrank_cache")
print("     Done.")

print("=== Model bake complete ===")
