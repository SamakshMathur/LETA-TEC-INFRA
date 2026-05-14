import os
import re

# Character caps — tuned for TITAN sub-5s target.
# MAX_CHUNK_CHARS: 1000 chars ≈ 250 tokens — enough for one full statutory paragraph.
# MAX_CONTEXT_CHARS: 15000 chars ≈ 3750 tokens — keeps total LLM input well under 6KB.
# (Previous values: 80 000 / 3 000 caused 12 000-18 000 token context injections.)
MAX_CONTEXT_CHARS = 15000
MAX_CHUNK_CHARS = 1000

# ─────────────────────────────────────────────────────────────
# Citation extraction patterns — used to build the registry
# ─────────────────────────────────────────────────────────────
_CITATION_PATTERNS = [
    r'\bSection\s+\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bSec\.\s*\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bRule\s+\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bArticle\s+\d+[A-Z]?\s*(?:\(\d+[A-Z]?\))*',
    r'\bNotification\s+No\.?\s*[\d]+\s*/\s*[\d\-\w]+(?:-\w+)*',
    r'\bCircular\s+No\.?\s*[\d]+\s*/\s*[\d\-\w]+(?:/[\d\w]+)*',
    r'\bOrder\s+No\.?\s*[\d/\-\w]+',
    r'\bSchedule\s+[IVX]+',
]


def _extract_legal_refs(text: str) -> list:
    """Extract all legal references from a text snippet."""
    refs = set()
    for pat in _CITATION_PATTERNS:
        for m in re.findall(pat, text, re.IGNORECASE):
            clean = m.strip()
            if len(clean) > 4:  # filter junk
                refs.add(clean)
    return sorted(refs)


def build_citation_registry(chunks: list[dict]) -> str:
    """
    Pre-extracts ALL legal citations that appear in the retrieved chunks.
    Returns a formatted registry that locks the LLM to only verified refs.
    """
    all_refs = {}  # ref -> [source filenames]
    
    for c in chunks:
        text = c.get('text', '')
        source = os.path.basename(c.get('source', 'Unknown'))
        refs = _extract_legal_refs(text)
        for ref in refs:
            if ref not in all_refs:
                all_refs[ref] = []
            if source not in all_refs[ref]:
                all_refs[ref].append(source)
    
    if not all_refs:
        return "⚠️ No specific legal provisions extracted from the retrieved documents."
    
    lines = ["The following legal references were FOUND IN THE RETRIEVED DOCUMENTS.",
             "You MAY ONLY cite the references listed here. Any citation not on this list is PROHIBITED:\n"]
    
    for ref, sources in sorted(all_refs.items()):
        src_list = ", ".join(sources[:2])  # max 2 source names per ref
        lines.append(f"  ✅ {ref}  [verified in: {src_list}]")
    
    return "\n".join(lines)


def build_context(chunks: list[dict]) -> str:
    """
    Builds a citation-ready context block from retrieved chunks.
    Includes a VERIFIED CITATION REGISTRY and QUOTABLE SOURCE blocks.
    """
    if not chunks:
        return "No relevant documents found."
    
    base_url = "/api/documents/view"
    
    # ── Step 1: Build the Citation Registry ──────────────────
    registry = build_citation_registry(chunks)
    
    # ── Step 2: Build Quotable Source Blocks ─────────────────
    context_blocks = []
    for i, c in enumerate(chunks):
        raw_source = c.get('source', 'Unknown')
        filename = os.path.basename(raw_source)
        
        source_type = _classify_source(raw_source)
        authority_rank = _get_authority_rank(raw_source)
        
        safe_filename = filename.replace(" ", "%20")
        link = f"{base_url}?category=all&filename={safe_filename}"
        
        rerank_score = c.get('_rerank_score', None)
        relevance_tag = f" | Relevance: {rerank_score:.3f}" if rerank_score is not None else ""
        
        chunk_text = c['text'].strip()
        if len(chunk_text) > MAX_CHUNK_CHARS:
            chunk_text = chunk_text[:MAX_CHUNK_CHARS] + "... [truncated]"
        
        context_blocks.append(
            f"════════════════════════════════════════\n"
            f"SOURCE [{i+1}] | {authority_rank} | {source_type}\n"
            f"DOCUMENT: [{filename}]({link})\n"
            f"Page: {c.get('page', 'N/A')}{relevance_tag}\n"
            f"════════════════════════════════════════\n"
            f"[QUOTABLE TEXT — copy exactly as written below]\n"
            f"\"\"\"\n"
            f"{chunk_text}\n"
            f"\"\"\"\n"
            f"════════════════════════════════════════"
        )
    
    sources_section = "\n\n".join(context_blocks)
    
    # ── Step 3: Assemble Full Context ─────────────────────────
    full_context = (
        f"╔══════════════════════════════════════════╗\n"
        f"║   VERIFIED CITATION REGISTRY             ║\n"
        f"╚══════════════════════════════════════════╝\n"
        f"{registry}\n\n"
        f"╔══════════════════════════════════════════╗\n"
        f"║   RETRIEVED SOURCE DOCUMENTS             ║\n"
        f"╚══════════════════════════════════════════╝\n"
        f"{sources_section}"
    )
    
    if len(full_context) > MAX_CONTEXT_CHARS:
        full_context = full_context[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated to stay within token limits]"
    
    return full_context


def _path_segments(source_path: str) -> set:
    """Returns the set of lowercased path components for exact folder matching."""
    from pathlib import Path
    return {p.lower() for p in Path(source_path.replace("\\", "/")).parts}


def _classify_source(source_path: str) -> str:
    """Classify by folder name (path segment), not filename substring."""
    parts = _path_segments(source_path)
    if parts & {"act", "cgst", "igst", "utgst", "sgst"}:
        return "PRIMARY LAW (Act)"
    if parts & {"notification", "notifications"}:
        return "NOTIFICATION (Statutory)"
    if parts & {"circular", "circulars"}:
        return "CIRCULAR (CBIC)"
    if parts & {"rules", "rule"}:
        return "RULES"
    if parts & {"aar"}:
        return "ADVANCE RULING"
    if parts & {"high court case laws", "supreme court case laws"}:
        return "COURT JUDGMENT"
    if parts & {"icai"}:
        return "ICAI GUIDANCE"
    if parts & {"form", "forms"}:
        return "FORM"
    return "REFERENCE DOCUMENT"


def _get_authority_rank(source_path: str) -> str:
    """Rank by folder name (path segment), not filename substring."""
    parts = _path_segments(source_path)
    if parts & {"act", "cgst", "igst", "utgst", "sgst"}:
        return "RANK-1 (Act)"
    if parts & {"rules", "rule"}:
        return "RANK-2 (Rules)"
    if parts & {"notification", "notifications"}:
        return "RANK-3 (Notification)"
    if parts & {"circular", "circulars"}:
        return "RANK-4 (Circular)"
    if parts & {"aar", "high court case laws", "supreme court case laws"}:
        return "RANK-5 (Case Law/AAR)"
    if parts & {"icai"}:
        return "RANK-5 (ICAI)"
    return "RANK-6 (Reference)"