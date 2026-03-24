import json
from pathlib import Path

DOCS_JSONL = Path("data/chunks/documents.jsonl")
CHECKPOINT_FILE = Path("data/chunks/ingestion_checkpoint.json")

def create_checkpoint():
    if not DOCS_JSONL.exists():
        print("No existing documents.jsonl found.")
        return

    sources = set()
    with open(DOCS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                source = data.get("metadata", {}).get("source")
                if source:
                    sources.add(source)
            except:
                continue
    
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(list(sources), f)
    
    print(f"Checkpoint created with {len(sources)} unique files.")

if __name__ == "__main__":
    create_checkpoint()
