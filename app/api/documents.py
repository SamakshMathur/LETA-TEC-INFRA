from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import os
from pathlib import Path
from typing import List, Dict

router = APIRouter()

# Base path for documents
# Use absolute path relative to this file to avoid CWD issues
BASE_DIR = Path(__file__).resolve().parent.parent.parent / "RAG_INFORMATION_DATABASE"

# Category Mapping
CATEGORY_MAP = {
    "circulars": "Circulars",
    "notifications": "Circulars", # Fallback since no Notifications folder found
    "forms": "Forms",
    "flyers": "Other APP Result", # Fallback
    "faqs": "FAQs"
}

@router.get("/categories")
def get_categories():
    """Returns available categories and file counts."""
    stats = {}
    
    # Debug print
    print(f"DEBUG: BASE_DIR resolved to: {BASE_DIR}")
    
    for key, folder_name in CATEGORY_MAP.items():
        folder_path = BASE_DIR / folder_name
        if folder_path.exists():
            # Count files
            try:
                # Count valid files only (PDFs usually, but count all for stats)
                files = [f for f in folder_path.rglob("*") if f.is_file() and f.suffix.lower() == '.pdf']
                stats[key] = len(files)
            except Exception as e:
                print(f"Error counting {folder_name}: {e}")
                stats[key] = 0
        else:
            print(f"Folder not found: {folder_path}")
            stats[key] = 0
    return stats

@router.get("/list/{category}")
def list_documents(category: str):
    """Lists files in a category."""
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(status_code=404, detail="Category not found")
    
    folder_path = BASE_DIR / folder_name
    if not folder_path.exists():
        return []

    docs = []
    try:
        # Case insensitive search for PDFs
        all_files = [f for f in folder_path.rglob("*") if f.is_file() and f.suffix.lower() == '.pdf']
        
        for idx, file_path in enumerate(all_files): 
            docs.append({
                "id": f"{category}_{idx}",
                "title": file_path.name,
                "desc": f"Document from {folder_name}",
                "date": "N/A", 
                "size": f"{round(file_path.stat().st_size / 1024, 1)} KB",
                "filename": file_path.name,
                "path": str(file_path.relative_to(BASE_DIR)).replace("\\", "/")
            })
    except Exception as e:
        print(f"Error scanning {folder_path}: {e}")
        return []
    
    return docs[:100] # Limit to 100 for performance

@router.get("/view")
def view_document(category: str, filename: str):
    """Serves a document for viewing/downloading."""
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Security check: prevent directory traversal
    safe_filename = os.path.basename(filename)
    
    # We might need to find the file recursively if we used rglob above
    # Ideally search for it
    target_path = None
    folder_path = BASE_DIR / folder_name
    
    # optimization: Try direct path first
    direct_path = folder_path / safe_filename
    if direct_path.exists():
        target_path = direct_path
    else:
        # Search recursively
        found = list(folder_path.rglob(safe_filename))
        if found:
            target_path = found[0]
            
    if not target_path or not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(
        path=target_path,
        filename=safe_filename,
        media_type='application/pdf'
    )
