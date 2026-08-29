import logging
import subprocess
import tempfile
from pathlib import Path

from docx import Document

logger = logging.getLogger(__name__)


def extract_text_from_docx(path) -> list:
    """Extract text from a modern .docx file using python-docx."""
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if not full_text.strip():
        return []
    return [{
        "text": full_text,
        "metadata": {"source": str(path), "type": "docx"},
    }]


def extract_text_from_doc(path) -> list:
    """
    Extract text from a legacy .doc file (binary Word 97-2003 format).

    Strategy (tried in order):
      1. LibreOffice headless: convert .doc → .docx in a temp dir, then read
         with python-docx.  Most reliable; available on the ECS image.
      2. antiword: lightweight CLI tool, available via `apt install antiword`.
      3. Graceful empty fallback: logs a warning rather than crashing the
         entire ingestion run over one unreadable legacy file.

    This function was previously imported but never defined in docx_reader.py,
    causing an ImportError that crashed every ingestion startup.
    """
    path = Path(path)

    # ── Strategy 1: LibreOffice ───────────────────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "libreoffice", "--headless", "--convert-to", "docx",
                    "--outdir", tmpdir, str(path),
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                converted = Path(tmpdir) / (path.stem + ".docx")
                if converted.exists():
                    return extract_text_from_docx(converted)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
        logger.debug(f"LibreOffice .doc conversion failed (non-fatal): {exc}")

    # ── Strategy 2: antiword ─────────────────────────────────────────────────
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [{
                "text": result.stdout.strip(),
                "metadata": {"source": str(path), "type": "doc"},
            }]
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
        logger.debug(f"antiword .doc extraction failed (non-fatal): {exc}")

    # ── Strategy 3: graceful fallback ────────────────────────────────────────
    logger.warning(
        f"Could not extract text from legacy .doc file: {path.name} — "
        "neither LibreOffice nor antiword is available.  File skipped."
    )
    return []