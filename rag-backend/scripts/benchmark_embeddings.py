import os
import sys
import time
import torch
import numpy as np
from sentence_transformers import SentenceTransformer

# Resolve app root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import EMBEDDING_MODEL

def run_benchmark(device, batch_size, texts):
    print(f"Running benchmark on {device.upper()} with batch_size={batch_size}...", flush=True)
    try:
        model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    except Exception as e:
        print(f"ERROR: Failed to load model on {device}: {e}", flush=True)
        return None

    # Pre-warm
    model.encode(texts[:batch_size], batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)

    t0 = time.time()
    embeddings = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    t1 = time.time()

    duration = t1 - t0
    throughput_texts = len(texts) / duration
    # Estimate tokens: 1.35 * words
    total_words = sum(len(t.split()) for t in texts)
    throughput_tokens = (total_words * 1.35) / duration

    print(f"  --> Completed in {duration:.2f}s | Throughput: {throughput_texts:.1f} texts/s ({throughput_tokens:.1f} tokens/s)", flush=True)
    return {
        "duration_s": duration,
        "throughput_texts_per_s": throughput_texts,
        "throughput_tokens_per_s": throughput_tokens
    }

def main():
    print("=== BAAI/bge-large-en-v1.5 EMBEDDING BENCHMARK ===", flush=True)
    print("PyTorch version:", torch.__version__, flush=True)
    mps_available = torch.backends.mps.is_available()
    print("MPS available:", mps_available, flush=True)

    devices_to_test = ["cpu"]
    if mps_available:
        devices_to_test.append("mps")

    # Generate 128 representative legal text samples
    sample_text = "Subject to the provisions of Section 16, a registered person shall be entitled to take credit of input tax. " * 8
    texts = [sample_text + f" (Sample chunk {i})" for i in range(128)]

    results = {}
    for dev in devices_to_test:
        results[dev] = {}
        for bs in [8, 16, 32, 64]:
            res = run_benchmark(dev, bs, texts)
            if res:
                results[dev][bs] = res

    # Find best config
    best_dev = "cpu"
    best_bs = 8
    best_rate = 0.0

    for dev, bs_results in results.items():
        for bs, res in bs_results.items():
            if res["throughput_texts_per_s"] > best_rate:
                best_rate = res["throughput_texts_per_s"]
                best_dev = dev
                best_bs = bs

    print("\n=== BENCHMARK RESULTS SUMMARY ===", flush=True)
    for dev, bs_results in results.items():
        print(f"\nDevice: {dev.upper()}")
        for bs, res in bs_results.items():
            print(f"  Batch size {bs:2d} : {res['throughput_texts_per_s']:5.1f} texts/s | {res['throughput_tokens_per_s']:7.1f} tokens/s")

    print(f"\nRecommended Optimal Configuration:")
    print(f"  Device     : {best_dev.upper()}")
    print(f"  Batch Size : {best_bs}")
    print(f"  Throughput : {best_rate:.1f} texts/s")

if __name__ == "__main__":
    main()
