from pathlib import Path
from app.retrieval.retriever import Retriever

# ---------- Lazy Load Retriever ----------
_retriever = None

def get_retriever():
    global _retriever
    if _retriever is None or _retriever.index is None:
        print("Initializing Retriever (Lazy Load)...")
        _retriever = Retriever(
            index_path=Path("vectordb/index.faiss"),
            chunks_path=Path("data/chunks/chunks.jsonl")
        )
    return _retriever

def reload_retriever():
    """Force-reload the retriever after incremental ingestion."""
    global _retriever
    print("Hot-reloading Retriever after new document ingestion...")
    _retriever = Retriever(
        index_path=Path("vectordb/index.faiss"),
        chunks_path=Path("data/chunks/chunks.jsonl")
    )
    return _retriever
