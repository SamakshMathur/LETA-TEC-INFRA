import json
import logging
import os
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import faiss
except ImportError:
    faiss = None  # type: ignore  # CI env; only fails if index load/write is attempted
import numpy as np

from app.config import DATA_DIR, CHUNKS_PATH, VECTOR_DB_PATH
from app.database import get_db
from app.ingestion.legal_parser import LegalParser
from app.ingestion.pdf_text import extract_text_from_pdf
from app.ingestion.docx_reader import extract_text_from_docx
from app.ingestion.excel_reader import extract_text_from_excel
from app.ingestion.clean_text import clean_text

_S3_BUCKET = os.getenv("S3_DATA_BUCKET", "")
_S3_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

# Set ENABLE_CONTEXTUAL_ENRICHMENT=true in ECS task definition to enable
# per-chunk Haiku context enrichment on admin-upload ingestion.
# Off by default — each chunk costs one Haiku API call (~$0.0003) and adds
# ~2-5s per chunk; appropriate for nightly batch jobs, not real-time uploads.
_ENRICHMENT_ENABLED = os.getenv("ENABLE_CONTEXTUAL_ENRICHMENT", "false").lower() == "true"

logger = logging.getLogger(__name__)

CHUNKS_FILE = Path(CHUNKS_PATH)
INDEX_FILE  = Path(VECTOR_DB_PATH)
META_FILE   = INDEX_FILE.with_suffix(".meta.json")
DATA_ROOT   = Path(DATA_DIR)


def calculate_sha256(file_path: Path) -> str:
    """Calculates the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def _find_coordinates(file_path: str, page_num: int, text: str) -> Dict[str, float]:
    """Retrieves PDF bounding box coordinates for a text snippet on a page."""
    try:
        import fitz
        doc = fitz.open(file_path)
        if 0 <= page_num - 1 < len(doc):
            page = doc[page_num - 1]
            search_str = text.strip()[:80]
            if search_str:
                rects = page.search_for(search_str)
                if rects:
                    r = rects[0]
                    return {"x0": float(r.x0), "y0": float(r.y0), "x1": float(r.x1), "y1": float(r.y1)}
    except Exception as e:
        logger.debug(f"Failed to find coordinates: {e}")
    return {"x0": 0.0, "y0": 0.0, "x1": 0.0, "y1": 0.0}


# ── Step 1: Extract text from a single file ───────────────────────────────────

def _extract_pages(file_path: Path, rel_path: str) -> List[Dict]:
    ext = file_path.suffix.lower()

    try:
        pages = []
        if ext == ".pdf":
            pages = extract_text_from_pdf(str(file_path))
            if not pages or sum(len(p.get("text", "")) for p in pages) < 100:
                from app.ingestion.pdf_scanned import extract_text_from_scanned_pdf
                pages = extract_text_from_scanned_pdf(str(file_path))
        elif ext == ".docx":
            pages = extract_text_from_docx(file_path)
        elif ext in (".xlsx", ".xls"):
            pages = extract_text_from_excel(file_path)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []

        if not pages:
            return []

        # Content-based canonical metadata extraction
        full_text = "\n".join(p.get("text", "") for p in pages)
        first_page = pages[0].get("text", "") if pages else ""
        doc_meta = LegalParser.extract_document_metadata(full_text, first_page, file_path.name)

        file_hash = calculate_sha256(file_path)

        is_active, status = LegalParser.determine_quarantine(doc_meta)
        if not is_active:
            if status == "NEEDS_REVIEW" and doc_meta["document_type"] in ["CIRCULAR", "NOTIFICATION"] and (doc_meta["date_precision"] == "UNKNOWN" or doc_meta["date_year"] is None):
                logger.warning(f"Document {file_path.name} is missing a reliable date/year. Quarantined!")
            else:
                logger.warning(f"Document {file_path.name} failed metadata confidence check ({doc_meta['confidence']:.2f}). Quarantined!")

        # Update or insert into MongoDB knowledge_base
        try:
            db = get_db()
            if db is not None:
                db["knowledge_base"].update_one(
                    {"sha256": file_hash},
                    {"$set": {
                        "is_active": is_active,
                        "status": status,
                        "canonical_document_type": doc_meta["document_type"],
                        "issuing_authority": doc_meta["authority"],
                        "jurisdiction": doc_meta["jurisdiction"],
                        "date_issued": doc_meta["date_issued"],
                        "date_year": doc_meta["date_year"],
                        "date_precision": doc_meta["date_precision"],
                        "confidence": doc_meta["confidence"],
                        "document_type": doc_meta["document_type"]  # keep standard field aligned
                    }},
                    upsert=True
                )
        except Exception as e:
            logger.warning(f"Failed to update MongoDB for metadata: {e}")

        # If quarantined, we do not index it
        if not is_active:
            logger.warning(f"Quarantined document {file_path.name} from vector index.")

        clean_pages = []
        for p in pages:
            raw_text = p.get("text", "")
            if not raw_text or raw_text.strip() == "[OCR_EMPTY_PAGE]":
                continue
            p["text"] = clean_text(raw_text)
            p["metadata"] = p.get("metadata", {})
            p["metadata"].update({
                "document_type": doc_meta["document_type"],
                "authority": doc_meta["authority"],
                "jurisdiction": doc_meta["jurisdiction"],
                "date_issued": doc_meta["date_issued"],
                "date_year": doc_meta["date_year"],
                "date_precision": doc_meta["date_precision"],
                "confidence": doc_meta["confidence"],
                "is_active": is_active,
                "status": status,
                "sha256": file_hash,
                "rel_path": rel_path,
                "source": str(file_path)
            })
            clean_pages.append(p)

        return clean_pages

    except Exception as e:
        logger.error(f"Extraction failed for {file_path}: {e}")
        return []


# ── Step 2: Chunk the extracted pages ─────────────────────────────────────────

def _chunk_pages(pages: List[Dict]) -> List[Dict]:
    if not pages:
        return []

    first_meta = pages[0]["metadata"]
    # Check if document is quarantined
    if not first_meta.get("is_active", True):
        logger.warning("Document is quarantined (NEEDS_REVIEW). Skipping chunk generation.")
        return []

    full_text   = "\n".join(p["text"] for p in pages)
    doc_type    = first_meta.get("document_type", "Other")
    chunks_data = LegalParser.structural_split(full_text, doc_type)

    chunks = []
    for idx, chunk_obj in enumerate(chunks_data):
        text      = chunk_obj["text"].strip()
        structure = chunk_obj["structure"]
        if not text:
            continue

        raw_citations        = LegalParser.extract_citations(text, normalize=False)
        normalized_citations = LegalParser.extract_citations(text, normalize=True)
        topic                = LegalParser.classify_topic(text)
        primary_provisions   = [c for c in normalized_citations if "SEC" in c or "RUL" in c]

        import re
        raw_section_nums = [
            re.search(r'\d+', c).group()
            for c in normalized_citations
            if "SEC" in c and re.search(r'\d+', c)
        ]
        law_type = "general"
        if any(s in LegalParser.SUBSTANTIVE_SECTIONS for s in raw_section_nums):
            law_type = "substantive"
        elif any(s in LegalParser.PROCEDURAL_SECTIONS for s in raw_section_nums):
            law_type = "procedural"

        # Calculate exact text and source hashes
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        source_hash = first_meta.get("sha256", "")

        # Try to resolve page coordinates
        page_num = pages[0]["metadata"].get("page", 1)  # fallback
        # Find which page contains this chunk text
        for p in pages:
            if text[:100] in p["text"]:
                page_num = p["metadata"].get("page", page_num)
                break

        coords = _find_coordinates(first_meta.get("source", ""), page_num, text)

        full_meta = {
            **first_meta,
            "topic":       topic,
            "law_type":    law_type,
            "citations":   normalized_citations,
            "raw_citations": raw_citations,
            "provisions":  primary_provisions,
            "section_type": structure,
            "page":        page_num,
            "citation_coordinates": coords,
            "source_hash": source_hash,
            "text_hash":   text_hash,
            "extraction_method": "PDF_TEXT" if first_meta.get("source", "").lower().endswith(".pdf") else "DOCX",
            "extraction_confidence": 1.0
        }

        # Generate canonical 4-tier IDs:
        # doc_id: doc_<hash>
        # ver_id: ver_<hash>
        # prov_id: prov_<doc_type_short>_<section/rule_num>
        doc_id = f"doc_{source_hash[:16]}"
        ver_id = f"ver_{source_hash[:16]}"

        # Provision ID based on primary provision
        prov_num = "general"
        if primary_provisions:
            prov_num = primary_provisions[0].lower().replace("cgst_", "")
        prov_id = f"prov_{doc_id}_{prov_num}"

        # Chunk ID
        chunk_id = LegalParser.generate_chunk_id(full_meta, structure, text, idx)

        # Inject 4-tier IDs into metadata
        full_meta.update({
            "document_id": doc_id,
            "version_id": ver_id,
            "provision_id": prov_id,
            "chunk_id": chunk_id
        })

        chunks.append({
            "chunk_id": chunk_id,
            "text":     text,
            "metadata": full_meta,
            "source":   first_meta.get("source", ""),
            "rel_path": first_meta.get("rel_path", ""),
            "document_id": doc_id,
            "version_id": ver_id,
            "provision_id": prov_id
        })

    return chunks



# ── Step 3: Embed + append to FAISS ───────────────────────────────────────────

def _embed_and_append(chunks: List[Dict]) -> int:
    if not chunks:
        return 0

    from app.embeddings.embedder import embed_texts

    # Use context-enriched text when available (set by enrich_document_chunks).
    # Falls back to raw chunk text when enrichment was skipped or failed.
    texts      = [c.get("text_with_context") or c["text"] for c in chunks]
    embeddings = embed_texts(texts).astype("float32")

    # Load existing index (or create fresh if missing)
    if INDEX_FILE.exists():
        index = faiss.read_index(str(INDEX_FILE))
    else:
        from app.config import VECTOR_DIM
        index = faiss.IndexFlatIP(VECTOR_DIM)  # must match retriever's inner-product search

    # Load existing metadata
    existing_meta: list = []
    if META_FILE.exists():
        with META_FILE.open(encoding="utf-8") as f:
            existing_meta = json.load(f)

    # Append
    index.add(embeddings)
    new_meta = [c.get("metadata", {}) | {"chunk_id": c["chunk_id"]} for c in chunks]
    existing_meta.extend(new_meta)

    # Save
    faiss.write_index(index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(existing_meta, f, ensure_ascii=False)

    logger.info(f"FAISS index updated: +{len(chunks)} vectors → total {index.ntotal}")
    return len(chunks)


def _is_positive_conflict(text: str) -> bool:
    text_lower = text.lower()
    conflict_words = ["conflict", "contrary", "override", "overrule", "differ"]
    for word in conflict_words:
        idx = text_lower.find(word)
        if idx != -1:
            pre_text = text_lower[max(0, idx-40):idx]
            negations = ["no ", "not ", "without ", "never ", "none ", "does not"]
            if not any(n in pre_text for n in negations):
                return True
    return False

def _resolve_target_provision(db, target_prov_ref: str, current_metadata: Dict) -> str:
    """
    Dynamically resolves referenced provisions against the actual target document/provision identity.
    If multiple candidates exist or none can be determined, returns "UNRESOLVED".
    """
    ref_lower = target_prov_ref.lower().strip()
    num_match = re.search(r'\b\d+[A-Z]*\b', ref_lower)
    if not num_match:
        return "UNRESOLVED"
    base_num = num_match.group()

    if any(k in ref_lower for k in ["notification", "notfn", "notif"]):
        doc_type = "NOTIFICATION"
    elif "circular" in ref_lower or "cir" in ref_lower:
        doc_type = "CIRCULAR"
    elif "rule" in ref_lower or "rul" in ref_lower:
        doc_type = "RULES"
    else:
        doc_type = "PRIMARY_LAW"
    jurisdiction = current_metadata.get("jurisdiction", "Central")

    candidates = list(db["knowledge_base"].find({
        "canonical_document_type": doc_type,
        "jurisdiction": jurisdiction,
        "is_active": True
    }))

    if not candidates:
        candidates = list(db["knowledge_base"].find({
            "canonical_document_type": doc_type,
            "is_active": True
        }))

    if len(candidates) == 1:
        doc = candidates[0]
        doc_id = doc.get("document_id")
        target_id = f"prov_{doc_id}_{base_num}"
        return target_id
    elif len(candidates) > 1:
        text_context = (current_metadata.get("title", "") + " " + current_metadata.get("source", "")).lower()
        matched_doc = None
        for cand in candidates:
            cand_title = cand.get("title", "").lower()
            if "igst" in text_context and "igst" in cand_title:
                matched_doc = cand
                break
            elif "cgst" in text_context and "cgst" in cand_title:
                matched_doc = cand
                break
        if matched_doc:
            doc_id = matched_doc.get("document_id")
            return f"prov_{doc_id}_{base_num}"

    return "UNRESOLVED"

def _update_relational_database(chunks: List[Dict]):
    """
    Populates MongoDB 'provisions' and 'relationships' collections from ingested chunk metadata.
    Enforces graph write atomicity, idempotency, and negation-gated conflicts.
    """
    db = get_db()
    if db is None:
        return

    provisions_batch = {}
    relationships_batch = []

    unique_doc_ids = set()
    unique_prov_ids = set()

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        doc_id = meta.get("document_id")
        ver_id = meta.get("version_id")
        prov_id = meta.get("provision_id")

        if doc_id:
            unique_doc_ids.add(doc_id)
        if prov_id:
            unique_prov_ids.add(prov_id)

        # 1. Track provisions for update
        if prov_id and not prov_id.endswith("_general"):
            primary_prov = meta.get("provisions", [])
            prov_name = primary_prov[0] if primary_prov else "Unknown Provision"

            provisions_batch[prov_id] = {
                "provision_id": prov_id,
                "document_id": doc_id,
                "version_id": ver_id,
                "type": "RULE" if "RUL" in prov_id else "SECTION",
                "name": prov_name,
                "text": chunk.get("text", ""),
                "hierarchy_path": [prov_name]
            }

        # 2. Extract relationships based on citations and references
        citations = meta.get("citations", [])
        for cit in citations:
            target_prov_id = _resolve_target_provision(db, cit, meta)

            if target_prov_id == "UNRESOLVED":
                db["unresolved_references"].update_one(
                    {"source_id": prov_id or doc_id, "reference_text": cit},
                    {"$set": {"source_id": prov_id or doc_id, "reference_text": cit, "type": "CITATION"}},
                    upsert=True
                )
            elif prov_id and target_prov_id != prov_id:
                relationships_batch.append({
                    "edge_id": f"edge_{prov_id}_{target_prov_id}_ref",
                    "source_id": prov_id,
                    "target_id": target_prov_id,
                    "relationship_type": "REFERS_TO"
                })

        doc_type = meta.get("document_type")

        # Circulars CLARIFY primary provisions
        if doc_type == "CIRCULAR":
            for prov in meta.get("provisions", []):
                target_prov_id = _resolve_target_provision(db, prov, meta)

                if target_prov_id == "UNRESOLVED":
                    db["unresolved_references"].update_one(
                        {"source_id": doc_id, "reference_text": prov},
                        {"$set": {"source_id": doc_id, "reference_text": prov, "type": "CLARIFIES"}},
                        upsert=True
                    )
                else:
                    relationships_batch.append({
                        "edge_id": f"edge_{doc_id}_{target_prov_id}_clarify",
                        "source_id": doc_id,
                        "target_id": target_prov_id,
                        "relationship_type": "CLARIFIES"
                    })

        # Case law INTERPRETS primary provisions
        elif doc_type in ["CASE_LAW", "ADVANCE_RULING"]:
            for prov in meta.get("provisions", []):
                target_prov_id = _resolve_target_provision(db, prov, meta)

                if target_prov_id == "UNRESOLVED":
                    db["unresolved_references"].update_one(
                        {"source_id": doc_id, "reference_text": prov},
                        {"$set": {"source_id": doc_id, "reference_text": prov, "type": "INTERPRETS"}},
                        upsert=True
                    )
                else:
                    relationships_batch.append({
                        "edge_id": f"edge_{doc_id}_{target_prov_id}_interpret",
                        "source_id": doc_id,
                        "target_id": target_prov_id,
                        "relationship_type": "INTERPRETS"
                    })

        # Negation-gated conflict detection
        if _is_positive_conflict(chunk.get("text", "")):
            for cit in citations:
                target_prov_id = _resolve_target_provision(db, cit, meta)
                if target_prov_id != "UNRESOLVED" and prov_id and target_prov_id != prov_id:
                    relationships_batch.append({
                        "edge_id": f"edge_{prov_id}_{target_prov_id}_conflict",
                        "source_id": prov_id,
                        "target_id": target_prov_id,
                        "relationship_type": "CONFLICTS_WITH",
                        "evidence_chunk_id": chunk.get("chunk_id", ""),
                        "confidence": 0.90,
                        "extraction_method": "NLP_NEGATION_GATED"
                    })

    # Bulk write transaction execution (Idempotent clean + insert)
    try:
        # Idempotent cleanup to prevent duplicate/stale relationships
        for d_id in unique_doc_ids:
            db["provisions"].delete_many({"document_id": d_id})
            db["relationships"].delete_many({"$or": [{"source_id": d_id}, {"target_id": d_id}]})

        for p_id in unique_prov_ids:
            db["relationships"].delete_many({"$or": [{"source_id": p_id}, {"target_id": p_id}]})

        # Bulk write provisions
        if provisions_batch:
            from pymongo import ReplaceOne
            operations = [
                ReplaceOne({"provision_id": pid}, pdata, upsert=True)
                for pid, pdata in provisions_batch.items()
            ]
            db["provisions"].bulk_write(operations)
            logger.info(f"Relational DB: Idempotently upserted {len(operations)} provisions")

        # Bulk write relationships
        if relationships_batch:
            from pymongo import ReplaceOne
            operations = [
                ReplaceOne({"edge_id": r["edge_id"]}, r, upsert=True)
                for r in relationships_batch
            ]
            db["relationships"].bulk_write(operations)
            logger.info(f"Relational DB: Idempotently upserted {len(operations)} relationship edges")
    except Exception as e:
        logger.error(f"Failed to idempotently update provisions/relationships in DB: {e}")


# ── Step 4: Append to chunks.jsonl ────────────────────────────────────────────

def _append_to_chunks_file(chunks: List[Dict]):
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")


# ── S3 persistence ────────────────────────────────────────────────────────────

def _persist_to_s3():
    """Upload the updated FAISS index and chunks.jsonl back to S3 so the next
    ECS task restart picks them up instead of re-downloading the stale versions."""
    if not _S3_BUCKET:
        return
    try:
        import boto3
        s3 = boto3.client("s3", region_name=_S3_REGION)
        for local, key in [
            (INDEX_FILE,  "vectordb/index.faiss"),
            (META_FILE,   "vectordb/index.meta.json"),
            (CHUNKS_FILE, "data/chunks/chunks.jsonl"),
        ]:
            if local.exists():
                s3.upload_file(str(local), _S3_BUCKET, key)
                logger.info(f"Persisted {local.name} → s3://{_S3_BUCKET}/{key}")
    except Exception as e:
        logger.warning(f"S3 persistence failed (index still updated in-memory): {e}")


# ── Public entry point ────────────────────────────────────────────────────────

def ingest_file(file_path: Path, rel_path: str) -> Dict:
    """
    Full incremental pipeline for a single uploaded file.
    Returns a status dict: {chunks_added, vectors_added, status}
    """
    logger.info(f"Incremental ingest: {rel_path}")

    pages  = _extract_pages(file_path, rel_path)
    if not pages:
        return {"chunks_added": 0, "vectors_added": 0, "status": "no_text_extracted"}

    chunks = _chunk_pages(pages)
    if not chunks:
        return {"chunks_added": 0, "vectors_added": 0, "status": "no_chunks_generated"}

    # Optional per-chunk contextual enrichment (Anthropic Contextual Retrieval).
    # When enabled, each chunk gets a Haiku-generated 1-2 sentence context that
    # situates it within its source document.  embed_text (context + raw text) is
    # what gets encoded into the FAISS vector; text is preserved for display.
    # ~49% retrieval failure reduction per Anthropic's published benchmark.
    if _ENRICHMENT_ENABLED:
        try:
            from app.chunking.contextual_enricher import enrich_document_chunks
            full_text = "\n\n".join(p.get("text", "") for p in pages)
            chunks = enrich_document_chunks(chunks, full_text, rel_path)
            logger.info(f"Contextual enrichment complete for {rel_path}")
        except Exception as exc:
            logger.warning(f"Contextual enrichment failed — continuing without it: {exc}")

    _append_to_chunks_file(chunks)
    vectors_added = _embed_and_append(chunks)

    # Update relational provisions and graph collections
    _update_relational_database(chunks)

    # Persist updated index to S3 so it survives ECS task restarts
    _persist_to_s3()

    # Signal the live retriever to reload so new docs are searchable immediately
    try:
        from app.dependencies import reload_retriever
        reload_retriever()
        logger.info("Retriever hot-reloaded after incremental ingest")
    except Exception as e:
        logger.warning(f"Retriever reload failed (restart server to pick up changes): {e}")

    return {
        "chunks_added":  len(chunks),
        "vectors_added": vectors_added,
        "status":        "success",
    }
