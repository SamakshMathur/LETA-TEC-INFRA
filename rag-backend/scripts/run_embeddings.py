import sys
import os
# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from app.vectordb.store import build_vector_store

CHUNKS = Path("data/chunks/chunks.jsonl")
INDEX = Path("vectordb/index.faiss")
INDEX.parent.mkdir(exist_ok=True)

if __name__ == "__main__":
    build_vector_store(CHUNKS, INDEX)