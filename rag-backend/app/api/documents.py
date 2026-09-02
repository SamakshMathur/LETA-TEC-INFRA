from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
from pathlib import Path

router = APIRouter()

# ── Base directory ─────────────────────────────────────────────────────────────
# Must stay in sync with config.DATA_DIR (Database_V2.0).  We read it here
# directly so documents.py can be imported independently during startup before
# the config module's lazy initialisers have all run.
_APP_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = _APP_ROOT / "Database_V2.0"

# ── Category map ───────────────────────────────────────────────────────────────
# Keys = frontend category IDs (from documentLibrary.ts CATEGORY_GROUPS)
# Values = actual folder names inside Database_V2.0
# Keep this in sync with legal_parser.py _FOLDER_MAP and router.py _DOMAIN_PATHS
CATEGORY_MAP: dict[str, str] = {
    "circulars":    "circulars(2017-2025)",
    "notifications": "Rate_notifications_2.0",
    "acts":         "CGST Acts",
    "cgst":         "CGST Acts",
    "rules":        "CGST Rules 10-08-2026",
    "igst":         "IGST Acts",
    "highcourt":    "High Court Case Laws",
    "supremecourt": "Supreme Court Case Laws",
    # Folders not yet in Database_V2.0 — return empty list gracefully
    "aars":         "AARs",
    "icai":         "ICAI",
    "forms":        "Forms",
    "faqs":         "FAQs",
    "brochures":    "Brochures",
    "flyers":       "Other APP Result",
}


@router.get("/categories")
def get_categories():
    """Returns available categories and file counts."""
    stats = {}
    for key, folder_name in CATEGORY_MAP.items():
        folder_path = BASE_DIR / folder_name
        if folder_path.exists():
            try:
                files = [
                    f for f in folder_path.rglob("*")
                    if f.is_file() and f.suffix.lower() == ".pdf"
                ]
                stats[key] = len(files)
            except Exception:
                stats[key] = 0
        else:
            stats[key] = 0
    return stats


@router.get("/list/{category}")
def list_documents(category: str):
    """Lists PDF files in a category (max 200)."""
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(status_code=404, detail=f"Unknown category '{category}'")

    folder_path = BASE_DIR / folder_name
    if not folder_path.exists():
        return []

    docs = []
    try:
        all_files = sorted(
            [f for f in folder_path.rglob("*") if f.is_file() and f.suffix.lower() == ".pdf"],
            key=lambda f: f.name.lower(),
        )
        for idx, file_path in enumerate(all_files):
            rel = str(file_path.relative_to(BASE_DIR)).replace("\\", "/")
            # Extract year from parent folder name if it's a 4-digit year
            year_part = file_path.parent.name if file_path.parent.name.isdigit() and len(file_path.parent.name) == 4 else None
            docs.append({
                "id":       f"{category}_{idx}",
                "title":    file_path.stem.replace("_", " ").replace("-", " "),
                "filename": file_path.name,
                "size":     f"{round(file_path.stat().st_size / 1024, 1)} KB",
                "path":     rel,
                "category": category,
                "year":     year_part,
            })
    except Exception as e:
        print(f"[documents] Error scanning {folder_path}: {e}")
        return []

    return docs[:200]


@router.get("/view")
def view_document(category: str, filename: str):
    """Serves a document for inline viewing or download."""
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(status_code=404, detail=f"Unknown category '{category}'")

    safe_filename = os.path.basename(filename)
    folder_path = BASE_DIR / folder_name

    # Fast direct path first
    direct = folder_path / safe_filename
    if direct.exists():
        return FileResponse(
            str(direct),
            media_type="application/pdf",
            filename=safe_filename,
        )

    # Recursive search (for year-subfolder structure like circulars)
    for found in folder_path.rglob(safe_filename):
        if found.is_file():
            return FileResponse(
                str(found),
                media_type="application/pdf",
                filename=safe_filename,
            )

    raise HTTPException(status_code=404, detail=f"'{safe_filename}' not found in {folder_name}")


@router.get("/ai-search")
def ai_search_documents(q: str = ""):
    """Placeholder AI search endpoint — returns empty list until implemented."""
    return []
