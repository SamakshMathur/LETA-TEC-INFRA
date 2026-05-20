"""
Rebuilds the FAISS vector index from scratch using all chunks in chunks.jsonl.
Run this after any incremental ingest to ensure full alignment.

Run from: RAG/rag-backend/
    python scripts/rebuild_faiss_from_chunks.py

Time estimate: ~30 min for 40,000 chunks on CPU (BAAI/bge-m3, 1024 dim)
               ~5 min with GPU
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

CHUNKS_FILE  = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\chunks.jsonl")
INDEX_FILE   = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\vectordb\index.faiss")
VECTOR_DIM   = 1024
BATCH_SIZE   = 256   # embed this many chunks at once — keeps RAM under ~2 GB


def load_chunks():
    texts    = []
    chunk_ids = []
    with CHUNKS_FILE.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                c = json.loads(line.strip())
                text = c.get("text", "").strip()
                if text:
                    texts.append(text)
                    chunk_ids.append(c.get("chunk_id", ""))
            except Exception:
                pass
    return texts, chunk_ids


def rebuild():
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    print("Loading embedding model (BAAI/bge-m3)...")
    model = SentenceTransformer("BAAI/bge-m3")

    print(f"Reading chunks from {CHUNKS_FILE}...")
    texts, chunk_ids = load_chunks()
    print(f"  {len(texts)} chunks to embed")

    # Build a fresh IndexFlatIP
    index = faiss.IndexFlatIP(VECTOR_DIM)

    print(f"Embedding in batches of {BATCH_SIZE}...")
    t0 = time.time()
    total_added = 0

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start: start + BATCH_SIZE]
        vecs  = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        vecs  = vecs.astype("float32")
        index.add(vecs)
        total_added += len(batch)

        elapsed = time.time() - t0
        rate    = total_added / elapsed if elapsed > 0 else 0
        eta     = (len(texts) - total_added) / rate if rate > 0 else 0
        print(f"  [{total_added}/{len(texts)}]  {rate:.0f} chunks/s  ETA {eta/60:.1f} min", end="\r")

    print(f"\nAll {total_added} chunks embedded in {(time.time()-t0)/60:.1f} min")
    print(f"Writing FAISS index to {INDEX_FILE}...")

    # Backup the old index before overwriting
    backup = INDEX_FILE.with_suffix(".faiss.bak")
    if INDEX_FILE.exists():
        import shutil
        shutil.copy2(str(INDEX_FILE), str(backup))
        print(f"  Old index backed up to {backup.name}")

    faiss.write_index(index, str(INDEX_FILE))

    # Remove sidecar if it exists
    sidecar = INDEX_FILE.parent / "index_sidecar.faiss"
    if sidecar.exists():
        sidecar.unlink()
        print("  Sidecar index removed (merged into main)")

    size_mb = INDEX_FILE.stat().st_size / (1024 * 1024)
    print(f"\nDONE.")
    print(f"  Vectors in FAISS : {index.ntotal}")
    print(f"  Index file size  : {size_mb:.1f} MB")
    print(f"  Chunks in file   : {len(texts)}")
    if index.ntotal == len(texts):
        print("  Alignment        : PERFECT (vectors == chunks)")
    else:
        print(f"  Alignment        : MISMATCH ({abs(index.ntotal - len(texts))} difference)")


if __name__ == "__main__":
    rebuild()
