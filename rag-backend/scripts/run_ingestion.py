import sys
import os
from pathlib import Path
import json

# Add parent directory to path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
from app.ingestion.docx_reader import extract_text_from_docx
from app.ingestion.excel_reader import extract_text_from_excel
from app.utils.legal_cleaner import LegalCleaner
from app.config import DATA_DIR, CHUNKS_PATH

# Config
INPUT_DIR = Path(DATA_DIR)
OUTPUT_FILE = Path(CHUNKS_PATH)
CHECKPOINT_FILE = OUTPUT_FILE.parent / "ingestion_checkpoint.json"

# Ensure output directory exists
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Temporary storage for raw documents before chunking
DOCS_OUTPUT = OUTPUT_FILE.parent / "documents.jsonl"

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_checkpoint(processed_set):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(list(processed_set), f)

def write_record(record):
    """Write a single record to the output JSONL file if it passes quality checks."""
    text = record.get("text", "")
    if not text.strip():
        return
        
    # Layer 1-3 Cleaning & Quality Gate
    cleaned_text = LegalCleaner.clean(text)
    if LegalCleaner.is_garbage(cleaned_text, threshold=0.5): # Relaxed for raw docs
        return
        
    record["text"] = cleaned_text
    
    with DOCS_OUTPUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def is_text_meaningful(text):
    """
    Heuristic to check if text is valid English/meaningful.
    Returns True if > 40% of words are alphanumeric and sensible length.
    """
    if not text: return False
    words = text.split()
    if not words: return False
    
    # Check for mojibake or OCR garbage (too many non-ascii or random symbols)
    valid_words = 0
    total_words = len(words)
    
    for w in words:
        # Simple heuristic: Alpha-only and length > 2
        if w.isalpha() and len(w) > 2:
            valid_words += 1
            
    ratio = valid_words / total_words
    return ratio > 0.4  # At least 40% valid English-looking words

from app.ingestion.legal_parser import LegalParser

def process_pdf(path, rel_path):
    print(f"Processing PDF: {path}")
    try:
        pages = extract_text_from_pdf(path)
        combined_text = " ".join([p["text"] for p in pages]) if pages else ""
        
        # Classification & Legal Parsing
        cls_info = LegalParser.classify_folder(rel_path)
        for p in pages:
            # Clean page text specifically
            p["text"] = LegalCleaner.clean(p["text"])
            p["metadata"].update(cls_info)
            p["metadata"]["rel_path"] = rel_path
            write_record(p)
            
    except Exception as e:
        print(f"Error reading PDF {path}: {e}")

def run():
    print(f"Starting LETA Legal-Aware Ingestion from: {INPUT_DIR.absolute()}")
    
    # We clear the output for a fresh legal rebuild as requested by user
    if DOCS_OUTPUT.exists():
        DOCS_OUTPUT.unlink()
        
    processed_sources = set() # Force re-ingestion for quality upgrade

    count = 0
    newly_processed = 0
    for root, _, files in os.walk(INPUT_DIR):
        if "__MACOSX" in root: continue
        for file in files:
            file_path = Path(root) / file
            rel_path = str(file_path.relative_to(INPUT_DIR)) # Correct relative path from DB root
            
            if file.startswith(".") or file.startswith("._"): continue
            ext = file_path.suffix.lower()
            
            success = False
            if ext == ".pdf":
                process_pdf(file_path, rel_path)
                success = True
            elif ext == ".docx":
                try:
                    pages = extract_text_from_docx(file_path)
                    cls_info = LegalParser.classify_folder(rel_path)
                    for p in pages: 
                        p["metadata"].update(cls_info)
                        p["metadata"]["rel_path"] = rel_path
                        write_record(p)
                    success = True
                except Exception as e:
                    print(f"Error reading DOCX {file_path}: {e}")
            elif ext in [".xlsx", ".xls"]:
                # Optimization: Excel files in root (like Sections List) are processed later or ignored as text
                if file_path.parent == INPUT_DIR:
                    print(f"Skipping Index Excel for main text ingestion: {file}")
                    continue
                try:
                    pages = extract_text_from_excel(file_path)
                    cls_info = LegalParser.classify_folder(rel_path)
                    for p in pages: 
                        p["metadata"].update(cls_info)
                        p["metadata"]["rel_path"] = rel_path
                        write_record(p)
                    success = True
                except Exception as e:
                    print(f"Error reading EXCEL {file_path}: {e}")
            
            if success:
                newly_processed += 1

            count += 1
            if count % 20 == 0:
                print(f"Ingested {count} files...")

    print(f"Ingestion complete. Output saved to: {DOCS_OUTPUT}")

if __name__ == "__main__":
    run()