"""Run during Docker build to cache AI models into the image layer.

All models are downloaded once at build time so containers start in
seconds rather than spending time downloading from HuggingFace.
"""
print("=== Baking AI models into Docker image ===")

print("1/2  BAAI/bge-large-en-v1.5 (~1.3 GB) — embedding model...")
from sentence_transformers import SentenceTransformer
SentenceTransformer("BAAI/bge-large-en-v1.5")
print("     Done.")

print("2/3  ms-marco-MiniLM-L-12-v2 (~22 MB) — FlashRank stage-1 filter...")
from flashrank import Ranker
Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/root/.flashrank_cache")
print("     Done.")

print("3/3  BAAI/bge-reranker-v2-m3 (~570 MB) — BGE stage-2 precision reranker...")
from FlagEmbedding import FlagReranker
FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
print("     Done.")

print("=== Model bake complete ===")
