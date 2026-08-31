import os
import sys
import json
import time
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
import numpy as np
import torch
import faiss
from sentence_transformers import SentenceTransformer

# Resolve app root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import EMBEDDING_MODEL, VECTOR_DIM, CHUNKS_PATH, VECTOR_DB_PATH

def compute_file_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with filepath.open("rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def compute_ids_sha256(chunk_ids: list) -> str:
    sha = hashlib.sha256()
    sha.update("".join(chunk_ids).encode("utf-8"))
    return sha.hexdigest()

def main():
    # Paths
    dry_run_chunks_path = Path("scratch/chunks_v2_dry_run.jsonl")
    checkpoint_path = Path("scratch/embedding_checkpoint.json")
    npy_path = Path("scratch/embeddings_v2.npy")
    processed_chunks_path = Path("scratch/chunks_v2_processed.jsonl")

    if not dry_run_chunks_path.exists():
        print(f"ERROR: Dry run chunks file not found at {dry_run_chunks_path}. Run dry run first!")
        sys.exit(1)

    print("=== STARTING CANONICAL V2.0 VECTOR INDEX BUILD ===", flush=True)

    # 1. Load validated V2 chunks
    chunks = []
    with open(dry_run_chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    num_chunks = len(chunks)
    print(f"Loaded {num_chunks} chunks from dry-run output.", flush=True)

    # 2. Determine resume state
    start_idx = 0
    existing_vectors = None
    processed_chunk_records = []

    if checkpoint_path.exists() and npy_path.exists() and processed_chunks_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            last_idx = checkpoint.get("last_processed_chunk_idx", -1)

            # Load processed chunks
            with open(processed_chunks_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        processed_chunk_records.append(json.loads(line))

            # Verify length alignment
            existing_vectors = np.load(npy_path)
            if existing_vectors.shape[0] == last_idx + 1 and len(processed_chunk_records) == last_idx + 1:
                start_idx = last_idx + 1
                print(f"Resuming from checkpoint at chunk index {start_idx}...", flush=True)
                print(f"Loaded {existing_vectors.shape[0]} existing vectors.", flush=True)
            else:
                print("WARNING: Checkpoint files mismatched or corrupted. Starting fresh.", flush=True)
                start_idx = 0
                existing_vectors = None
                processed_chunk_records = []
        except Exception as e:
            print(f"WARNING: Error loading checkpoint: {e}. Starting fresh.", flush=True)
            start_idx = 0
            existing_vectors = None
            processed_chunk_records = []

    # 3. Load model
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading SentenceTransformer model {EMBEDDING_MODEL} on {device.upper()}...", flush=True)
    model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    print("Model loaded successfully.", flush=True)

    # 4. Process in batches
    batch_size = 32
    vectors_list = [existing_vectors] if existing_vectors is not None else []

    # Open processed chunks file in append/write mode
    mode = "a" if start_idx > 0 else "w"
    with open(processed_chunks_path, mode, encoding="utf-8") as out_chunks_f:
        t0 = time.time()
        for i in range(start_idx, num_chunks, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_texts = [c["text"] for c in batch_chunks]

            print(f"Embedding batch [{i}/{num_chunks}] ({len(batch_chunks)} chunks)...", flush=True)

            # Compute embeddings
            batch_vecs = model.encode(
                batch_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True
            ).astype("float32")

            vectors_list.append(batch_vecs)

            # Write to chunks file
            for chunk in batch_chunks:
                out_chunks_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                processed_chunk_records.append(chunk)

            # Update checkpoint and temp npy
            current_vectors = np.vstack(vectors_list)
            np.save(npy_path, current_vectors)

            last_processed = i + len(batch_chunks) - 1
            checkpoint = {
                "last_processed_chunk_idx": last_processed,
                "chunk_id": batch_chunks[-1]["chunk_id"],
                "model_name": EMBEDDING_MODEL,
                "dimension": VECTOR_DIM,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            with open(checkpoint_path, "w", encoding="utf-8") as cp_f:
                json.dump(checkpoint, cp_f, indent=2)

            # Reset vectors_list to contain only the aggregated array to keep memory clean
            vectors_list = [current_vectors]

        print(f"All chunks embedded successfully in {time.time() - t0:.2f} seconds.", flush=True)

    # 5. Build and save index and meta files
    final_vectors = np.load(npy_path)
    print(f"Final vectors shape: {final_vectors.shape}", flush=True)

    if final_vectors.shape[0] != num_chunks:
        print(f"ERROR: Expected {num_chunks} embedded vectors, but found {final_vectors.shape[0]}.", flush=True)
        sys.exit(1)

    print("Building fresh IndexFlatIP index...", flush=True)
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(final_vectors)

    # Save files
    final_index_path = Path(VECTOR_DB_PATH)
    final_chunks_path = Path(CHUNKS_PATH)
    final_meta_path = final_index_path.with_suffix(".meta.json")

    # Make sure parent directories exist
    final_index_path.parent.mkdir(parents=True, exist_ok=True)
    final_chunks_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy chunks.jsonl
    shutil.copy2(processed_chunks_path, final_chunks_path)
    print(f"Saved fresh chunks file to {final_chunks_path}", flush=True)

    # Write FAISS index
    faiss.write_index(index, str(final_index_path))
    print(f"Saved fresh FAISS index to {final_index_path}", flush=True)

    # Write metadata index.meta.json
    metadatas = [c.get("metadata", {}) | {"chunk_id": c["chunk_id"]} for c in processed_chunk_records]
    with open(final_meta_path, "w", encoding="utf-8") as meta_f:
        json.dump(metadatas, meta_f, ensure_ascii=False, indent=2)
    print(f"Saved metadata file to {final_meta_path}", flush=True)

    # 6. Generate Manifest
    print("Generating index manifest...", flush=True)
    chunks_sha = compute_file_sha256(final_chunks_path)
    chunk_ids = [c["chunk_id"] for c in processed_chunk_records]
    ids_sha = compute_ids_sha256(chunk_ids)

    manifest = {
        "schema_version": 1,
        "index_count": index.ntotal,
        "chunk_count": num_chunks,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": VECTOR_DIM,
        "normalize_embeddings": True,
        "index_type": "IndexFlatIP",
        "chunks_sha256": chunks_sha,
        "chunk_ids_sha256": ids_sha,
        "build_timestamp": datetime.utcnow().isoformat() + "Z",
        "builder_version": "2.0.0",
        "corpus_name": "Database_V2.0",
        "corpus_root": "RAG_INFORMATION_DATABASE/NEW DATABASE/Database_V2.0"
    }

    manifest_path = final_index_path.parent / "index_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as manifest_f:
        json.dump(manifest, manifest_f, indent=2)
    print(f"Saved manifest to {manifest_path}", flush=True)

    # 7. Cleanup dry run and temp files
    for f in [checkpoint_path, npy_path, processed_chunks_path]:
        if f.exists():
            f.unlink()

    print("V2.0 BUILD COMPLETED SUCCESSFULLY.", flush=True)

if __name__ == "__main__":
    main()
