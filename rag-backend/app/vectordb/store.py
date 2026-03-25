import faiss
import json
import logging
from pathlib import Path
from app.embeddings.embedder import embed_texts, VECTOR_DIM

logger = logging.getLogger(__name__)


def build_vector_store(chunks_path: Path, index_path: Path):
    """Build FAISS index from chunks.jsonl with dimension validation and integrity checks."""
    texts = []
    metadatas = []
    skipped = 0

    logger.info(f"Loading chunks from {chunks_path}...")
    if not chunks_path.exists():
        logger.error(f"Chunks file not found: {chunks_path}")
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    with chunks_path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                text = record.get("text", "").strip()
                if not text:
                    skipped += 1
                    continue
                texts.append(text)
                meta = record.get("metadata", {})
                meta["chunk_id"] = record.get("chunk_id")
                metadatas.append(meta)
            except json.JSONDecodeError:
                logger.warning(f"Malformed JSON at line {line_num} — skipped")
                skipped += 1
            except KeyError as e:
                logger.warning(f"Missing key {e} at line {line_num} — skipped")
                skipped += 1

    if skipped > 0:
        logger.warning(f"Skipped {skipped} lines during chunk loading")

    if not texts:
        logger.error("No valid chunks found — cannot build index")
        raise ValueError("No valid chunks to embed")

    logger.info(f"Loaded {len(texts)} chunks. Generating embeddings...")

    # Generate embeddings
    embeddings = embed_texts(texts).astype("float32")
    logger.info(f"Embeddings shape: {embeddings.shape}")

    # Validate embedding dimensions match config
    if embeddings.shape[1] != VECTOR_DIM:
        raise ValueError(
            f"Embedding dimension {embeddings.shape[1]} != configured VECTOR_DIM {VECTOR_DIM}. "
            f"Check EMBEDDING_MODEL and VECTOR_DIM in config.py"
        )

    # IndexFlatIP with normalized vectors = cosine similarity (optimal for BGE models)
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(embeddings)

    # Ensure output directory exists
    index_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Saving index to {index_path}...")
    faiss.write_index(index, str(index_path))

    # Save metadata alongside
    meta_path = index_path.with_suffix(".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadatas, f, ensure_ascii=False, indent=2)

    # Integrity check
    verify_index = faiss.read_index(str(index_path))
    if verify_index.ntotal != len(texts):
        logger.error(f"Integrity check failed: index has {verify_index.ntotal} vectors, expected {len(texts)}")
    else:
        logger.info(
            f"Vector store built successfully: {verify_index.ntotal} vectors, "
            f"dim={verify_index.d}, index={index_path}, meta={meta_path}"
        )
