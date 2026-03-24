import sys
import os
# Add parent directory to path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from pathlib import Path
from app.chunking.chunker import chunk_text
from app.config import CHUNKS_PATH
from app.ingestion.legal_parser import LegalParser

# Input is the Output of Ingestion
INPUT = Path(CHUNKS_PATH).parent / "documents.jsonl"
OUTPUT = Path(CHUNKS_PATH)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

from collections import defaultdict

def run():
    print(f"Reading from: {INPUT}")
    if not INPUT.exists():
        print("Input file not found. Run ingestion first.")
        return

    # 1. Group records by rel_path (Assemble full documents)
    documents = defaultdict(list)
    with INPUT.open(encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                rel_path = record["metadata"].get("rel_path", "unknown")
                documents[rel_path].append(record)
            except json.JSONDecodeError:
                continue

    count = 0
    with OUTPUT.open("w", encoding="utf-8") as out:
        for rel_path, pages in documents.items():
            # Sort pages by page number to ensure correct text assembly
            pages.sort(key=lambda x: x["metadata"].get("page", 0))
            
            full_text = "\n".join([p["text"] for p in pages])
            first_metadata = pages[0]["metadata"]
            doc_type = first_metadata.get("document_type", "Other")
            
            # 2. Semantic / Structural Splitting on FULL TEXT
            # New LegalParser.structural_split already handles sub-chunking large segments
            chunks_data = LegalParser.structural_split(full_text, doc_type)
            
            for idx, chunk_obj in enumerate(chunks_data):
                text = chunk_obj["text"]
                structure = chunk_obj["structure"]
                
                # 3. High-Precision Metadata Extraction per Chunk
                raw_citations = LegalParser.extract_citations(text, normalize=False)
                normalized_citations = LegalParser.extract_citations(text, normalize=True)
                topic = LegalParser.classify_topic(text)
                
                # Extract primary provisions for filtering
                primary_provisions = [c for c in normalized_citations if "SEC" in c or "RUL" in c]
                
                # Determine law type (Substantive vs Procedural)
                law_type = "general"
                raw_section_nums = [re.search(r'\d+', c).group() for c in normalized_citations if "SEC" in c and re.search(r'\d+', c)]
                if any(s in LegalParser.SUBSTANTIVE_SECTIONS for s in raw_section_nums):
                    law_type = "substantive"
                elif any(s in LegalParser.PROCEDURAL_SECTIONS for s in raw_section_nums):
                    law_type = "procedural"

                page_nums = [p["metadata"].get("page", 0) for p in pages]
                
                full_metadata = {
                    **first_metadata,
                    "topic": topic,
                    "law_type": law_type,
                    "citations": normalized_citations,
                    "raw_citations": raw_citations,
                    "provisions": primary_provisions,
                    "section_type": structure,  # Changed from structural_part
                    "pages": sorted(list(set(page_nums)))
                }
                
                # 4. Deterministic ID Generation
                chunk_id = LegalParser.generate_chunk_id(full_metadata, structure, text, idx)
                
                out.write(json.dumps({
                    "chunk_id": chunk_id,
                    "text": text,
                    "metadata": full_metadata
                }, ensure_ascii=False) + "\n")
            count += 1
            if count % 10 == 0:
                print(f"Chunked {count} documents...")
            
    print(f"Chunking complete. Processed {count} documents.")
    print(f"Output saved to: {OUTPUT}")

if __name__ == "__main__":
    run()