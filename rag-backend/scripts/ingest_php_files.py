import os
import json
import re
from pathlib import Path

# Add parent directory to path to allow imports from app
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.clean_text import clean_text
from app.config import DATA_DIR, CHUNKS_PATH

INPUT_DIR = Path(DATA_DIR)
DOCS_OUTPUT = Path(CHUNKS_PATH).parent / "documents.jsonl"

def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def process_php_html(path):
    print(f"Processing PHP/HTML: {path}")
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Strip simple tags
        text = strip_html_tags(content)
        text = clean_text(text)
        
        if len(text.strip()) < 100:
            return

        record = {
            "text": text,
            "metadata": {
                "source": str(path.relative_to(INPUT_DIR.parent)),
                "type": "case_law_html"
            }
        }
        
        with DOCS_OUTPUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
    except Exception as e:
        print(f"Error reading PHP {path}: {e}")

def run():
    count = 0
    for root, _, files in os.walk(INPUT_DIR):
        for file in files:
            if file.lower().endswith('.php'):
                file_path = Path(root) / file
                process_php_html(file_path)
                count += 1
    print(f"Supplemental PHP ingestion complete. Processed {count} files.")

if __name__ == "__main__":
    run()
