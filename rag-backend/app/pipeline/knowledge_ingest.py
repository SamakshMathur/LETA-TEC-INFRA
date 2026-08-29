import json
import logging
import hashlib
import os
from pathlib import Path
from datetime import datetime
from app.utils.time import utc_now
from typing import List, Dict

import faiss
import pandas as pd
from app.config import DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH
from app.database import get_db
from app.ingestion.legal_parser import LegalParser
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.docx_reader import extract_text_from_docx, extract_text_from_doc
from app.ingestion.excel_reader import extract_text_from_excel
from app.pipeline.incremental_ingest import _chunk_pages, _embed_and_append, _append_to_chunks_file

logger = logging.getLogger(__name__)

def calculate_sha256(file_path: Path) -> str:
    """Calculates the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def _extract_text(file_path: Path, rel_path: str) -> List[Dict]:
    """Extracts text blocks and pages from different file types."""
    ext = file_path.suffix.lower()
    cls_info = LegalParser.classify_folder(rel_path)

    try:
        pages = []
        if ext == ".pdf":
            pages = extract_text_from_pdf(str(file_path))
            if not pages or sum(len(p.get("text", "")) for p in pages) < 100:
                from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
                pages = extract_text_from_scanned_pdf(str(file_path))
        elif ext == ".docx":
            pages = extract_text_from_docx(file_path)
        elif ext == ".doc":
            pages = extract_text_from_doc(file_path)
        elif ext in (".xlsx", ".xls"):
            pages = extract_text_from_excel(file_path)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                valid_pairs = [f"{col}: {row[col]}" for col in df.columns 
                              if pd.notna(row[col]) and "Unnamed" not in str(col)]
                sentence = ". ".join(valid_pairs)
                if sentence.strip():
                    pages.append({
                        "text": sentence,
                        "metadata": {
                            "source": str(file_path),
                            "type": "csv_data"
                        }
                    })
        elif ext in (".txt", ".md"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            if text.strip():
                pages.append({
                    "text": text,
                    "metadata": {
                        "source": str(file_path),
                        "type": "text"
                    }
                })
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []

        for p in pages:
            p["metadata"] = p.get("metadata", {})
            p["metadata"].update(cls_info)
            p["metadata"]["rel_path"] = rel_path
            p["metadata"]["source"]   = str(file_path)

        return pages

    except Exception as e:
        logger.error(f"Extraction failed for {file_path}: {e}")
        return []

def update_status(doc_id: str, status: str, chunk_count: int = 0, error_message: str = None):
    """Updates the status of a document in MongoDB."""
    try:
        db = get_db()
        if db is not None:
            update_data = {
                "status": status,
                "last_modified": utc_now()
            }
            if chunk_count > 0:
                update_data["chunk_count"] = chunk_count
            if error_message:
                update_data["error_message"] = error_message
                
            db["knowledge_base"].update_one(
                {"document_id": doc_id},
                {"$set": update_data}
            )
            
            # Log status updates in audit logs
            db["knowledge_audit_logs"].insert_one({
                "timestamp": utc_now(),
                "user_id": "system",
                "action": "status_update",
                "document_id": doc_id,
                "details": f"Ingestion status updated to {status}" + (f": {error_message}" if error_message else "")
            })
    except Exception as e:
        logger.error(f"Failed to update document status: {e}")

async def process_document_task(doc_id: str, file_path: str, rel_path: str):
    """Asynchronous pipeline execution task."""
    path = Path(file_path)
    
    update_status(doc_id, "Extracting")
    pages = _extract_text(path, rel_path)
    if not pages:
        update_status(doc_id, "Failed", error_message="No text extracted from file")
        return

    update_status(doc_id, "Cleaning")
    # Text is cleaned during classification and loading in structured splitter

    update_status(doc_id, "Chunking")
    chunks = _chunk_pages(pages)
    if not chunks:
        update_status(doc_id, "Failed", error_message="No semantic chunks generated")
        return

    update_status(doc_id, "Embedding")
    update_status(doc_id, "Indexing")
    try:
        _append_to_chunks_file(chunks)
        _embed_and_append(chunks)
    except Exception as e:
        update_status(doc_id, "Failed", error_message=f"Indexing failed: {str(e)}")
        return

    update_status(doc_id, "Refreshing Retriever")
    try:
        from app.dependencies import reload_retriever
        reload_retriever()
        update_status(doc_id, "Completed", chunk_count=len(chunks))
    except Exception as e:
        update_status(doc_id, "Failed", error_message=f"Retriever reload failed: {str(e)}")
