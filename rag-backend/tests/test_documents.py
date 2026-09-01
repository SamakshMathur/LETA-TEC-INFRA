import os
import shutil
import urllib.parse
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.documents import BASE_DIR, UPLOADS_DIR, _find_local, register_new_file_in_cache

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_files():
    # Make sure BASE_DIR and UPLOADS_DIR exist
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create test files
    test_files = [
        BASE_DIR / "Act" / "CGST.pdf",
        BASE_DIR / "rule" / "rule" / "CGST Rules.pdf",
        UPLOADS_DIR / "123456_CGST.pdf",
        BASE_DIR / "Act" / "CGST (Amended).pdf",
        BASE_DIR / "Act" / "नियम.pdf",
    ]
    
    created = []
    for f in test_files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4 mock content")
        created.append(f)
        # Register in cache
        register_new_file_in_cache(f)
        
    yield
    
    # Cleanup only the created files
    for f in created:
        try:
            f.unlink()
        except Exception:
            pass

def test_find_local_cases():
    # Windows path
    assert _find_local("Act\\CGST.pdf") is not None
    # Linux path
    assert _find_local("Act/CGST.pdf") is not None
    # Nested folder
    assert _find_local("Rules/CGST Rules.pdf") is not None
    # UUID upload
    assert _find_local("123456_CGST.pdf") is not None
    # Special characters
    assert _find_local("CGST (Amended).pdf") is not None
    # Unicode
    assert _find_local("नियम.pdf") is not None
    # Missing
    assert _find_local("non_existent_file.pdf") is None

def test_api_view_document():
    # Test GET /view (200)
    resp = client.get("/api/documents/view?category=all&filename=CGST.pdf")
    assert resp.status_code == 200
    
    # Test GET /view with UUID upload
    resp = client.get("/api/documents/view?category=all&filename=123456_CGST.pdf")
    assert resp.status_code == 200

def test_api_view_by_path():
    # Test GET /view_by_path (200)
    path_enc = urllib.parse.quote("Act/CGST.pdf")
    resp = client.get(f"/api/documents/view_by_path?path={path_enc}")
    assert resp.status_code == 200

def test_api_invalid_path():
    # Test GET /view_by_path with non-existent path (404)
    path_enc = urllib.parse.quote("NonExistent/file.pdf")
    resp = client.get(f"/api/documents/view_by_path?path={path_enc}")
    assert resp.status_code == 404

def test_api_traversal_attack():
    # Test Traversal attack (403 or 400)
    resp = client.get("/api/documents/view_by_path?path=../../../etc/passwd")
    assert resp.status_code in (400, 403)

def test_api_double_encoding():
    # Test Double encoding (%252e%252e -> Reject with 400 or 403)
    resp = client.get("/api/documents/view_by_path?path=%252e%252e%252f%252e%252e%252f%252e%252e%252fetc%252fpasswd")
    assert resp.status_code in (400, 403)
