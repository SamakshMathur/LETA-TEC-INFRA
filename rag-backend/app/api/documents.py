import os
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from app.services.document_discovery import DocumentDiscoveryService

router = APIRouter()

# Preserved for backward-compatibility with direct module imports
BASE_DIR = DocumentDiscoveryService.get_base_dir()


def _get_category_map() -> Dict[str, str]:
    """Generates legacy category map dynamically from discovered physical folders."""
    categories = DocumentDiscoveryService.discover_categories()
    return {k: (v.get("folder") or k) for k, v in categories.items()}


CATEGORY_MAP = _get_category_map()


@router.get("/categories")
def get_categories() -> Dict[str, int]:
    """Returns available categories and live file counts for the Document Library."""
    categories = DocumentDiscoveryService.discover_categories()
    return {k: v["files"] for k, v in categories.items()}


@router.get("/registry/summary")
def get_registry_summary() -> Dict[str, Any]:
    """Returns detailed category registry with labels, file counts, sizes, and dynamic flags."""
    categories = DocumentDiscoveryService.discover_categories()
    base_dir = DocumentDiscoveryService.get_base_dir()
    total_files = sum(c["files"] for c in categories.values())
    total_mb = round(sum(c["size_mb"] for c in categories.values()), 2)
    return {
        "base_dir": str(base_dir),
        "total_documents": total_files,
        "total_storage_mb": total_mb,
        "categories": categories,
    }


@router.get("/list/circulars/by-year")
def list_circulars_by_year():
    """Return circulars grouped by year: { '2025': [...], '2024': [...], ... }"""
    return DocumentDiscoveryService.get_year_breakdown("circulars")


@router.get("/list/notifications/by-year")
def list_notifications_by_year():
    """Return notifications grouped by year: { '2025': [...], '2024': [...], ... }"""
    return DocumentDiscoveryService.get_year_breakdown("notifications")


@router.get("/list/{category}/by-year")
def list_category_by_year(category: str):
    """Dynamic year breakdown endpoint for ANY category (Circulars, Rules, AAR, etc.)."""
    return DocumentDiscoveryService.get_year_breakdown(category)


@router.get("/list/{category}")
def list_documents(
    category: str,
    year: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200),
    skip: int = Query(0)
):
    """Lists actual physical documents in a category with live metadata and indexing state."""
    docs = DocumentDiscoveryService.discover_documents(
        category=category,
        year=year,
        search=search,
        limit=limit,
        skip=skip
    )
    if not docs and category.lower() not in DocumentDiscoveryService.discover_categories() and category.lower() != "all":
        raise HTTPException(status_code=404, detail=f"Unknown category '{category}'")
    return docs


@router.get("/view")
def view_document(category: str, filename: str):
    """Serves a document for inline viewing or download."""
    file_path = DocumentDiscoveryService.get_document_file(category, filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in category '{category}'")

    safe_filename = os.path.basename(filename)
    return FileResponse(
        str(file_path),
        media_type="application/pdf",
        filename=safe_filename,
    )


@router.get("/ai-search")
@router.get("/ai_search")
def ai_search_documents(q: str = ""):
    """Placeholder AI search endpoint."""
    return []
