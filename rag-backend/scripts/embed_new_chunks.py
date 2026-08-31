"""
Embeds only the chunks that are NOT yet in the FAISS index and writes them
to index_sidecar.faiss. Much gentler than a full rebuild.

Run from: rag-backend/
    python -X utf8 scripts/embed_new_chunks.py

The server will merge the sidecar into the main index on next startup.
"""
import sys
import io
import os
import json
import time
from pathlib import Path

# Resolve app root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import EMBEDDING_MODEL, VECTOR_DIM, CHUNKS_PATH, VECTOR_DB_PATH

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def main():
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    import torch

    chunks_file = Path(CHUNKS_PATH)
    index_file = Path(VECTOR_DB_PATH)
    sidecar_file = index_file.parent / "index_sidecar.faiss"

    # Limit to 2 CPU threads so the machine stays responsive
    torch.set_num_threads(2)

    print(f"Loading embedding model ({EMBEDDING_MODEL})...", flush=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

    print(f"Reading main FAISS index from {index_file}...", flush=True)
    if not index_file.exists():
        print(f"ERROR: Main index file not found at {index_file}. Run rebuild first.", flush=True)
        sys.exit(1)

    main_idx = faiss.read_index(str(index_file))
    main_n = main_idx.ntotal
    print(f"  Main index: {main_n} vectors", flush=True)
    del main_idx  # free RAM immediately

    print(f"Reading chunks from {chunks_file}...", flush=True)
    all_texts = []
    with chunks_file.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                c = json.loads(line_str)
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

    # Create a fresh sidecar
    sidecar_idx = faiss.IndexFlatIP(VECTOR_DIM)
    batch_size = 32
    print(f"\nEmbedding {len(new_texts)} chunks in batches of {batch_size}...", flush=True)
    t0 = time.time()
    total_added = 0

    for start in range(0, len(new_texts), batch_size):
        batch = new_texts[start: start + batch_size]
        vecs = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        vecs = vecs.astype("float32")
        sidecar_idx.add(vecs)
        total_added += len(batch)

        elapsed = time.time() - t0
        rate = total_added / elapsed if elapsed > 0 else 0
        eta_min = (len(new_texts) - total_added) / rate / 60 if rate > 0 else 0
        print(f"  [{total_added}/{len(new_texts)}]  {rate:.1f} chunks/s  ETA {eta_min:.1f} min", flush=True)

        # Write checkpoint every 500 chunks
        if total_added % 500 == 0:
            faiss.write_index(sidecar_idx, str(sidecar_file))
            print(f"  (checkpoint saved — {sidecar_file.stat().st_size // 1024} KB)", flush=True)

    print(f"\nAll {total_added} new chunks embedded in {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"Writing sidecar to {sidecar_file}...", flush=True)
    faiss.write_index(sidecar_idx, str(sidecar_file))

    size_kb = sidecar_file.stat().st_size // 1024
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
