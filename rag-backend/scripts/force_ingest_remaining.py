"""
Force-ingest the 30 missing files from Responses/ and Other APP Result/
that were skipped due to path length or encoding issues.
Appends directly to documents.jsonl without touching the checkpoint.
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.docx_reader import extract_text_from_docx
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
from app.ingestion.clean_text import clean_text
from app.config import DATA_DIR

INPUT_DIR = Path(DATA_DIR)
DOCS_OUTPUT = Path("data/chunks/documents.jsonl")

TARGET_FOLDERS = ["Responses", "Other APP Result"]

def write_record(text, source):
    text = clean_text(text)
    if not text or len(text.strip()) < 50:
        return False
    record = {"text": text, "metadata": {"source": source}}
    with DOCS_OUTPUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True

# Get already indexed sources
indexed = set()
with open(DOCS_OUTPUT, encoding="utf-8", errors="ignore") as f:
    for line in f:
        try:
            src = json.loads(line).get("metadata", {}).get("source", "")
            if src:
                indexed.add(src)
        except:
            continue

print(f"Already indexed: {len(indexed)} unique sources")

count = 0
errors = 0
for folder in TARGET_FOLDERS:
    folder_path = INPUT_DIR / folder
    if not folder_path.exists():
        print(f"Folder not found: {folder_path}")
        continue
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.startswith(".") or file.startswith("._"):
                continue
            fpath = Path(root) / file
            # Use \\\\?\\ prefix to handle long paths on Windows
            fpath_long = Path("\\\\?\\" + str(fpath.absolute()))
            rel = str(fpath.relative_to(INPUT_DIR.parent))
            
            if rel in indexed:
                continue
            
            ext = fpath.suffix.lower()
            try:
                if ext == ".pdf":
                    pages = extract_text_from_pdf(str(fpath_long))
                    for p in pages:
                        write_record(p.get("text", ""), rel)
                    count += 1
                elif ext == ".docx":
                    pages = extract_text_from_docx(str(fpath_long))
                    for p in pages:
                        write_record(p.get("text", ""), rel)
                    count += 1
                else:
                    # Try reading as text
                    try:
                        text = fpath_long.read_text(encoding="utf-8", errors="ignore")
                        write_record(text, rel)
                        count += 1
                    except:
                        pass
                print(f"  ✓ Ingested: {file}")
            except Exception as e:
                print(f"  ✗ Error on {file}: {e}")
                errors += 1

print(f"\nDone. Ingested {count} files, {errors} errors.")
