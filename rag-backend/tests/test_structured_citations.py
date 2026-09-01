import pytest
from app.generation.context_builder import build_context
from app.generation.context_compressor import compress_context

def test_build_context_contains_src_ids():
    chunks = [
        {
            "source": "Act/CGST Act.pdf",
            "page": 5,
            "text": "Section 16 eligibility criteria.",
            "source_type": "statute",
            "metadata": {
                "rel_path": "Act/CGST Act.pdf",
                "document_number": "12",
                "date": "2017"
            }
        },
        {
            "source": "circulars/Circular 12.pdf",
            "page": 2,
            "text": "Clarification on ITC eligibility.",
            "source_type": "circular",
            "metadata": {
                "rel_path": "circulars/Circular 12.pdf",
                "document_number": "12",
                "date": "2020"
            }
        }
    ]
    
    context = build_context(chunks)
    assert "SOURCE_ID: SRC-1" in context
    assert "SOURCE_ID: SRC-2" in context

def test_compress_context_contains_src_ids():
    chunks = [
        {
            "source": "Act/CGST Act.pdf",
            "page": 5,
            "text": "Section 16 eligibility criteria.",
            "source_type": "statute"
        }
    ]
    
    compressed = compress_context(chunks, "Section 16 eligibility")
    assert "[1] CGST Act.pdf p.5" in compressed
