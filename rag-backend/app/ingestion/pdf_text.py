import fitz  # PyMuPDF

def extract_text_from_pdf(path):
    doc = fitz.open(path)
    pages = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({
                "text": text,
                "metadata": {
                    "source": str(path),
                    "page": page_num + 1,
                    "type": "pdf_text"
                }
            })

    return pages