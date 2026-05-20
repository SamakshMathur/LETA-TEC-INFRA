"""
Embeds only the chunks that are NOT yet in the FAISS index and writes them
to index_sidecar.faiss. Much gentler than a full rebuild.

Run from: RAG/rag-backend/
    python -X utf8 scripts/embed_new_chunks.py

The server will merge the sidecar into the main index on next startup.
"""
import sys, io, os, json, time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

CHUNKS_FILE  = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\chunks.jsonl")
INDEX_FILE   = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\vectordb\index.faiss")
SIDECAR_FILE = Path(r"C:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\vectordb\index_sidecar.faiss")
VECTOR_DIM   = 1024
BATCH_SIZE   = 32   # small batches → low CPU spike, keeps system responsive


def main():
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    import torch

    # Limit to 2 CPU threads so the machine stays responsive
    torch.set_num_threads(2)

    print("Loading embedding model...", flush=True)
    model = SentenceTransformer("BAAI/bge-m3")

    print("Reading main FAISS index...", flush=True)
    main_idx = faiss.read_index(str(INDEX_FILE))
    main_n   = main_idx.ntotal
    print(f"  Main index: {main_n} vectors", flush=True)
    del main_idx  # free RAM immediately

    print("Reading chunks from JSONL...", flush=True)
    all_texts = []
    with CHUNKS_FILE.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                c = json.loads(line.strip())
                t = c.get("text", "").strip()
                if t:
                    all_texts.append(t)
            except Exception:
                pass
    total_chunks = len(all_texts)
    print(f"  Total chunks in JSONL: {total_chunks}", flush=True)

    # The first main_n chunks are already in FAISS — embed only the tail
    new_texts = all_texts[main_n:]
    print(f"  New chunks to embed: {len(new_texts)}", flush=True)
    del all_texts  # free RAM

    if not new_texts:
        print("Nothing to embed — FAISS is already fully aligned!", flush=True)
        return

    # Create a fresh sidecar (overwrite the old one to avoid duplication)
    sidecar_idx = faiss.IndexFlatIP(VECTOR_DIM)
    print(f"\nEmbedding {len(new_texts)} chunks in batches of {BATCH_SIZE}...", flush=True)
    t0 = time.time()
    total_added = 0

    for start in range(0, len(new_texts), BATCH_SIZE):
        batch = new_texts[start: start + BATCH_SIZE]
        vecs  = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        vecs  = vecs.astype("float32")
        sidecar_idx.add(vecs)
        total_added += len(batch)

        elapsed = time.time() - t0
        rate    = total_added / elapsed if elapsed > 0 else 0
        eta_min = (len(new_texts) - total_added) / rate / 60 if rate > 0 else 0
        print(f"  [{total_added}/{len(new_texts)}]  {rate:.1f} chunks/s  ETA {eta_min:.1f} min",
              flush=True)

        # Write checkpoint every 500 chunks so progress isn't lost on crash
        if total_added % 500 == 0:
            faiss.write_index(sidecar_idx, str(SIDECAR_FILE))
            print(f"  (checkpoint saved — {SIDECAR_FILE.stat().st_size // 1024} KB)", flush=True)

    print(f"\nAll {total_added} new chunks embedded in {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"Writing sidecar to {SIDECAR_FILE}...", flush=True)
    faiss.write_index(sidecar_idx, str(SIDECAR_FILE))

    size_kb = SIDECAR_FILE.stat().st_size // 1024
    print(f"\nDONE.", flush=True)
    print(f"  Sidecar vectors : {sidecar_idx.ntotal}", flush=True)
    print(f"  Sidecar size    : {size_kb} KB", flush=True)
    print(f"  Main index      : {main_n} vectors", flush=True)
    print(f"  Combined total  : {main_n + sidecar_idx.ntotal} vectors", flush=True)
    print(f"  Chunks in JSONL : {total_chunks}", flush=True)
    gap = total_chunks - (main_n + sidecar_idx.ntotal)
    if gap == 0:
        print(f"  Alignment       : PERFECT", flush=True)
    else:
        print(f"  Alignment gap   : {gap} chunks", flush=True)
    print(f"\nNext: restart the uvicorn server. It will merge the sidecar automatically.", flush=True)


if __name__ == "__main__":
    main()
