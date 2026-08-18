import json
from pathlib import Path
from typing import List

MAX_TOKENS = 550
OVERLAP_TOKENS = 100

def approx_token_len(text: str) -> int:
    # rough but stable approximation
    return len(text.split())

def chunk_text(paragraphs: List[str]):
    chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        para_len = approx_token_len(para)

        if current_len + para_len > MAX_TOKENS:
            chunks.append(" ".join(current_chunk))

            # overlap
            overlap_words = " ".join(current_chunk).split()[-OVERLAP_TOKENS:]
            current_chunk = [" ".join(overlap_words), para]
            current_len = approx_token_len(current_chunk[0]) + para_len
        else:
            current_chunk.append(para)
            current_len += para_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks