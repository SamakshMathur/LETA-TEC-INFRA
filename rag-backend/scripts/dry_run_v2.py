import os
import sys
import json
import hashlib
import re
from pathlib import Path

# Resolve app root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.legal_parser import LegalParser
from app.ingestion.pdf_text import extract_text_from_pdf

def compute_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def main(base_dir=None, temp_chunks_path=None, reports_dir=None):
    if base_dir is None:
        base_dir = Path("RAG_INFORMATION_DATABASE/NEW DATABASE/Database_V2.0")
    else:
        base_dir = Path(base_dir)

    if not base_dir.exists():
        print(f"ERROR: Database_V2.0 folder not found at {base_dir}")
        sys.exit(1)

    if reports_dir is None:
        reports_dir = Path("RAG_INFORMATION_DATABASE/generated_reports")
    else:
        reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if temp_chunks_path is None:
        scratch_dir = Path("scratch")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        temp_chunks_path = scratch_dir / "chunks_v2_dry_run.jsonl"
    else:
        temp_chunks_path = Path(temp_chunks_path)

    print(f"Scanning Database_V2.0 from: {base_dir}")

    pdf_files = []
    excluded_files = []

    # 1. Walk directory and collect files
    for root, dirs, files in os.walk(base_dir):
        # Ignore hidden files
        files = [f for f in files if not f.startswith(".")]
        for file in files:
            full_path = Path(root) / file
            rel_path = str(full_path.relative_to(base_dir.parent.parent.parent))  # relative to rag-backend/

            ext = full_path.suffix.lower()
            if ext == ".pdf":
                pdf_files.append((full_path, rel_path))
            else:
                excluded_files.append((full_path, rel_path))

    print(f"Found {len(pdf_files)} PDF files and {len(excluded_files)} non-PDF files.")

    # 2. Extract and check duplicates by SHA-256
    file_hashes = {}
    duplicates = []
    for path, rel_path in pdf_files:
        f_hash = compute_sha256(path)
        if f_hash in file_hashes:
            duplicates.append({
                "sha256": f_hash,
                "file1": file_hashes[f_hash],
                "file2": rel_path,
                "size": path.stat().st_size
            })
        else:
            file_hashes[f_hash] = rel_path

    print(f"Duplicate check: {len(duplicates)} exact duplicates detected.")

    # 3. Process each PDF (Dry Run)
    all_chunks = []
    doc_stats = {
        "total_documents": len(pdf_files),
        "active_documents": 0,
        "quarantined_documents": 0,
        "total_pages": 0,
        "by_type": {},
        "by_jurisdiction": {},
        "by_authority": {},
        "missing_date": 0,
        "missing_authority": 0,
        "extraction_failures": 0,
        "zero_chunks": 0
    }

    chunk_text_hashes = set()
    seen_file_hashes = set()
    duplicate_chunks_count = 0
    empty_chunks_count = 0
    quarantined_doc_ids = set()
    total_characters_count = 0
    total_words_count = 0

    with open(temp_chunks_path, "w", encoding="utf-8") as temp_out:
        for idx, (path, rel_path) in enumerate(pdf_files):
            file_hash = compute_sha256(path)
            if file_hash in seen_file_hashes:
                print(f"[{idx+1}/{len(pdf_files)}] Skipping duplicate file {path.name} (SHA-256 already processed).")
                continue
            seen_file_hashes.add(file_hash)

            print(f"[{idx+1}/{len(pdf_files)}] Parsing {path.name}...")

            # Read text
            try:
                pages = extract_text_from_pdf(str(path))
            except Exception as e:
                print(f"ERROR: Failed to extract text from {path.name}: {e}")
                doc_stats["extraction_failures"] += 1
                continue

            if not pages:
                print(f"WARNING: No text extracted from {path.name}")
                doc_stats["zero_chunks"] += 1
                continue

            doc_stats["total_pages"] += len(pages)
            for p in pages:
                p_text = p.get("text", "")
                total_characters_count += len(p_text)
                total_words_count += len(p_text.split())
            full_text = "\n".join(p["text"] for p in pages)
            first_page = pages[0]["text"] if pages else ""

            # Metadata
            doc_meta = LegalParser.extract_document_metadata(full_text, first_page, path.name)

            # Check quarantine rules
            is_active, status = LegalParser.determine_quarantine(doc_meta)
            if not is_active:
                doc_stats["quarantined_documents"] += 1
            else:
                doc_stats["active_documents"] += 1

            # Document stats grouping
            doc_type = doc_meta["document_type"]
            doc_stats["by_type"][doc_type] = doc_stats["by_type"].get(doc_type, 0) + 1

            jur = doc_meta["jurisdiction"]
            doc_stats["by_jurisdiction"][jur] = doc_stats["by_jurisdiction"].get(jur, 0) + 1

            auth = doc_meta["authority"]
            doc_stats["by_authority"][auth] = doc_stats["by_authority"].get(auth, 0) + 1

            if doc_meta["date_year"] is None:
                doc_stats["missing_date"] += 1
            if doc_meta["authority"] == "Unknown":
                doc_stats["missing_authority"] += 1

            # Split chunks
            chunks_data = LegalParser.structural_split(full_text, doc_type)
            if not chunks_data:
                doc_stats["zero_chunks"] += 1
                continue

            # Process chunks
            for c_idx, chunk_obj in enumerate(chunks_data):
                text = chunk_obj["text"].strip()
                structure = chunk_obj["structure"]

                if not text:
                    empty_chunks_count += 1
                    continue

                # Text hash checking for duplicate chunks (scoped by document rel_path)
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                chunk_key = (rel_path, text_hash)
                if chunk_key in chunk_text_hashes:
                    duplicate_chunks_count += 1
                    continue
                else:
                    chunk_text_hashes.add(chunk_key)

                raw_citations = LegalParser.extract_citations(text, normalize=False)
                normalized_citations = LegalParser.extract_citations(text, normalize=True)
                topic = LegalParser.classify_topic(text)
                primary_provisions = [c for c in normalized_citations if "SEC" in c or "RUL" in c]

                # Check substantive/procedural
                raw_section_nums = []
                for c in normalized_citations:
                    if "SEC" in c:
                        m = re.search(r'\d+', c)
                        if m:
                            raw_section_nums.append(m.group())

                law_type = "general"
                if any(s in LegalParser.SUBSTANTIVE_SECTIONS for s in raw_section_nums):
                    law_type = "substantive"
                elif any(s in LegalParser.PROCEDURAL_SECTIONS for s in raw_section_nums):
                    law_type = "procedural"

                # Determine page containing chunk
                page_num = 1
                for p in pages:
                    if text[:100] in p["text"]:
                        page_num = p["metadata"].get("page", 1)
                        break

                doc_id = f"doc_{file_hash[:16]}"
                ver_id = f"ver_{file_hash[:16]}"
                prov_num = "general"
                if primary_provisions:
                    prov_num = primary_provisions[0].lower().replace("cgst_", "")
                prov_id = f"prov_{doc_id}_{prov_num}"

                # Construct chunk metadata
                full_meta = {
                    "document_type": doc_type,
                    "authority": auth,
                    "jurisdiction": jur,
                    "date_issued": doc_meta["date_issued"],
                    "date_year": doc_meta["date_year"],
                    "date_precision": doc_meta["date_precision"],
                    "confidence": doc_meta["confidence"],
                    "is_active": is_active,
                    "status": status,
                    "sha256": file_hash,
                    "rel_path": rel_path,
                    "source": str(path),
                    "topic": topic,
                    "law_type": law_type,
                    "citations": normalized_citations,
                    "raw_citations": raw_citations,
                    "provisions": primary_provisions,
                    "section_type": structure,
                    "page": page_num,
                    "source_hash": file_hash,
                    "text_hash": text_hash,
                    "extraction_method": "PDF_TEXT",
                    "extraction_confidence": 1.0,
                    "document_id": doc_id,
                    "version_id": ver_id,
                    "provision_id": prov_id
                }

                chunk_id = LegalParser.generate_chunk_id(full_meta, structure, text, c_idx)
                full_meta["chunk_id"] = chunk_id

                chunk_record = {
                    "chunk_id": chunk_id,
                    "text": text,
                    "metadata": full_meta,
                    "source": str(path),
                    "rel_path": rel_path
                }

                all_chunks.append(chunk_record)
                temp_out.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")

    # 4. Compute statistics on chunks
    chunk_lengths = [len(c["text"]) for c in all_chunks]

    avg_len = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
    if chunk_lengths:
        sorted_lens = sorted(chunk_lengths)
        n = len(sorted_lens)
        median_len = sorted_lens[n // 2] if n % 2 != 0 else (sorted_lens[n // 2 - 1] + sorted_lens[n // 2]) / 2.0
        p95_len = sorted_lens[int((n - 1) * 0.95)]
        max_len = max(chunk_lengths)
    else:
        median_len = 0
        p95_len = 0
        max_len = 0

    below_100 = sum(1 for l in chunk_lengths if l < 100)
    above_2000 = sum(1 for l in chunk_lengths if l > 2000)
    above_4000 = sum(1 for l in chunk_lengths if l > 4000)

    # Exclude files list formatting
    excluded_files_report = []
    for p, rel in excluded_files:
        status_flag = "UNSUPPORTED / EXCLUDED" if p.suffix == ".php" else "IGNORED"
        excluded_files_report.append({
            "rel_path": rel,
            "status": status_flag
        })

    # Group chunks by doc_type and folders
    chunks_by_type = {}
    chunks_by_folder = {}
    chunks_by_authority = {}
    chunks_by_jurisdiction = {}
    chunks_by_topic = {}
    chunks_by_law_type = {}

    for c in all_chunks:
        meta = c["metadata"]
        t = meta["document_type"]
        chunks_by_type[t] = chunks_by_type.get(t, 0) + 1

        # Folder is the first component of rel_path
        fldr = Path(c["rel_path"]).parts[2] if len(Path(c["rel_path"]).parts) > 2 else "root"
        chunks_by_folder[fldr] = chunks_by_folder.get(fldr, 0) + 1

        a = meta["authority"]
        chunks_by_authority[a] = chunks_by_authority.get(a, 0) + 1

        j = meta["jurisdiction"]
        chunks_by_jurisdiction[j] = chunks_by_jurisdiction.get(j, 0) + 1

        tp = meta["topic"]
        chunks_by_topic[tp] = chunks_by_topic.get(tp, 0) + 1

        lt = meta["law_type"]
        chunks_by_law_type[lt] = chunks_by_law_type.get(lt, 0) + 1

    report_data = {
        "corpus": {
            "pdf_files": len(pdf_files),
            "total_pages": doc_stats["total_pages"],
            "total_characters": total_characters_count,
            "estimated_words": total_words_count,
            "estimated_tokens": int(total_words_count * 1.35),
            "excluded_files": excluded_files_report
        },
        "ingestion": {
            "documents_processed": len(pdf_files) - len(duplicates),
            "documents_failed": doc_stats["extraction_failures"],
            "documents_quarantined": doc_stats["quarantined_documents"],
            "documents_skipped": len(excluded_files),
            "documents_duplicated": len(duplicates),
            "by_type": doc_stats["by_type"],
            "by_jurisdiction": doc_stats["by_jurisdiction"],
            "by_authority": doc_stats["by_authority"],
            "missing_date": doc_stats["missing_date"],
            "missing_authority": doc_stats["missing_authority"]
        },
        "chunking": {
            "total_chunks": len(all_chunks),
            "average_length": float(avg_len),
            "median_length": float(median_len),
            "p95_length": float(p95_len),
            "max_length": int(max_len),
            "below_100": below_100,
            "above_2000": above_2000,
            "above_4000": above_4000,
            "duplicate_chunks": duplicate_chunks_count,
            "empty_chunks": empty_chunks_count,
            "chunks_by_type": chunks_by_type,
            "chunks_by_folder": chunks_by_folder,
            "chunks_by_authority": chunks_by_authority,
            "chunks_by_jurisdiction": chunks_by_jurisdiction,
            "chunks_by_topic": chunks_by_topic,
            "chunks_by_law_type": chunks_by_law_type
        }
    }

    # Write report json
    report_json_path = reports_dir / "v2_dry_run_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Written JSON report to: {report_json_path}")

    # Write report txt
    report_txt_path = reports_dir / "v2_dry_run_report.txt"
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write("=== DATABASE_V2.0 DRY RUN AUDIT REPORT ===\n\n")
        f.write(f"Total PDFs Scanned : {len(pdf_files)}\n")
        f.write(f"Total Pages        : {doc_stats['total_pages']}\n")
        f.write(f"Total Chunks       : {len(all_chunks)}\n\n")
        f.write("=== INGESTION DIMS ===\n")
        f.write(f"Active Docs        : {doc_stats['active_documents']}\n")
        f.write(f"Quarantined Docs   : {doc_stats['quarantined_documents']}\n")
        f.write(f"Missing Dates      : {doc_stats['missing_date']}\n")
        f.write(f"Missing Authority  : {doc_stats['missing_authority']}\n\n")
        f.write("=== CHUNK QUALITY ===\n")
        f.write(f"Average Length     : {avg_len:.1f}\n")
        f.write(f"Median Length      : {median_len:.1f}\n")
        f.write(f"P95 Length         : {p95_len:.1f}\n")
        f.write(f"Max Length         : {max_len}\n")
        f.write(f"Under 100 chars    : {below_100}\n")
        f.write(f"Over 2000 chars    : {above_2000}\n")
        f.write(f"Over 4000 chars    : {above_4000}\n")
        f.write(f"Duplicate Chunks   : {duplicate_chunks_count}\n")
        f.write(f"Empty Chunks       : {empty_chunks_count}\n\n")
        f.write("=== EXCLUDED FILES ===\n")
        for x in excluded_files_report:
            f.write(f"- {x['rel_path']} [{x['status']}]\n")

    print(f"Written Text report to: {report_txt_path}")
    print(f"Temporary chunks file generated at: {temp_chunks_path}")
    print("V2.0 DRY RUN COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    main()
