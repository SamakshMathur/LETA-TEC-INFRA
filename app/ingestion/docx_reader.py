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