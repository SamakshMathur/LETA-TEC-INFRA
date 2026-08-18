import faiss
import json
import numpy as np
from pathlib import Path
from app.embeddings.embedder import embed_texts, VECTOR_DIM

def build_vector_store(chunks_path: Path, index_path: Path):
    texts = []
    metadatas = []

    print(f"Loading chunks from {chunks_path}...")
    if not chunks_path.exists():
        print("Chunks file not found!")
        return

    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                texts.append(record["text"])
                # store relevant metadata
                metadatas.append({
                    "source": record.get("source"),
                    "page": record.get("page"),
                    "type": record.get("type"),
                    "chunk_id": record.get("chunk_id")
                })
            except:
                continue
    
    print(f"loaded {len(texts)} chunks. Generating embeddings...")
    
    # Generate embeddings
    embeddings = embed_texts(texts).astype("float32")
    
    print(f"Embeddings shape: {embeddings.shape}")

    # IndexFlatL2 requires exact dimension match
    index = faiss.IndexFlatL2(VECTOR_DIM)
    index.add(embeddings)

    print(f"Saving index to {index_path}...")
    faiss.write_index(index, str(index_path))

    # Save metadata alongside
    with open(index_path.with_suffix(".meta.json"), "w", encoding="utf-8") as f:
        json.dump(metadatas, f, ensure_ascii=False, indent=2)
        
    print("Vector Store built successfully.")