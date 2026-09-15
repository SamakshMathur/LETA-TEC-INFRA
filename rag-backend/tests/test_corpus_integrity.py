"""
Test Suite: Corpus Provision Metadata Integrity & Structural Section Detection
==============================================================================
Validates that:
1. Primary section headings take precedence over cross-references and footnotes.
2. Multiple genuine section boundaries within a single chunk are preserved.
3. Subsections are correctly associated with their parent provisions.
4. Footnote and amendment annotations do not create bogus primary provision keys.
5. Standalone numbered section starts ("16. (1) Zero rated supply") are recognized.
6. The Corpus Integrity Gate detects and blocks structural metadata mismatches.
"""

import pytest
from app.ingestion.provision_extractor import (
    StructuralProvisionExtractor,
    StructuralProvisionResult,
    resolve_default_act,
)
from scripts.validate_corpus_integrity import validate_corpus, CorpusIntegrityReport


class TestStructuralSectionDetection:
    """Test suite for data-driven statutory section detection."""

    def test_primary_header_vs_cross_references(self):
        """
        A chunk whose primary heading is Section 16 but references Section 17, 50, 54
        must retain Section 16 as its primary provision key.
        """
        text = """
        Section - 16, Integrated Goods And Services Tax Act, 2017
        CHAPTER VII
        ZERO RATED SUPPLY
        Zero rated supply.
        16. (1) "Zero rated supply" means any of the following supplies of goods or services:
        (a) export of goods or services or both;
        (2) Subject to the provisions of sub-section (5) of section 17 of the Central Goods and Services Tax Act...
        (3) A registered person shall be eligible for refund in accordance with section 54 of the Central Goods and Services Tax Act...
        Provided that interest shall be applicable under section 50 of the Central Goods and Services Tax Act...
        """
        rel_path = "Database_V2.0/IGST Acts/IGST Act.pdf"
        result = StructuralProvisionExtractor.extract(text, rel_path)

        assert "IGST_SEC_16" in result.primary_provision_keys
        assert result.primary_section_label == "Section 16"
        assert "CGST_SEC_17" in result.secondary_citation_keys
        assert "CGST_SEC_50" in result.secondary_citation_keys
        assert "CGST_SEC_54" in result.secondary_citation_keys

        # Crucial invariant: CGST sections must NOT be labeled as IGST_SEC_17/50/54
        assert "IGST_SEC_17" not in result.primary_provision_keys
        assert "IGST_SEC_50" not in result.primary_provision_keys
        assert "IGST_SEC_54" not in result.primary_provision_keys

    def test_standalone_numbered_section_start(self):
        """
        Statutory body text starting with "16. (1) \"Zero rated supply\"" without "Section" keyword.
        """
        text = """
        16. (1) "Zero rated supply" means any of the following supplies of goods or services or both, namely:—
        (a) export of goods or services or both; or
        (b) supply of goods or services or both to a Special Economic Zone developer.
        """
        rel_path = "Database_V2.0/IGST Acts/IGST Act.pdf"
        result = StructuralProvisionExtractor.extract(text, rel_path)

        assert "IGST_SEC_16" in result.primary_provision_keys
        assert "Section 16" in result.primary_section_labels

    def test_multiple_genuine_section_boundaries(self):
        """
        A chunk legitimately containing two section headers must represent both.
        """
        text = """
        Section 15. Apportionment of tax between Centre and States.
        (1) The integrated tax paid on supply shall be apportioned...
        
        Section 16. Zero rated supply.
        (1) "Zero rated supply" means export of goods or services...
        """
        rel_path = "Database_V2.0/IGST Acts/IGST Act.pdf"
        result = StructuralProvisionExtractor.extract(text, rel_path)

        assert "IGST_SEC_15" in result.primary_provision_keys
        assert "IGST_SEC_16" in result.primary_provision_keys
        assert "Section 15" in result.primary_section_labels
        assert "Section 16" in result.primary_section_labels

    def test_rule_headers_and_cross_references(self):
        """
        Rule headers must be recognized with CGST/IGST prefix matching the document.
        """
        text = """
        Rule 96. Refund of integrated tax paid on goods or services exported out of India.—
        (1) The shipping bill filed by an exporter of goods shall be deemed to be an application for refund...
        (2) The details of the relevant export invoices in FORM GSTR-1 shall be transmitted...
        """
        rel_path = "Database_V2.0/CGST Rules 10-08-2026/cgst_rules.pdf"
        result = StructuralProvisionExtractor.extract(text, rel_path)

        assert "CGST_RUL_96" in result.primary_provision_keys
        assert "Rule 96" in result.primary_section_labels

    def test_footnote_amendments_do_not_create_primary_keys(self):
        """
        Footnote text containing numbered lines like "31. Enforced with effect from 1-7-2017"
        must not be mistaken for Section 31.
        """
        text = """
        31. Enforced with effect from 1-7-2017.
        32. Inserted by the Integrated Goods and Services Tax (Amendment) Act, 2018, w.e.f. 1-2-2019.
        Section 16. Zero rated supply.
        (1) "Zero rated supply" means export...
        """
        rel_path = "Database_V2.0/IGST Acts/IGST Act.pdf"
        result = StructuralProvisionExtractor.extract(text, rel_path)

        assert "IGST_SEC_16" in result.primary_provision_keys
        assert "IGST_SEC_31" not in result.primary_provision_keys
        assert "IGST_SEC_32" not in result.primary_provision_keys

    def test_circular_and_notification_identity(self):
        """
        Circular and Notification chunks must have their document IDs extracted.
        """
        text = """
        Circular No. 131/1/2020-GST
        Subject: Standard Operating Procedure (SOP) for verification of CGST/SGST/IGST export refunds.
        """
        rel_path = "Database_V2.0/circulars(2017-2025)/2020/circular-131-01-2020.pdf"
        result = StructuralProvisionExtractor.extract(text, rel_path, category="circulars")

        assert "CIRCULAR_131" in result.primary_provision_keys


class TestCorpusIntegrityGate:
    """Test suite for the reusable Corpus Integrity Gate auditor."""

    def test_gate_detects_and_blocks_mismatched_metadata(self):
        """
        Simulate a corrupted chunk (like Chunk 2940's original defect):
        Source text establishes Section 16, but metadata contains Section 17, 50, 54.
        The Integrity Gate MUST fail (passed = False).
        """
        corrupted_chunks = [
            {
                "chunk_id": "corrupted_chunk_001",
                "rel_path": "Database_V2.0/IGST Acts/IGST Act.pdf",
                "text": "Section - 16, Integrated Goods And Services Tax Act, 2017\n16. (1) Zero rated supply means export...",
                "metadata": {
                    "rel_path": "Database_V2.0/IGST Acts/IGST Act.pdf",
                    "chunk_id": "corrupted_chunk_001",
                    "chunk_index": 11,
                    "provision_keys": ["IGST_SEC_17", "IGST_SEC_50", "IGST_SEC_54"],
                    "section_label": "section 17",
                }
            }
        ]

        report = validate_corpus(corrupted_chunks)
        assert report.passed is False
        assert report.provision_metadata_mismatches == 1
        assert len(report.mismatches) == 1
        assert report.mismatches[0].chunk_id == "corrupted_chunk_001"
        assert "IGST_SEC_16" in report.mismatches[0].missing_provisions

    def test_gate_passes_consistent_metadata(self):
        """
        Consistent chunks where structural primary provisions match metadata MUST pass.
        """
        clean_chunks = [
            {
                "chunk_id": "clean_chunk_001",
                "rel_path": "Database_V2.0/IGST Acts/IGST Act.pdf",
                "text": "Section - 16, Integrated Goods And Services Tax Act, 2017\n16. (1) Zero rated supply means export...",
                "metadata": {
                    "rel_path": "Database_V2.0/IGST Acts/IGST Act.pdf",
                    "chunk_id": "clean_chunk_001",
                    "chunk_index": 11,
                    "provision_keys": ["IGST_SEC_16"],
                    "section_label": "Section 16",
                    "section_labels": ["Section 16"],
                }
            },
            {
                "chunk_id": "clean_chunk_002",
                "rel_path": "Database_V2.0/CGST Rules 10-08-2026/cgst_rules.pdf",
                "text": "Rule 96. Refund of integrated tax paid on goods or services exported out of India...",
                "metadata": {
                    "rel_path": "Database_V2.0/CGST Rules 10-08-2026/cgst_rules.pdf",
                    "chunk_id": "clean_chunk_002",
                    "chunk_index": 45,
                    "provision_keys": ["CGST_RUL_96"],
                    "section_label": "Rule 96",
                    "section_labels": ["Rule 96"],
                }
            }
        ]

        report = validate_corpus(clean_chunks)
        assert report.passed is True
        assert report.provision_metadata_mismatches == 0
        assert report.missing_provision_index_mappings == 0
        assert len(report.mismatches) == 0
