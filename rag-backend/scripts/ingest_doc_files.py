import os
import sys
import json
from pathlib import Path

# Add parent directory to path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.clean_text import clean_text
from app.config import DATA_DIR, CHUNKS_PATH
import re

INPUT_DIR = Path(DATA_DIR)
DOCS_OUTPUT = Path(CHUNKS_PATH).parent / "documents.jsonl"

def extract_strings_from_doc(file_path):
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        ascii_strings = re.findall(b'[ -~]{4,}', content)
        text_ascii = "\n".join([s.decode('ascii', errors='ignore') for s in ascii_strings])
        utf16_strings = re.findall(b'(?:[\x20-\x7E][\x00]){4,}', content)
        text_utf16 = "\n".join([s.decode('utf-16le', errors='ignore') for s in utf16_strings])
        combined = text_ascii + "\n" + text_utf16
        lines = [line.strip() for line in combined.split('\n') if len(line.strip()) > 10]
        return "\n".join(lines)
    except Exception as e:
        print(f"Error extracting from {file_path}: {e}")
        return ""

def write_record(record):
    if not record.get("text") or not record["text"].strip():
        return
    record["text"] = clean_text(record["text"])
    with DOCS_OUTPUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def run():
    print(f"Starting supplemental doc ingestion from: {INPUT_DIR}")
    count = 0
    for root, _, files in os.walk(INPUT_DIR):
        if "__MACOSX" in root: continue
        for file in files:
            file_path = Path(root) / file
            if file.startswith(".") or file.startswith("._"): continue
            if file_path.suffix.lower() == ".doc":
                print(f"Processing legacy doc: {file_path}")
                text = extract_strings_from_doc(file_path)
                if text:
                    record = {
                        "text": text,
                        "metadata": {
                            "source": str(file_path.relative_to(INPUT_DIR.parent)),
                            "type": "doc_legacy_string_extracted"
                        }
                    }
                    write_record(record)
                    count += 1
    print(f"Done. Processed {count} .doc files.")

if __name__ == "__main__":
    run()
