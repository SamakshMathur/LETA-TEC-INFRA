"""
test_deduplication.py — Phase 5 Active Deduplication Verification

Tests:
  1. Exact duplicate PDF files (identical binary SHA-256): First file is processed, second is skipped.
  2. Different PDF files with identical content (distinct binary SHA-256): Treated as distinct files.
  3. Same document + identical chunk text: First chunk is retained, duplicate chunk is skipped.
  4. Different documents + identical chunk text: Both chunks are retained under their respective documents.
  5. Unique chunks: Retained completely unchanged.
  6. Metadata/provenance: Retained chunks keep their exact original rel_path, source, document_type, citations, provisions, chunk_id, etc.
  7. Duplicate chunks: Not written to the chunks_v2_dry_run.jsonl file.
  8. Statistics: Duplicate count and unique chunk count reconcile correctly.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

# Resolve app root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts import dry_run_v2


# ─── Mock helper for extract_text_from_pdf ──────────────────────────────────

def mock_extract_text_from_pdf(path):
    """
    Mock PDF text extraction based on filename to simulate different chunk texts,
    including duplicate chunk text within the same document and across different documents.
    """
    filename = Path(path).name
    
    if filename == "file1.pdf" or filename == "file2.pdf":
        # file1 and file2 are identical binary files (exact duplicates).
        # Both produce this text if processed.
        return [
            {
                "text": "Section 16 under CGST Act. Eligibility for input tax credit. (1) Every registered person shall be entitled to take credit.",
                "metadata": {"page": 1}
            }
        ]
        
    elif filename == "file3.pdf":
        # file3 has different binary contents but produces the same chunk text as file1.
        # This is a different document with identical content.
        return [
            {
                "text": "Section 16 under CGST Act. Eligibility for input tax credit. (1) Every registered person shall be entitled to take credit.",
                "metadata": {"page": 1}
            }
        ]
        
    elif filename == "file4.pdf":
        # file4 contains repeating/duplicate chunk text inside the SAME document.
        # The first chunk should be kept, the second duplicate chunk skipped.
        return [
            {
                "text": "Rule 89 under CGST Rules. Application for refund. (1) Any person claiming refund of tax may make an application.",
                "metadata": {"page": 1}
            },
            {
                "text": "Rule 89 under CGST Rules. Application for refund. (1) Any person claiming refund of tax may make an application.",
                "metadata": {"page": 2}  # identical chunk text on page 2
            },
            {
                "text": "Rule 89 under CGST Rules. Rule 89 sub-rule (2). Here is some unique text on page 3.",
                "metadata": {"page": 3}  # unique chunk in file4
            }
        ]
        
    elif filename == "file5.pdf":
        # file5 is a completely unique document with unique chunk text.
        return [
            {
                "text": "Section 17 under CGST Act. Apportionment of credit and blocked credits. (1) Where the goods or services are used partly for business.",
                "metadata": {"page": 1}
            }
        ]
        
    return []


# ─── Test Suite ───────────────────────────────────────────────────────────────

class TestActiveDeduplication(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for our mock database
        self.test_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.test_dir.name) / "Database_V2.0"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.reports_dir = Path(self.test_dir.name) / "generated_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.temp_chunks_path = Path(self.test_dir.name) / "chunks_v2_dry_run.jsonl"
        
        # Create mock target subfolders
        (self.base_dir / "CGST Acts").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "CGST Rules").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "IGST Acts").mkdir(parents=True, exist_ok=True)
        
        # Write dummy binary PDF files (binary contents define SHA-256 identity)
        # file1 and file2 are identical binary files (same SHA-256)
        (self.base_dir / "CGST Acts" / "file1.pdf").write_bytes(b"pdf_binary_content_alpha")
        (self.base_dir / "CGST Acts" / "file2.pdf").write_bytes(b"pdf_binary_content_alpha") # exact binary duplicate
        
        # file3 has different binary contents but produces the same chunk text
        (self.base_dir / "CGST Acts" / "file3.pdf").write_bytes(b"pdf_binary_content_beta")
        
        # file4 has different binary content, produces duplicate chunks within itself
        (self.base_dir / "CGST Rules" / "file4.pdf").write_bytes(b"pdf_binary_content_gamma")
        
        # file5 is completely unique
        (self.base_dir / "IGST Acts" / "file5.pdf").write_bytes(b"pdf_binary_content_delta")

    def tearDown(self):
        self.test_dir.cleanup()

    @patch("scripts.dry_run_v2.extract_text_from_pdf", side_effect=mock_extract_text_from_pdf)
    def test_end_to_end_deduplication(self, mock_extract):
        """Runs the parameterized dry_run_v2 script and asserts all active deduplication invariants."""
        # Run the dry run script on the mock directory
        dry_run_v2.main(
            base_dir=self.base_dir,
            temp_chunks_path=self.temp_chunks_path,
            reports_dir=self.reports_dir
        )
        
        # Load the output chunks file
        self.assertTrue(self.temp_chunks_path.exists(), "Output chunks JSONL file must be created")
        
        chunks = []
        with open(self.temp_chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
                    
        # Load report statistics
        report_json_path = self.reports_dir / "v2_dry_run_report.json"
        self.assertTrue(report_json_path.exists(), "Report JSON file must be created")
        with open(report_json_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        # ── Verification 1: Exact duplicate files are skipped globally ──────────
        # Since file1.pdf and file2.pdf are binary duplicates, only one must produce chunks.
        file1_chunks = [c for c in chunks if "file1.pdf" in c["rel_path"]]
        file2_chunks = [c for c in chunks if "file2.pdf" in c["rel_path"]]
        
        self.assertGreater(len(file1_chunks), 0, "Unique file1.pdf must be parsed and processed")
        self.assertEqual(len(file2_chunks), 0, "Binary duplicate file2.pdf must be completely skipped")

        # ── Verification 2: Different files with identical content are kept ─────
        # file1 and file3 produce the same text but have different SHA-256 hashes.
        # Under the binary SHA-256 rule, both must be processed.
        file3_chunks = [c for c in chunks if "file3.pdf" in c["rel_path"]]
        self.assertGreater(len(file3_chunks), 0, "file3.pdf must be processed since it is binary distinct")
        
        # Compare texts
        self.assertEqual(
            file1_chunks[0]["text"],
            file3_chunks[0]["text"],
            "Sanity check: file1 and file3 chunks must have identical text"
        )
        # Verify both survived under their respective relative paths (provenance)
        self.assertNotEqual(
            file1_chunks[0]["rel_path"],
            file3_chunks[0]["rel_path"],
            "Unique relative paths must be preserved"
        )

        # ── Verification 3: Same document + identical chunk text: duplicate skipped ─
        # file4 produces duplicate chunks on page 1 and page 2, and a unique chunk on page 3.
        # Only the page 1 chunk and page 3 chunk should remain.
        file4_chunks = [c for c in chunks if "file4.pdf" in c["rel_path"]]
        self.assertEqual(len(file4_chunks), 2, "file4 should produce exactly 2 unique chunks (the duplicate is skipped)")
        
        # Verify first occurrence was kept (page 1) and second (page 2) was skipped
        self.assertEqual(file4_chunks[0]["metadata"]["page"], 1, "The first duplicate chunk occurrence (page 1) must be retained")
        self.assertEqual(file4_chunks[1]["metadata"]["page"], 3, "The unique chunk on page 3 must be retained")

        # ── Verification 4: Unique chunks are retained unchanged ──────────────────
        file5_chunks = [c for c in chunks if "file5.pdf" in c["rel_path"]]
        self.assertEqual(len(file5_chunks), 1, "Unique document file5.pdf must retain its unique chunk")

        # ── Verification 5: Metadata and provenance preservation ─────────────────
        # Inspect retained chunk's metadata fields
        retained = file1_chunks[0]
        self.assertIn("chunk_id", retained)
        self.assertIn("metadata", retained)
        
        meta = retained["metadata"]
        self.assertTrue(meta["rel_path"].endswith("Database_V2.0/CGST Acts/file1.pdf"))
        self.assertEqual(meta["document_type"], "PRIMARY_LAW")
        self.assertEqual(meta["topic"], "ITC")
        self.assertEqual(meta["law_type"], "substantive")

        # ── Verification 6: Report statistics reconcile correctly ─────────────────
        # Let's check report numbers:
        # Total scanned PDFs: 5 (file1, file2, file3, file4, file5)
        # Duplicate files skipped: 1 (file2)
        # Unique files processed: 4
        self.assertEqual(report_data["ingestion"]["documents_processed"], 4)
        self.assertEqual(report_data["ingestion"]["documents_duplicated"], 1)
        
        # Chunk level:
        # file1: 1 chunk (unique)
        # file3: 1 chunk (unique across files)
        # file4: 3 chunks generated, 1 duplicate skipped -> 2 chunks written, 1 duplicate counted
        # file5: 1 chunk (unique)
        # Total unique chunks written = 1 + 1 + 2 + 1 = 5
        self.assertEqual(len(chunks), 5, "Total chunks written to JSONL must match unique count")
        self.assertEqual(report_data["chunking"]["total_chunks"], 5)
        self.assertEqual(report_data["chunking"]["duplicate_chunks"], 1)

        # ── Verification 7: Exclude skipped duplicate files from parsing ──────────
        called_files = [Path(args[0]).name for args, kwargs in mock_extract.call_args_list]
        self.assertIn("file1.pdf", called_files, "file1.pdf must be parsed")
        self.assertIn("file3.pdf", called_files, "file3.pdf must be parsed")
        self.assertIn("file4.pdf", called_files, "file4.pdf must be parsed")
        self.assertIn("file5.pdf", called_files, "file5.pdf must be parsed")
        self.assertNotIn("file2.pdf", called_files, "file2.pdf (duplicate) must NEVER be parsed")


if __name__ == "__main__":
    unittest.main()
