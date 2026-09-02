import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# Base root resolution: rag-backend/
_APP_ROOT = Path(__file__).resolve().parents[2]


def resolve_base_dir() -> Path:
    """
    Dynamically locate the source document directory (Database_V2.0).
    Checks DATA_DIR env var, standard locations, and nested repository paths.
    """
    env_path = os.getenv("DATA_DIR")
    if env_path and Path(env_path).exists():
        try:
            next(Path(env_path).iterdir(), None)
            return Path(env_path)
        except Exception:
            pass

    candidates = [
        _APP_ROOT / "Database_V2.0",
        _APP_ROOT / "RAG_INFORMATION_DATABASE" / "NEW DATABASE" / "Database_V2.0",
        _APP_ROOT / "RAG_INFORMATION_DATABASE",
        _APP_ROOT.parent / "Database_V2.0",
    ]
    for c in candidates:
        if c.exists():
            try:
                next(c.iterdir(), None)
                return c
            except Exception:
                continue
    return _APP_ROOT / "Database_V2.0"



class DocumentDiscoveryService:
    """
    Authoritative Dynamic Discovery Engine for Physical Legal Documents.
    Scans the actual filesystem repository at runtime, normalizes categories,
    computes live counts and sizes, and correlates indexing status.
    """

    CANONICAL_SYNONYMS = {
        "circulars":     ["circular", "circulars", "cbic_circular"],
        "notifications": ["notification", "notifications", "rate_notification", "rate_notifications"],
        "rules":         ["rule", "rules", "cgst_rule", "cgst_rules", "cgst_rules_10_08_2026", "igst_rules"],
        "acts":          ["act", "acts", "cgst_act", "cgst_acts", "statute"],
        "igst":          ["igst_act", "igst_acts", "igst"],
        "highcourt":     ["high_court", "highcourt", "high_court_case_laws", "hc_judgments"],
        "supremecourt":  ["supreme_court", "supremecourt", "supreme_court_case_laws", "sc_judgments"],
        "aars":          ["aar", "aars", "advance_ruling", "advance_rulings"],
        "icai":          ["icai", "icai_guidance"],
        "forms":         ["form", "forms"],
        "faqs":          ["faq", "faqs"],
        "brochures":     ["brochure", "brochures"],
        "flyers":        ["flyer", "flyers", "other_app_result"],
        "reports":       ["report", "reports", "generated_reports"],
    }

    CANONICAL_LABELS = {
        "circulars":     "Circulars",
        "notifications": "Notifications",
        "rules":         "CGST & IGST Rules",
        "acts":          "CGST Acts",
        "cgst":          "CGST Acts",
        "igst":          "IGST Acts",
        "highcourt":     "High Court Case Laws",
        "supremecourt":  "Supreme Court Case Laws",
        "aars":          "Advance Rulings (AAR)",
        "icai":          "ICAI Guidance",
        "forms":         "Forms",
        "faqs":          "FAQs",
        "brochures":     "Brochures",
        "flyers":        "Flyers & Summary Results",
        "reports":       "Generated Reports",
    }

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt"}

    _indexed_rel_paths: Optional[Set[str]] = None
    _indexed_filenames: Optional[Set[str]] = None

    @classmethod
    def get_base_dir(cls) -> Path:
        return resolve_base_dir()

    @classmethod
    def _normalize_name_tokens(cls, name: str) -> str:
        """Convert a folder name to lowercase tokenized snake_case string."""
        s = name.lower()
        # Remove date patterns like 10-08-2026 or 2017-2025
        s = re.sub(r"\b\d{1,4}[-_]\d{1,2}[-_]\d{2,4}\b", "", s)
        s = re.sub(r"\b\d{4}[-_]\d{4}\b", "", s)
        # Remove versioning like 2.0
        s = re.sub(r"\bv?\d+\.\d+\b", "", s)
        # Replace non-alphanumerics with underscore
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    @classmethod
    def normalize_category(cls, folder_name: str) -> Tuple[str, str, bool]:
        """
        Derives canonical category ID and human label from physical folder name.
        Returns (category_id, display_label, is_dynamic).
        """
        tokenized = cls._normalize_name_tokens(folder_name)

        # 1. Match against known canonical synonyms
        for canonical_id, synonyms in cls.CANONICAL_SYNONYMS.items():
            for syn in synonyms:
                if syn == tokenized or syn in tokenized.split("_") or f"_{syn}_" in f"_{tokenized}_":
                    label = cls.CANONICAL_LABELS.get(canonical_id, canonical_id.replace("_", " ").title())
                    return canonical_id, label, False

        # 2. Dynamic auto-discovery category
        clean_slug = re.sub(r"[^a-z0-9]+", "_", folder_name.lower()).strip("_")
        clean_label = folder_name.replace("_", " ").replace("-", " ").title()
        return clean_slug, clean_label, True

    @classmethod
    def _load_chunk_provenance(cls) -> None:
        """Loads provenance filenames/paths from chunks.jsonl into memory cache if available."""
        if cls._indexed_rel_paths is not None:
            return

        cls._indexed_rel_paths = set()
        cls._indexed_filenames = set()

        from app.config import CHUNKS_PATH
        chunks_file = Path(CHUNKS_PATH)
        if not chunks_file.exists():
            return

        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                # Check if it's a Git LFS pointer
                first_line = f.readline()
                if "git-lfs" in first_line:
                    # In local dev with LFS pointers, fallback to assuming corpus PDFs are indexed
                    return

                f.seek(0)
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        rel_path = data.get("rel_path") or data.get("metadata", {}).get("rel_path", "")
                        source = data.get("source") or data.get("metadata", {}).get("source", "")
                        if rel_path:
                            norm_rel = str(rel_path).replace("\\", "/").lower()
                            cls._indexed_rel_paths.add(norm_rel)
                            cls._indexed_filenames.add(Path(norm_rel).name)
                        if source:
                            cls._indexed_filenames.add(Path(source).name.lower())
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Could not scan chunk provenance: {e}")

    @classmethod
    def extract_year(cls, file_path: Path) -> Optional[str]:
        """Extracts publication or effective year from folder hierarchy or filename pattern."""
        for part in reversed(file_path.parent.parts):
            if part.isdigit() and len(part) == 4 and part.startswith("20"):
                return part
        m = re.search(r"\b(20[12]\d)\b", file_path.name)
        if m:
            return m.group(1)
        return None

    @classmethod
    def discover_categories(cls) -> Dict[str, Dict[str, Any]]:
        """
        Scans all physical folders under BASE_DIR dynamically.
        Returns a dictionary of category metadata keyed by canonical or dynamic category ID.
        """
        base_dir = cls.get_base_dir()
        result: Dict[str, Dict[str, Any]] = {}

        # Pre-seed canonical categories
        for cat_id, label in cls.CANONICAL_LABELS.items():
            result[cat_id] = {
                "id": cat_id,
                "label": label,
                "folder": None,
                "folders": [],
                "files": 0,
                "size_bytes": 0,
                "size_mb": 0.0,
                "is_dynamic": False,
                "exists": False,
            }

        if not base_dir.exists():
            return result

        # Scan actual top-level folders
        for item in sorted(base_dir.iterdir()):
            if not item.is_dir():
                continue

            folder_name = item.name
            cat_id, label, is_dyn = cls.normalize_category(folder_name)

            # Count files & bytes
            all_files = [
                f for f in item.rglob("*")
                if f.is_file() and f.suffix.lower() in cls.SUPPORTED_EXTENSIONS
            ]
            total_size = sum(f.stat().st_size for f in all_files)

            if cat_id not in result:
                result[cat_id] = {
                    "id": cat_id,
                    "label": label,
                    "folder": folder_name,
                    "folders": [folder_name],
                    "files": len(all_files),
                    "size_bytes": total_size,
                    "size_mb": round(total_size / (1024 * 1024), 2),
                    "is_dynamic": is_dyn,
                    "exists": True,
                }
            else:
                entry = result[cat_id]
                entry["exists"] = True
                if entry["folder"] is None:
                    entry["folder"] = folder_name
                entry["folders"].append(folder_name)
                entry["files"] += len(all_files)
                entry["size_bytes"] += total_size
                entry["size_mb"] = round(entry["size_bytes"] / (1024 * 1024), 2)

        return result

    @classmethod
    def get_category_folders(cls, category_id: str) -> List[Path]:
        """Returns list of matching Path directories on disk for a category ID."""
        base_dir = cls.get_base_dir()
        if not base_dir.exists():
            return []

        categories = cls.discover_categories()
        cat_info = categories.get(category_id.lower())
        if not cat_info or not cat_info.get("folders"):
            # Fallback search if exact folder exists
            direct = base_dir / category_id
            return [direct] if direct.exists() else []

        return [base_dir / f_name for f_name in cat_info["folders"] if (base_dir / f_name).exists()]

    @classmethod
    def discover_documents(
        cls,
        category: str = "all",
        year: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 300,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lists actual physical documents with live metadata, extracted year, size,
        and correlated indexing status.
        """
        cls._load_chunk_provenance()
        base_dir = cls.get_base_dir()
        if not base_dir.exists():
            return []

        if category.lower() == "all":
            all_docs = []
            for cat_id in cls.discover_categories():
                all_docs.extend(cls.discover_documents(category=cat_id, limit=50))
            return all_docs[skip : skip + limit]

        folders = cls.get_category_folders(category)
        if not folders:
            return []

        docs = []
        for folder_path in folders:
            try:
                files = sorted(
                    [f for f in folder_path.rglob("*") if f.is_file() and f.suffix.lower() in cls.SUPPORTED_EXTENSIONS],
                    key=lambda f: f.name.lower(),
                )
                for idx, file_path in enumerate(files):
                    rel = str(file_path.relative_to(base_dir)).replace("\\", "/")
                    file_year = cls.extract_year(file_path)

                    if year and file_year != year and year.lower() != "all":
                        continue

                    if search:
                        s_lower = search.lower()
                        if s_lower not in file_path.name.lower() and s_lower not in rel.lower():
                            continue

                    size_bytes = file_path.stat().st_size
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    ext = file_path.suffix.upper().replace(".", "")

                    # Check indexing status against chunks.jsonl / fallback
                    is_indexed = True
                    norm_rel = rel.lower()
                    if cls._indexed_rel_paths:
                        is_indexed = norm_rel in cls._indexed_rel_paths or file_path.name.lower() in cls._indexed_filenames

                    docs.append({
                        "id": f"{category}_{idx}",
                        "title": file_path.stem.replace("_", " ").replace("-", " "),
                        "filename": file_path.name,
                        "size": f"{round(size_bytes / 1024, 1)} KB",
                        "size_bytes": size_bytes,
                        "modified_at": mtime,
                        "path": rel,
                        "category": category,
                        "year": file_year,
                        "file_type": ext,
                        "indexed": is_indexed,
                        "status": "Completed" if is_indexed else "Discovered",
                    })
            except Exception as e:
                logger.error(f"Error scanning folder {folder_path}: {e}")

        return docs[skip : skip + limit]

    @classmethod
    def get_year_breakdown(cls, category: str) -> Dict[str, List[Dict[str, Any]]]:
        """Groups category documents into descending year buckets."""
        all_docs = cls.discover_documents(category=category, limit=1000)
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for doc in all_docs:
            y = doc.get("year") or "other"
            grouped.setdefault(y, []).append(doc)

        sorted_grouped = {}
        for y in sorted((k for k in grouped if k != "other"), reverse=True):
            sorted_grouped[y] = grouped[y]
        if "other" in grouped:
            sorted_grouped["other"] = grouped["other"]
        return sorted_grouped

    @classmethod
    def get_document_file(cls, category: str, filename: str) -> Optional[Path]:
        """Finds the actual Path on disk for serving/downloading."""
        base_dir = cls.get_base_dir()
        if not base_dir.exists():
            return None

        safe_filename = os.path.basename(filename)
        folders = cls.get_category_folders(category)

        # 1. Search in category folders first
        for folder in folders:
            direct = folder / safe_filename
            if direct.exists() and direct.is_file():
                return direct
            for found in folder.rglob(safe_filename):
                if found.is_file():
                    return found

        # 2. Global search under base_dir
        for found in base_dir.rglob(safe_filename):
            if found.is_file():
                return found

        return None
