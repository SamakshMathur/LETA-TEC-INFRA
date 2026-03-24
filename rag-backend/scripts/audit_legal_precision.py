import json
from collections import Counter
import re

CHUNKS_PATH = r"c:\Users\LENOVO\Downloads\RAG-20260130T152632Z-3-001\RAG\rag-backend\data\chunks\chunks.jsonl"

def audit_chunks():
    stats = {
        "total_chunks": 0,
        "citation_count": 0,
        "structural_parts": Counter(),
        "topics": Counter(),
        "ocr_artifacts": Counter(),
        "short_chunks": 0
    }

    # User's specific "bad" patterns to check for
    bad_patterns = [
        r"worl<s", r"contracl", r"I\(one", r"AGAII", r"tr'O\]I", r"surji\)ct", r"tlilider", r"tli{der"
    ]

    with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            chunk = json.loads(line)
            stats["total_chunks"] += 1
            
            metadata = chunk.get("metadata", {})
            
            # 1. Structural Parts
            stats["structural_parts"][metadata.get("structural_part", "UNKNOWN")] += 1
            
            # 2. Topics
            stats["topics"][metadata.get("topic", "General")] += 1
            
            # 3. Citations
            if metadata.get("citations"):
                stats["citation_count"] += 1
            
            # 4. OCR Noise
            text = chunk.get("text", "")
            for pattern in bad_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    stats["ocr_artifacts"][pattern] += 1
            
            # 5. Short chunks (potential issues)
            if len(text) < 100:
                stats["short_chunks"] += 1

    print(f"--- CHUNK AUDIT RESULTS ---")
    print(f"Total Chunks: {stats['total_chunks']}")
    print(f"Chunks with Citations: {stats['citation_count']} ({stats['citation_count']/stats['total_chunks']*100:.1f}%)")
    print(f"Short Chunks (<100 chars): {stats['short_chunks']}")
    
    print("\nStructural Parts:")
    for part, count in stats["structural_parts"].most_common():
        print(f"  - {part}: {count}")
        
    print("\nTop 10 Topics:")
    for topic, count in stats["topics"].most_common(10):
        print(f"  - {topic}: {count}")
        
    print("\nOCR Artifact Residuals:")
    if not stats["ocr_artifacts"]:
        print("  Clean! No targeted artifacts found.")
    else:
        for pattern, count in stats["ocr_artifacts"].items():
            print(f"  - {pattern}: {count}")

if __name__ == "__main__":
    audit_chunks()
