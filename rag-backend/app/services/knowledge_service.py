import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from app.utils.time import utc_now
from typing import List, Dict, Optional, Tuple

from app.database import get_db
from app.config import DATA_DIR
from app.pipeline.knowledge_ingest import calculate_sha256, process_document_task

logger = logging.getLogger(__name__)

class KnowledgeService:
    @staticmethod
    def get_upload_dir() -> Path:
        upload_dir = Path(DATA_DIR) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    @staticmethod
    def check_duplicate(file_hash: str) -> Optional[Dict]:
        """Checks if a document with the same hash exists and is active."""
        db = get_db()
        if db is not None:
            return db["knowledge_base"].find_one({"sha256": file_hash, "is_active": True})
        return None

    @classmethod
    def upload_document(
        cls,
        file_content: bytes,
        filename: str,
        category: str,
        uploader: str,
        tags: List[str] = None,
        effective_date: str = None,
        force: bool = False,
        background_tasks = None
    ) -> Tuple[Dict, Optional[Dict]]:
        """Orchestrates document upload, metadata persistence, duplicate check, and asynchronous processing."""
        upload_dir = cls.get_upload_dir()
        temp_path = upload_dir / f"{uuid.uuid4()}_{filename}"
        
        with open(temp_path, "wb") as f:
            f.write(file_content)

        file_hash = calculate_sha256(temp_path)
        
        if not force:
            duplicate = cls.check_duplicate(file_hash)
            if duplicate:
                os.remove(temp_path)
                return {"status": "duplicate", "message": "A duplicate document already exists"}, duplicate

        document_id = str(uuid.uuid4())
        ext = Path(filename).suffix.replace(".", "").upper()

        metadata = {
            "document_id": document_id,
            "title": filename,
            "filename": filename,
            "category": category,
            "document_type": ext,
            "tags": tags or [],
            "uploader": uploader,
            "uploaded_at": utc_now(),
            "effective_date": effective_date or utc_now().strftime("%Y-%m-%d"),
            "version": 1,
            "status": "Queued",
            "chunk_count": 0,
            "is_active": True,
            "sha256": file_hash,
            "rel_path": filename,
            "file_path": str(temp_path)
        }

        db = get_db()
        if db is not None:
            db["knowledge_base"].insert_one(metadata)
            db["knowledge_audit_logs"].insert_one({
                "timestamp": utc_now(),
                "user_id": uploader,
                "action": "Upload",
                "document_id": document_id,
                "details": f"Uploaded document {filename}"
            })

        if background_tasks:
            background_tasks.add_task(process_document_task, document_id, str(temp_path), filename)
        else:
            import asyncio
            asyncio.create_task(process_document_task(document_id, str(temp_path), filename))

        # Clean ObjectId from return dict
        metadata.pop("_id", None)
        return {"status": "success", "document_id": document_id, "metadata": metadata}, None

    @classmethod
    def replace_document(
        cls,
        doc_id: str,
        file_content: bytes,
        filename: str,
        uploader: str,
        background_tasks = None
    ) -> Dict:
        """Uploads a new version of a document, archiving the older version."""
        db = get_db()
        if db is None:
            return {"status": "error", "message": "Database connection failed"}

        old_doc = db["knowledge_base"].find_one({"document_id": doc_id})
        if not old_doc:
            return {"status": "error", "message": "Document not found"}

        # Archive old version
        db["knowledge_base"].update_one(
            {"document_id": doc_id},
            {"$set": {"is_active": False, "status": "Archived"}}
        )

        db["knowledge_audit_logs"].insert_one({
            "timestamp": utc_now(),
            "user_id": uploader,
            "action": "Archive",
            "document_id": doc_id,
            "details": f"Archived previous version {old_doc['version']} of {filename}"
        })

        # Process new version
        res, _ = cls.upload_document(
            file_content=file_content,
            filename=filename,
            category=old_doc["category"],
            uploader=uploader,
            tags=old_doc.get("tags", []),
            effective_date=old_doc.get("effective_date"),
            force=True,
            background_tasks=background_tasks
        )

        if res["status"] == "success":
            new_doc_id = res["document_id"]
            db["knowledge_base"].update_one(
                {"document_id": new_doc_id},
                {"$set": {"version": old_doc["version"] + 1}}
            )
            db["knowledge_audit_logs"].insert_one({
                "timestamp": utc_now(),
                "user_id": uploader,
                "action": "Replace",
                "document_id": new_doc_id,
                "details": f"Replaced document {doc_id} with new version {old_doc['version'] + 1}"
            })

        return res

    @staticmethod
    def archive_document(doc_id: str, user_id: str) -> Dict:
        """Soft deletes or archives a document."""
        db = get_db()
        if db is not None:
            doc = db["knowledge_base"].find_one({"document_id": doc_id})
            if not doc:
                return {"status": "error", "message": "Document not found"}

            db["knowledge_base"].update_one(
                {"document_id": doc_id},
                {"$set": {"is_active": False, "status": "Archived"}}
            )
            db["knowledge_audit_logs"].insert_one({
                "timestamp": utc_now(),
                "user_id": user_id,
                "action": "Archive",
                "document_id": doc_id,
                "details": f"Archived document {doc['filename']}"
            })

            # Refresh retriever to dynamically ignore archived chunks
            KnowledgeService.refresh_retriever()
            return {"status": "success", "message": "Document archived successfully"}
        return {"status": "error", "message": "Database connection failed"}

    @staticmethod
    def reindex_document(doc_id: str, user_id: str, background_tasks = None) -> Dict:
        """Triggers re-indexing of an existing document."""
        db = get_db()
        if db is not None:
            doc = db["knowledge_base"].find_one({"document_id": doc_id})
            if not doc:
                return {"status": "error", "message": "Document not found"}

            db["knowledge_audit_logs"].insert_one({
                "timestamp": utc_now(),
                "user_id": user_id,
                "action": "Re-index",
                "document_id": doc_id,
                "details": f"Re-indexed document {doc['filename']}"
            })

            if background_tasks:
                background_tasks.add_task(process_document_task, doc_id, doc["file_path"], doc["filename"])
            else:
                import asyncio
                asyncio.create_task(process_document_task(doc_id, doc["file_path"], doc["filename"]))
            return {"status": "success", "message": "Re-indexing task queued"}
        return {"status": "error", "message": "Database connection failed"}

    @staticmethod
    def list_documents(
        category: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict]:
        """Lists documents by merging MongoDB upload records and physical repository documents."""
        from app.services.document_discovery import DocumentDiscoveryService

        db = get_db()
        mongo_docs = []
        known_filenames = set()

        if db is not None:
            query = {}
            if category and category.lower() != "all":
                query["category"] = category.lower()
            if status and status.lower() != "all":
                query["status"] = status
            if search:
                query["filename"] = {"$regex": search, "$options": "i"}

            raw_mongo = list(db["knowledge_base"].find(query).sort("uploaded_at", -1))
            for doc in raw_mongo:
                doc.pop("_id", None)
                if isinstance(doc.get("uploaded_at"), datetime):
                    doc["uploaded_at"] = doc["uploaded_at"].isoformat()
                mongo_docs.append(doc)
                if doc.get("filename"):
                    known_filenames.add(doc["filename"].lower())

        # Physical documents from repository
        phys_docs = DocumentDiscoveryService.discover_documents(
            category=category or "all",
            search=search,
            limit=limit * 2
        )

        merged: List[Dict] = list(mongo_docs)
        for p in phys_docs:
            if p["filename"].lower() in known_filenames:
                continue

            if status and status.lower() not in ("all", "completed", "indexed", "discovered"):
                continue

            merged.append({
                "document_id": p["id"],
                "title": p["title"],
                "filename": p["filename"],
                "category": p["category"],
                "document_type": p["file_type"],
                "tags": [p["category"], p["file_type"]],
                "uploader": "System Corpus",
                "uploaded_at": p["modified_at"],
                "effective_date": p["year"] or "2024",
                "version": 1,
                "status": "Completed" if p.get("indexed") else "Discovered",
                "chunk_count": p.get("chunk_count", 0),
                "is_active": True,
                "rel_path": p["path"],
                "file_path": p["path"],
                "size": p["size"],
                "year": p["year"]
            })

        return merged[skip : skip + limit]


    @staticmethod
    def refresh_retriever():
        """Refreshes the live retriever instance."""
        try:
            from app.dependencies import reload_retriever
            reload_retriever()
            logger.info("Retriever hot-reloaded successfully")
        except Exception as e:
            logger.error(f"Retriever reload failed: {e}")
