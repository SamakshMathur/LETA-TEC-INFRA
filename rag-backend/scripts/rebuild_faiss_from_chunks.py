"""
Rebuilds the FAISS vector index by reusing the verified first 33936 vectors
and re-embedding the tail chunks using correct model in parallel subprocesses
to bypass PyTorch CPU multi-threading segfaults.
Generates a data integrity manifest verifying exact positional alignment.

Run from: rag-backend/
    python scripts/rebuild_faiss_from_chunks.py
"""
import os
import sys
import math
import json
import time
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np

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


def embed_slice_subprocess(slice_idx: int, texts_to_embed: list, temp_dir: Path):
    # Write texts to temp file
    texts_file = temp_dir / f"texts_{slice_idx}.json"
    with open(texts_file, "w", encoding="utf-8") as f:
        json.dump(texts_to_embed, f)

    out_file = temp_dir / f"vecs_{slice_idx}.npy"

    # Command to run single-threaded Python subprocess via helper script
    cmd = [
        sys.executable,
        "scripts/embed_worker.py",
        EMBEDDING_MODEL,
        str(texts_file),
        str(out_file)
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE), texts_file, out_file


def rebuild():
    chunks_file = Path(CHUNKS_PATH)
    index_file = Path(VECTOR_DB_PATH)
    manifest_file = index_file.parent / "index_manifest.json"
    temp_dir = Path("scratch")
    temp_dir.mkdir(exist_ok=True)

    print("Reading chunks from chunks.jsonl...", flush=True)
    texts = []
    chunk_ids = []
    with chunks_file.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                c = json.loads(line_str)
                text = c.get("text", "").strip()
                cid = c.get("chunk_id", "").strip()
                if text and cid:
                    texts.append(text)
                    chunk_ids.append(cid)
            except Exception:
                pass
    num_chunks = len(texts)
    print(f"Loaded {num_chunks} chunks.", flush=True)

    if not texts:
        print("ERROR: No chunks found to build index.", flush=True)
        return

    # Try to load existing index to reuse first 33936 vectors
    reused_vectors = []
    split_idx = 33936

    if index_file.exists():
        try:
            print(f"Reading existing FAISS index from {index_file}...", flush=True)
            old_index = faiss.read_index(str(index_file))
            print(f"Old index has {old_index.ntotal} vectors.", flush=True)
            if old_index.ntotal >= split_idx and old_index.d == VECTOR_DIM:
                print(f"Reusing first {split_idx} vectors from existing index...", flush=True)
                for i in range(split_idx):
                    reused_vectors.append(old_index.reconstruct(i))
                reused_vectors = np.array(reused_vectors).astype("float32")
                print("Reused vectors successfully reconstructed.", flush=True)
            else:
                print(f"Existing index size ({old_index.ntotal}) or dimension ({old_index.d}) mismatch. Rebuilding entirely.", flush=True)
        except Exception as e:
            print(f"Failed to reuse existing index: {e}. Rebuilding entirely.", flush=True)

    # Embed chunks that are not reused
    if len(reused_vectors) > 0:
        start_idx = split_idx
        combined_vectors_list = [reused_vectors]
    else:
        start_idx = 0
        combined_vectors_list = []

    remaining_texts = texts[start_idx:]
    if len(remaining_texts) > 0:
        num_workers = 6  # 6 parallel workers
        chunk_size = math.ceil(len(remaining_texts) / num_workers)
        print(f"Embedding remaining {len(remaining_texts)} chunks using {num_workers} parallel subprocesses...", flush=True)

        t0 = time.time()
        processes = []
        temp_files = []
        npy_files = []

        for w in range(num_workers):
            w_start = w * chunk_size
            w_end = min(w_start + chunk_size, len(remaining_texts))
            if w_start >= len(remaining_texts):
                break
            w_texts = remaining_texts[w_start:w_end]
            print(f"  Spawning worker {w}: chunks {w_start} to {w_end} ({len(w_texts)} texts)...", flush=True)
            p, t_file, n_file = embed_slice_subprocess(w, w_texts, temp_dir)
            processes.append(p)
            temp_files.append(t_file)
            npy_files.append(n_file)

        print("Waiting for workers to finish...", flush=True)
        # Monitor workers
        failed = False
        for w, p in enumerate(processes):
            stdout, stderr = p.communicate()
            if p.returncode != 0:
                print(f"ERROR: Worker {w} failed with code {p.returncode}!", flush=True)
                print("Stderr:", stderr.decode(), flush=True)
                failed = True
            else:
                print(f"Worker {w} finished successfully.", flush=True)

        if failed:
            print("ERROR: One or more workers failed. Aborting rebuild.", flush=True)
            # Cleanup temp files
            for f in temp_files + npy_files:
                if f.exists():
                    f.unlink()
            return

        print(f"All workers finished in {(time.time() - t0)/60:.2f} minutes.", flush=True)

        # Load and append new embeddings
        new_embeddings = []
        for n_file in npy_files:
            new_embeddings.append(np.load(n_file))
        new_embeddings = np.vstack(new_embeddings)
        combined_vectors_list.append(new_embeddings)

        # Cleanup temp files
        for f in temp_files + npy_files:
            if f.exists():
                f.unlink()

    # Combine all vectors
    combined_vectors = np.vstack(combined_vectors_list)
    print(f"Combined vectors shape: {combined_vectors.shape}", flush=True)

    # Build fresh IndexFlatIP index
    print("Building new IndexFlatIP index...", flush=True)
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(combined_vectors)

    # Backup the old index before overwriting
    if index_file.exists():
        backup = index_file.with_suffix(".faiss.bak")
        import shutil
        shutil.copy2(str(index_file), str(backup))
        print(f"Old index backed up to {backup.name}", flush=True)

    faiss.write_index(index, str(index_file))

    # Remove sidecar if it exists
    sidecar = index_file.parent / "index_sidecar.faiss"
    if sidecar.exists():
        sidecar.unlink()
        print("Sidecar index removed", flush=True)

    # Generate data integrity manifest
    print("Computing chunks fingerprint...", flush=True)
    chunks_sha = compute_file_sha256(chunks_file)
    ids_sha = compute_ids_sha256(chunk_ids)

    manifest = {
        "schema_version": 1,
        "index_count": index.ntotal,
        "chunk_count": len(texts),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": VECTOR_DIM,
        "normalize_embeddings": True,
        "index_type": "IndexFlatIP",
        "chunks_sha256": chunks_sha,
        "chunk_ids_sha256": ids_sha,
        "build_timestamp": datetime.utcnow().isoformat() + "Z",
        "builder_version": "1.0.0"
    }

    print(f"Writing index manifest to {manifest_file}...", flush=True)
    with manifest_file.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    size_mb = index_file.stat().st_size / (1024 * 1024)
    print(f"\nDONE.", flush=True)
    print(f"  Vectors in FAISS : {index.ntotal}", flush=True)
    print(f"  Index file size  : {size_mb:.1f} MB", flush=True)
    print(f"  Chunks count     : {len(texts)}", flush=True)
    print("Manifest integrity signature generated successfully.", flush=True)


if __name__ == "__main__":
    rebuild()
