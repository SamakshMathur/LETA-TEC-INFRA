import sys
import os
from pathlib import Path
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.run_ingestion import process_pdf, DOCS_OUTPUT

# Target ONLY the FAQ folder
FAQ_DIR = Path("RAG_INFORMATION_DATABASE/FAQs")

def fast_track():
    print(f"--- Fast-Track Ingestion for FAQs ---")
    print(f"Targeting: {FAQ_DIR.absolute()}")
    
    # We do NOT unlink DOCS_OUTPUT, but check what's already there?
    # Actually, if we want to add to the existing work, we just append.
    # The run() script in run_ingestion.py unlinks. 
    # For fast-track, let's just create a separate files list and process them.
    
    count = 0
    for root, _, files in os.walk(FAQ_DIR):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() == ".pdf":
                process_pdf(file_path)
                count += 1
                
    print(f"Fast-Track complete. Processed {count} FAQ documents.")

if __name__ == "__main__":
    fast_track()
