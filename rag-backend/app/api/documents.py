import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# ── Base directory ─────────────────────────────────────────────────────────────
# Dynamically resolves Database_V2.0 across root, nested, and environment locations.
_APP_ROOT = Path(__file__).resolve().parents[2]  # rag-backend/


def _resolve_base_dir() -> Path:
    env_path = os.getenv("DATA_DIR")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    candidates = [
        _APP_ROOT / "Database_V2.0",
        _APP_ROOT / "RAG_INFORMATION_DATABASE" / "NEW DATABASE" / "Database_V2.0",
        _APP_ROOT.parent / "Database_V2.0",
        _APP_ROOT / "RAG_INFORMATION_DATABASE",
    ]
    for c in candidates:
        if c.exists():
            return c
    return _APP_ROOT / "Database_V2.0"

BASE_DIR = _resolve_base_dir()

# ── Category map ───────────────────────────────────────────────────────────────
# Keys = frontend category IDs (from documentLibrary.ts CATEGORY_GROUPS)
# Values = actual folder names inside Database_V2.0
CATEGORY_MAP: dict[str, str] = {
    "circulars":     "circulars(2017-2025)",
    "notifications": "Rate_notifications_2.0",
    "acts":          "CGST Acts",
    "cgst":          "CGST Acts",
    "rules":         "CGST Rules 10-08-2026",
    "igst":          "IGST Acts",
    "highcourt":     "High Court Case Laws",
    "supremecourt":  "Supreme Court Case Laws",
    # Folders not yet in Database_V2.0 — return empty list gracefully
    "aars":          "AARs",
    "icai":          "ICAI",
    "forms":         "Forms",
    "faqs":          "FAQs",
    "brochures":     "Brochures",
    "flyers":        "Other APP Result",
}


def _extract_year(file_path: Path) -> Optional[str]:
    """Extract year from subfolder or filename pattern (2017-2026)."""
    if file_path.parent.name.isdigit() and len(file_path.parent.name) == 4:
        return file_path.parent.name
    m = re.search(r"\b(20[12]\d)\b", file_path.name)
    if m:
        return m.group(1)
    return None


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


def _scan_category_docs(category: str, limit: int = 300) -> List[dict]:
    """Internal helper to scan PDF files for a given category key."""
    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        return []

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
            year_part = _extract_year(file_path)
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

    return docs[:limit]


def _group_by_year(category_id: str) -> dict:
    """Group all documents in a category by year (descending)."""
    all_docs = _scan_category_docs(category_id, limit=500)
    grouped: dict = {}
    for doc in all_docs:
        year = doc.get("year") or "other"
        grouped.setdefault(year, []).append(doc)
    sorted_grouped = {}
    for y in sorted((k for k in grouped if k != "other"), reverse=True):
        sorted_grouped[y] = grouped[y]
    if "other" in grouped:
        sorted_grouped["other"] = grouped["other"]
    return sorted_grouped


@router.get("/list/circulars/by-year")
def list_circulars_by_year():
    """Return circulars grouped by year: { '2025': [...], '2024': [...], ... }"""
    return _group_by_year("circulars")


@router.get("/list/notifications/by-year")
def list_notifications_by_year():
    """Return notifications grouped by year: { '2025': [...], '2024': [...], ... }"""
    return _group_by_year("notifications")


@router.get("/list/{category}")
def list_documents(category: str):
    """Lists PDF files in a category (or all categories if category='all')."""
    if category.lower() == "all":
        docs = []
        for cat in CATEGORY_MAP:
            docs.extend(_scan_category_docs(cat, limit=50))
        return docs[:400]

    folder_name = CATEGORY_MAP.get(category.lower())
    if not folder_name:
        raise HTTPException(status_code=404, detail=f"Unknown category '{category}'")

    return _scan_category_docs(category, limit=200)


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
@router.get("/ai_search")
def ai_search_documents(q: str = ""):
    """Placeholder AI search endpoint — returns empty list until implemented."""
    return []
