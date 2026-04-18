from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
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
    "notifications": "Notification", 
    "forms": "Forms",
    "flyers": "Other APP Result",
    "brochures": "Brochures",
    "faqs": "FAQs",
    "reports": "generated_reports",
    "aars": "AAR",
    "highcourt": "High Court Case Laws",
    "supremecourt": "Supreme Court Case Laws",
    "acts": "Act",
    "cgst": "CGST",
    "export": "Export",
    "igst": "IGST",
    "rules": "Rules",
    "icai": "ICAI",
    "responses": "Responses"
}

@router.get("/health")
def health():
    return {"status": "ok", "service": "documents"}

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
                # Count all supported files
                files = [f for f in folder_path.rglob("*") if f.is_file() and f.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.txt']]
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
        # Case insensitive search for all supported files
        all_files = [f for f in folder_path.rglob("*") if f.is_file() and f.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.txt']]
        
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
def view_document(category: str, filename: str, download: bool = False):
    import urllib.parse
    
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('utf-8', errors='replace').decode('utf-8')) # Fallback
        except Exception:
            pass

    try:
        # Decode filename just in case
        filename = urllib.parse.unquote(filename)
        safe_filename = os.path.basename(filename)
        
        safe_print(f"DEBUG: view_document called with category='{category}', filename='{filename}'")
        
        target_path = None

        if category.lower() in ["all", "any", "global", "ai"]:
            # Search ALL categories
            safe_print(f"DEBUG: Global search for {safe_filename}...")
            for cat_key, folder_name in CATEGORY_MAP.items():
                folder_path = BASE_DIR / folder_name
                if folder_path.exists():
                    # Direct check first
                    possible_path = folder_path / safe_filename
                    if possible_path.exists():
                        target_path = possible_path
                        safe_print(f"DEBUG: Found direct match: {target_path}")
                        break
                    # Recursive check
                    found = list(folder_path.rglob(safe_filename))
                    if found:
                        target_path = found[0]
                        safe_print(f"DEBUG: Found recursive match: {target_path}")
                        break
        else:
            # Specific category search
            folder_name = CATEGORY_MAP.get(category.lower())
            if not folder_name:
                raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
            
            folder_path = BASE_DIR / folder_name
            
            # optimization: Try direct path first
            direct_path = folder_path / safe_filename
            safe_print(f"DEBUG: Checking direct path: {direct_path}")
            if direct_path.exists():
                target_path = direct_path
                safe_print(f"DEBUG: Found direct match: {target_path}")
            else:
                # Search recursively
                safe_print(f"DEBUG: Searching recursively in {folder_path}")
                found = list(folder_path.rglob(safe_filename))
                if found:
                    target_path = found[0]
                    safe_print(f"DEBUG: Found recursive match: {target_path}")
                else:
                    safe_print(f"DEBUG: File not found in {folder_path}")

        if not target_path or not target_path.exists():
            safe_print(f"DEBUG: File not found anywhere.")
            raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found in library.")
            
        # Prepare Response
        headers = {
            "Content-Disposition": f"{'attachment' if download else 'inline'}; filename=\"{safe_filename}\"",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }

        try:
            with open(target_path, "rb") as f:
                content = f.read()
            safe_print(f"DEBUG: Successfully read {len(content)} bytes via manual read. Download={download}")
            # Determine media type based on extension
            media_types = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.txt': 'text/plain',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            ext = os.path.splitext(target_path)[1].lower()
            media_type = media_types.get(ext, 'application/octet-stream')

            return Response(
                content=content, 
                media_type=media_type,
                headers=headers
            )
        except Exception as read_err:
            safe_print(f"Manual read failed: {read_err}. Trying FileResponse...")
            return FileResponse(
                path=str(target_path),
                filename=safe_filename,
                media_type='application/pdf',
                content_disposition_type='attachment' if download else 'inline'
            )

    except HTTPException:
        raise
    except Exception as e:
        safe_print(f"ERROR in view_document: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})
@router.get("/ai_search")
async def ai_search(query: str = Query(...)):
    """AI-powered semantic search across the document library."""
    from app.dependencies import get_retriever
    try:
        retriever = get_retriever()
        if not retriever or not retriever.index:
            return []
            
        # Perform semantic hybrid search
        results = retriever.search(query, top_k=20)
        
        # Format results for the Netflix-style UI
        formatted_results = []
        for res in results:
            source = res.get("source", "")
            # Deduce category from source path/name
            category = "all"
            for key, folder_name in CATEGORY_MAP.items():
                if folder_name.lower() in source.lower():
                    category = key
                    break
            
            formatted_results.append({
                "id": f"ai_{res.get('chunk_id', source)}",
                "title": os.path.basename(source),
                "category": category,
                "path": source,
                "desc": res.get("text", "")[:150] + "...",
                "score": round(float(res.get("_rerank_score", res.get("_debug_score", 0))), 4)
            })
            
        return formatted_results
    except Exception as e:
        print(f"AI Search Error: {e}")
        return []
