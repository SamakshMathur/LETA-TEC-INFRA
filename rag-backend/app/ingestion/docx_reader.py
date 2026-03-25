import subprocess
from docx import Document


def extract_text_from_docx(path):
    doc = Document(path)
    text_blocks = []

    full_text = "\n".join(
        p.text for p in doc.paragraphs if p.text.strip()
    )

    if full_text.strip():
        text_blocks.append({
            "text": full_text,
            "metadata": {
                "source": str(path),
                "type": "docx"
            }
        })

    return text_blocks


def extract_text_from_doc(path):
    """Extract text from legacy .doc files using antiword."""
    text_blocks = []
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True, text=True, timeout=30
        )
        full_text = result.stdout.strip()
        if full_text:
            text_blocks.append({
                "text": full_text,
                "metadata": {
                    "source": str(path),
                    "type": "doc"
                }
            })
    except Exception as e:
        print(f"antiword failed for {path}: {e}")
    return text_blocks