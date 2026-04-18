import os
import sys
import time
from typing import List, Dict, Any

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_template_collection
from app.embeddings.embedder import embed_texts
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.docx_reader import extract_text_from_docx, extract_text_from_doc
from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf

# Configuration
DATA_DIRS = [
    os.path.join("RAG_INFORMATION_DATABASE", "Responses"),
    os.path.join("RAG_INFORMATION_DATABASE", "Notification"),
    os.path.join("RAG_INFORMATION_DATABASE", "Circulars")
]
BATCH_SIZE = 50  # Increased for faster ingestion of 900+ files

def get_files_recursively(directory: str) -> List[str]:
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Skip junk and temp files
            if file.lower().endswith(('.pdf', '.docx', '.doc')) and not file.startswith('~') and '__MACOSX' not in root:
                file_list.append(os.path.join(root, file))
    return file_list

def ingest_templates():
    print(f"Starting ingestion from {DATA_DIRS}...")
    collection = get_template_collection()
    if collection is None:
        print("Error: Could not connect to MongoDB template collection.")
        return

    # REMOVED: Clear existing templates for a fresh start as requested
    # We will now do INCREMENTAL ingestion to save time
    print("Starting incremental ingestion (checking for duplicates)...")

    template_files = []
    for data_dir in DATA_DIRS:
        print(f"  - Searching in {data_dir}...")
        template_files.extend(get_files_recursively(data_dir))
    print(f"Found {len(template_files)} files to check/process.")

    total_inserted = 0
    total_skipped = 0
    batch_docs = []
    batch_texts = []

    for i, file_path in enumerate(template_files):
        filename = os.path.basename(file_path)
        
        # Duplicate Check
        existing = collection.find_one({"file_path": file_path})
        if existing:
            total_skipped += 1
            if total_skipped % 50 == 0:
                print(f"  - Already ingested {total_skipped} files so far...")
            continue

        print(f"[{i+1}/{len(template_files)}] Processing: {filename}")
        
        try:
            extracted_text = ""
            if filename.lower().endswith(".pdf"):
                # Try normal extraction first, fallback to OCR if empty
                pages = extract_text_from_pdf(file_path)
                extracted_text = "\n".join(p["text"] for p in pages)
                if not extracted_text.strip():
                    print(f"  - No text in {filename}, attempting OCR...")
                    pages = extract_text_from_scanned_pdf(file_path)
                    extracted_text = "\n".join(p["text"] for p in pages)
            
            elif filename.lower().endswith(".docx"):
                blocks = extract_text_from_docx(file_path)
                extracted_text = "\n".join(b["text"] for b in blocks)
            
            elif filename.lower().endswith(".doc"):
                blocks = extract_text_from_doc(file_path) # Uses antiword/fallback
                extracted_text = "\n".join(b["text"] for b in blocks)

            if not extracted_text.strip():
                print(f"  - Skip: No text extracted from {filename}")
                continue

            # Guess metadata from filename and path
            # Remove "S. No. XXX -" prefix if exists
            clean_title = filename.rsplit(".", 1)[0]
            if " - " in clean_title:
                parts = clean_title.split(" - ", 1)
                if "S. No." in parts[0] or "S No" in parts[0]:
                    clean_title = parts[1]
            
            title = clean_title.replace("_", " ").replace("-", " ").title().strip()
            
            # Simple category inference based on directory or filename
            category = "General"
            if "ITC" in title.upper(): category = "ITC"
            elif "REFUND" in title.upper(): category = "Refund"
            elif "APPEAL" in title.upper(): category = "Appeal"
            elif "DRC" in title.upper(): category = "Demand/Recovery"
            elif "REGISTRATION" in title.upper() or "CANCEL" in title.upper(): category = "Registration"
            
            stage = "Draft"
            if "SCN" in title.upper() or "NOTICE" in title.upper() or "REPLY" in title.upper(): stage = "Response"
            elif "APPEAL" in title.upper(): stage = "Appeal"
            elif "LETTER" in title.upper(): stage = "Communication"

            doc = {
                "title": title,
                "category": category,
                "stage": stage,
                "sub_category": "",
                "keywords": [k.strip() for k in title.split() if len(k) > 3],
                "summary": f"Litigation template: {title}",
                "content": extracted_text,
                "file_path": file_path,
                "ingested_at": time.time()
            }
            
            batch_docs.append(doc)
            batch_texts.append(extracted_text[:4000]) # Use a snippet for embedding to save tokens/speed

            if len(batch_docs) >= BATCH_SIZE:
                save_batch(collection, batch_docs, batch_texts)
                total_inserted += len(batch_docs)
                batch_docs = []
                batch_texts = []

        except Exception as e:
            print(f"  - Error processing {filename}: {str(e)}")

    # Final batch
    if batch_docs:
        save_batch(collection, batch_docs, batch_texts)
        total_inserted += len(batch_docs)

    print(f"\nIngestion Complete! Total templates inserted: {total_inserted}")

def save_batch(collection, docs, texts):
    print(f"  - Generating embeddings for batch of {len(docs)}...")
    try:
        embeddings = embed_texts(texts)
        for j, doc in enumerate(docs):
            doc["embedding"] = embeddings[j].tolist()
        
        collection.insert_many(docs)
        print(f"  - Inserted {len(docs)} documents.")
    except Exception as e:
        print(f"  - Batch Error: {str(e)}")

if __name__ == "__main__":
    ingest_templates()
