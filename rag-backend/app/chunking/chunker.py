import re
import json
from pathlib import Path
from typing import List, Dict, Optional

MAX_TOKENS = 500       # conservative — real token count is ~1.3x word count for legal text
OVERLAP_TOKENS = 80    # overlap in words

# Legal section header patterns — never split in the middle of these
SECTION_PATTERNS = [
    r'^\s*Section\s+\d+[\w\(\)]*',          # Section 17(5)
    r'^\s*Sec\.\s*\d+[\w\(\)]*',            # Sec. 17
    r'^\s*Rule\s+\d+[\w\(\)]*',             # Rule 36(4)
    r'^\s*Article\s+\d+[\w\(\)]*',          # Article 246A
    r'^\s*\d+\.\s+[A-Z]',                   # Numbered top-level paragraphs: "1. Short title..."
    r'^\s*\(\d+\)\s',                        # Sub-sections: "(1) ", "(2) "
    r'^\s*\([a-z]\)\s',                      # Clauses: "(a) ", "(b) "
    r'^\s*[A-Z]{2,}',                        # ALL-CAPS headings (CHAPTER, PART, SCHEDULE)
    r'^\s*Provided\s+that',                  # Proviso — must stay with parent
    r'^\s*Explanation[—\-\.]',               # Explanation clause
    r'^\s*WHEREAS',                          # Notification preamble
    r'^\s*NOW,\s+THEREFORE',                 # Notification body
]

_section_re = re.compile('|'.join(SECTION_PATTERNS), re.MULTILINE)

# Patterns to extract section/rule numbers from a heading line for metadata
_SECTION_NUM_RE = re.compile(
    r'(?:Section|Sec\.)\s*(\d+[\w\(\)]*)', re.IGNORECASE
)
_RULE_NUM_RE = re.compile(
    r'Rule\s+(\d+[\w\(\)]*)', re.IGNORECASE
)
_ARTICLE_NUM_RE = re.compile(
    r'Article\s+(\d+[\w\(\)]*)', re.IGNORECASE
)


def approx_token_len(text: str) -> int:
    """
    More accurate token estimate for legal text.
    Legal language has long words — multiply word count by 1.35 to approximate
    subword tokens (BPE). This avoids silent context overflow.
    """
    words = len(text.split())
    return int(words * 1.35)


def is_section_boundary(para: str) -> bool:
    """Returns True if this paragraph starts a new legal section/provision."""
    return bool(_section_re.match(para.strip()))


def extract_section_label(para: str) -> Optional[str]:
    """
    Returns a short section label from a boundary paragraph if detectable.
    e.g. "Section 17(5) Apportionment..." → "Section 17(5)"
         "Rule 36(4) ..."                 → "Rule 36(4)"
    Returns None if no structured label found.
    """
    m = _SECTION_NUM_RE.search(para)
    if m:
        return f"Section {m.group(1)}"
    m = _RULE_NUM_RE.search(para)
    if m:
        return f"Rule {m.group(1)}"
    m = _ARTICLE_NUM_RE.search(para)
    if m:
        return f"Article {m.group(1)}"
    return None


def split_oversized_para(para: str, max_tokens: int) -> List[str]:
    """
    If a single paragraph exceeds max_tokens (e.g. a giant run-on proviso),
    split it at sentence boundaries rather than mid-word.
    """
    if approx_token_len(para) <= max_tokens:
        return [para]

    sentences = re.split(r'(?<=[.;])\s+', para)
    sub_chunks = []
    current = []
    current_len = 0

    for sent in sentences:
        sent_len = approx_token_len(sent)
        if current_len + sent_len > max_tokens and current:
            sub_chunks.append(" ".join(current))
            current = [sent]
            current_len = sent_len
        else:
            current.append(sent)
            current_len += sent_len

    if current:
        sub_chunks.append(" ".join(current))

    return sub_chunks if sub_chunks else [para]


def chunk_text(paragraphs: List[str]) -> List[str]:
    """
    Section-aware chunker for legal documents.
    Returns plain text chunks (backward-compatible with existing pipeline).
    For chunks with metadata use chunk_text_with_metadata().
    """
    return [c["text"] for c in chunk_text_with_metadata(paragraphs)]


def chunk_text_with_metadata(paragraphs: List[str]) -> List[Dict]:
    """
    Section-aware chunker that returns dicts with both text and metadata.

    Each returned dict:
    {
        "text": str,                    # chunk content
        "section_label": str | None,    # e.g. "Section 17(5)" — for citation verifier
        "section_labels": [str],        # all section labels present in this chunk
    }

    Rules:
    1. Never break a chunk in the middle of a legal section boundary.
    2. Use real token estimation (1.35x word count) to avoid overflows.
    3. Carry an overlap of the last N words into the next chunk.
    4. Oversized paragraphs are split at sentence/semicolon boundaries.
    5. Each chunk records which section(s) it covers — used downstream
       by the citation verifier for exact, reliable verification.
    """
    chunks: List[Dict] = []
    current_parts: List[str] = []
    current_len = 0
    current_section_labels: List[str] = []   # sections seen in current chunk
    active_section: Optional[str] = None     # most recent section heading

    def flush(parts, labels):
        text = " ".join(parts).strip()
        if text:
            chunks.append({
                "text": text,
                "section_label": labels[0] if labels else None,
                "section_labels": list(labels),
            })

    for raw_para in paragraphs:
        para = raw_para.strip()
        if not para:
            continue

        sub_paras = split_oversized_para(para, MAX_TOKENS)

        for sub in sub_paras:
            sub_len = approx_token_len(sub)
            starts_section = is_section_boundary(sub)

            if starts_section:
                label = extract_section_label(sub)
                if label:
                    active_section = label

            # Rule 1: flush on section boundary
            if starts_section and current_parts:
                flush(current_parts, current_section_labels)
                overlap_words = " ".join(current_parts).split()[-OVERLAP_TOKENS:]
                current_parts = [" ".join(overlap_words)] if overlap_words else []
                current_len = approx_token_len(current_parts[0]) if current_parts else 0
                current_section_labels = [active_section] if active_section else []

            # Rule 2: flush on size limit
            if current_len + sub_len > MAX_TOKENS and current_parts:
                flush(current_parts, current_section_labels)
                overlap_words = " ".join(current_parts).split()[-OVERLAP_TOKENS:]
                current_parts = [" ".join(overlap_words)] if overlap_words else []
                current_len = approx_token_len(current_parts[0]) if current_parts else 0
                # Inherit active section into next chunk
                current_section_labels = [active_section] if active_section else []

            current_parts.append(sub)
            current_len += sub_len

            # Track new section labels entering this chunk
            if starts_section and active_section and active_section not in current_section_labels:
                current_section_labels.append(active_section)

    # Flush remainder
    flush(current_parts, current_section_labels)

    return chunks
