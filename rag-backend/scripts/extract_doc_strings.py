import re
import sys
from pathlib import Path

def extract_strings_from_doc(file_path):
    """
    Fallback extraction for legacy .doc (OLE2) files.
    Extracts sequences of printable characters.
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Regex for printable ASCII sequences (at least 4 chars long)
        # Note: .doc files often use UTF-16 internally for many strings.
        # We'll try to capture both ASCII and UTF-16
        
        # 1. ASCII strings
        ascii_strings = re.findall(b'[ -~]{4,}', content)
        text_ascii = "\n".join([s.decode('ascii', errors='ignore') for s in ascii_strings])
        
        # 2. UTF-16LE strings (common in .doc)
        utf16_strings = re.findall(b'(?:[\x20-\x7E][\x00]){4,}', content)
        text_utf16 = "\n".join([s.decode('utf-16le', errors='ignore') for s in utf16_strings])
        
        combined = text_ascii + "\n" + text_utf16
        
        # Basic cleanup
        lines = []
        for line in combined.split('\n'):
            line = line.strip()
            if len(line) > 10: # Only keep meaningful lines
                lines.append(line)
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error extracting from {file_path}: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(extract_strings_from_doc(sys.argv[1]))
