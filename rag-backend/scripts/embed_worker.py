"""
Worker script executed as a subprocess by rebuild_faiss_from_chunks.py
to embed a slice of chunks using 1 CPU thread.
"""
import os
import sys
import json
import numpy as np
import torch

# Force strictly single-threaded CPU execution to prevent segfaults
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"
torch.set_num_threads(1)

from sentence_transformers import SentenceTransformer


def main():
    if len(sys.argv) < 4:
        print("Usage: embed_worker.py <model_name> <input_json> <output_npy>")
        sys.exit(1)

    model_name = sys.argv[1]
    input_json = sys.argv[2]
    output_npy = sys.argv[3]

    with open(input_json, "r", encoding="utf-8") as f:
        texts = json.load(f)

    model = SentenceTransformer(model_name, device="cpu")
    vecs = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    np.save(output_npy, vecs.astype("float32"))
    print(f"Successfully embedded {len(texts)} chunks to {output_npy}")


if __name__ == "__main__":
    main()
