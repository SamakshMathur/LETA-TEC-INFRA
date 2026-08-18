import re
import unicodedata

def clean_text(text: str) -> str:
    # Normalize unicode characters (e.g., smart quotes -> normal quotes, ligatures -> split chars)
    text = unicodedata.normalize('NFKD', text)
    
    # Remove form feeds
    text = text.replace("\x0c", "")
    
    # Collapse multiple spaces
    text = re.sub(r"[ \t]+", " ", text)
    
    # Normalize newlines (max 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove remaining non-printable control chars, but keep newlines
    text = "".join(ch for ch in text if ch.isprintable() or ch == '\n')

    return text.strip()