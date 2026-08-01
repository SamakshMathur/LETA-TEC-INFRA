import os
import re
from pathlib import Path

# Character caps — tuned for TITAN sub-5s target.
# Q&A mode: 15 000 chars. Draft mode: 30 000 chars (needed for 5000-word replies).
MAX_CONTEXT_CHARS_QA    = 18000   # was 15000 — circulars are dense, more context helps
MAX_CONTEXT_CHARS_DRAFT = 30000
MAX_CHUNK_CHARS_QA      = 1400   # was 1000 — prevents circulars being truncated mid-clause
MAX_CHUNK_CHARS_DRAFT   = 1800  # longer excerpts needed for verbatim statutory reproduction

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


_CASE_LAW_FOLDERS = {"high court case laws", "supreme court case laws", "aar", "other app result"}

# Patterns to extract case names from judgment text
_CASE_NAME_PATTERNS = [
    r'(?:M/s\.?\s+)?[\w\s\.\-&,\']+(?:\s+(?:Pvt\.?\s*Ltd\.?|Ltd\.?|LLP|Inc\.?|Corp\.?))?(?:\s+(?:[Vv]s?\.?|[Vv]ersus)\s+)[\w\s\.\-&,\']+(?:\s+(?:Pvt\.?\s*Ltd\.?|Ltd\.?|LLP))?',
]


def _extract_case_name_from_filename(filename: str) -> str:
    """
    Converts a case law filename to a readable case name.
    e.g. "Esveeaar+Distilleries+Private+Limited+Vs+AC+ST+-+APHC.pdf"
         → "Esveeaar Distilleries Private Limited Vs AC ST"
    """
    stem = Path(filename).stem
    # Replace URL-encoded + with space, then clean court suffix after last " - "
    name = stem.replace("+", " ").replace("_", " ")
    # Strip court abbreviation at end (e.g. " - APHC", " - GUJHC")
    name = re.sub(r'\s+-\s+[A-Z]{2,8}$', '', name)
    return name.strip()


def _is_case_law_source(source_path: str) -> bool:
    path = source_path.lower().replace("\\", "/")
    return any(f"/{f}/" in path or path.startswith(f + "/") for f in _CASE_LAW_FOLDERS)


def build_citation_registry(chunks: list[dict], is_draft: bool = False) -> str:
    """
    Pre-extracts ALL legal citations that appear in the retrieved chunks.
    For draft mode: also extracts case names from filenames so the LLM can
    cite them verbatim without hallucinating names.
    """
    all_refs = {}  # ref -> [source filenames]
    case_names = {}  # case_name -> court type

    for c in chunks:
        text = c.get('text', '')
        raw_source = c.get('source', '') or c.get('metadata', {}).get('source', '')
        rel_path = c.get('rel_path', '') or c.get('metadata', {}).get('rel_path', '')
        classify_path = rel_path if rel_path else raw_source
        source = os.path.basename(rel_path) if rel_path else (os.path.basename(raw_source) or 'Unknown')
        refs = _extract_legal_refs(text)
        for ref in refs:
            if ref not in all_refs:
                all_refs[ref] = []
            if source not in all_refs[ref]:
                all_refs[ref].append(source)

        # Phase 3: extract case names from filenames for case law sources
        if is_draft and _is_case_law_source(classify_path):
            case_name = _extract_case_name_from_filename(source)
            if case_name and len(case_name) > 10:
                path_lower = classify_path.lower()
                if "supreme court" in path_lower:
                    court = "Supreme Court of India"
                elif "high court" in path_lower:
                    court = "High Court"
                elif "aar" in path_lower:
                    court = "AAR"
                else:
                    court = "Appellate Authority"
                case_names[case_name] = court

    # Separate refs into circulars/notifications vs sections/rules
    circular_refs = {r: s for r, s in all_refs.items()
                     if re.search(r'(?i)(circular|notification|instruction|order)', r)}
    statutory_refs = {r: s for r, s in all_refs.items() if r not in circular_refs}

    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║  MANDATORY CITATION LIST — ALL ITEMS BELOW MUST APPEAR IN   ║",
        "║  YOUR DRAFT. Do NOT skip any. Do NOT add any not listed here.║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
    ]

    if statutory_refs:
        lines.append("── STATUTORY PROVISIONS (cite in BLOCK D, Step 3 — reproduce verbatim) ──")
        for ref, sources in sorted(statutory_refs.items()):
            src_list = ", ".join(sources[:2])
            lines.append(f"  📖 {ref}  [from: {src_list}]")
        lines.append("")

    if circular_refs:
        lines.append("── CIRCULARS / NOTIFICATIONS (cite in BLOCK E — reproduce verbatim extract) ──")
        for ref, sources in sorted(circular_refs.items()):
            src_list = ", ".join(sources[:2])
            lines.append(f"  📋 {ref}  [from: {src_list}]")
        lines.append("")

    if case_names:
        lines.append("── CASE LAWS (cite in BLOCK D Step 5 — use 'Reliance is placed on...' pattern) ──")
        for name, court in sorted(case_names.items()):
            lines.append(f"  ⚖️  {name}  [{court}] — reproduce verbatim extract from SOURCE DOCUMENTS below")
        lines.append("")

    if not all_refs and not case_names:
        return (
            "NO DOCUMENTS RETRIEVED from the vector database for this query.\n"
            "Use statutory provisions from TRUTH RULES only. Mark each argument:\n"
            "[No supporting case law retrieved — practitioner to verify from database]"
        )

    lines.append("INSTRUCTION: Every item above MUST appear in the draft letter with verbatim extract.")
    lines.append("Missing even one is a drafting failure. Use the SOURCE DOCUMENTS below to get the text.")
    return "\n".join(lines)


def build_context(chunks: list[dict], is_draft: bool = False) -> str:
    """
    Builds a citation-ready context block from retrieved chunks.
    Draft mode uses larger limits (30 000 chars, 1800 chars/chunk) and
    includes the case law name registry for hallucination grounding.
    """
    if not chunks:
        return "No relevant documents found."

    max_context = MAX_CONTEXT_CHARS_DRAFT if is_draft else MAX_CONTEXT_CHARS_QA
    max_chunk   = MAX_CHUNK_CHARS_DRAFT   if is_draft else MAX_CHUNK_CHARS_QA

    base_url = "/api/documents/view"

    # ── Step 1: Build the Citation Registry ──────────────────
    registry = build_citation_registry(chunks, is_draft=is_draft)

    # ── Step 2: Build Quotable Source Blocks ─────────────────
    context_blocks = []
    for i, c in enumerate(chunks):
        raw_source = c.get('source', '') or c.get('metadata', {}).get('source', 'Unknown')
        rel_path = c.get('rel_path', '') or c.get('metadata', {}).get('rel_path', '')
        # Use rel_path for the display filename — it holds the real file name.
        # Fall back to basename(raw_source) only when rel_path is absent.
        filename = os.path.basename(rel_path) if rel_path else (os.path.basename(raw_source) or 'Unknown')

        # For path classification use rel_path when available (it has folder info)
        classify_path = rel_path if rel_path else raw_source
        source_type = _classify_source(classify_path)
        authority_rank = _get_authority_rank(classify_path)

        safe_filename = filename.replace(" ", "%20")
        link = f"{base_url}?category=all&filename={safe_filename}"

        rerank_score = c.get('_rerank_score', None)
        relevance_tag = f" | Relevance: {rerank_score:.3f}" if rerank_score is not None else ""

        # Use context_text (enriched with adjacent-page neighbors) when available
        chunk_text = (c.get('context_text') or c['text']).strip()
        if len(chunk_text) > max_chunk:
            chunk_text = chunk_text[:max_chunk] + "... [truncated]"

        # Include DOCUMENT LINK in the source block so the LLM can output clickable links.
        # The frontend renders markdown hyperlinks; the model is instructed to use this URL.
        year_tag = ""
        doc_year = c.get("year") or c.get("metadata", {}).get("year")
        if doc_year:
            year_tag = f" | Year: {doc_year}"

        context_blocks.append(
            f"════════════════════════════════════════\n"
            f"SOURCE: «{filename}» | {authority_rank} | {source_type}{year_tag}\n"
            f"DOCUMENT LINK: {link}\n"
            f"Page: {c.get('page', 'N/A')}{relevance_tag}\n"
            f"════════════════════════════════════════\n"
            f"[QUOTABLE TEXT — cite «{filename}» verbatim and include its DOCUMENT LINK as [📄 View]({link})]\n"
            f"\"\"\"\n"
            f"{chunk_text}\n"
            f"\"\"\"\n"
            f"════════════════════════════════════════"
        )

    # ── Step 2.5: Interleave circulars AND notifications so they survive char-truncation ──
    # LegalReranker ranks Acts/Rules highest → without interleaving, all circular and
    # notification blocks appear at the end and get cut by the char budget.
    # Notifications are just as query-critical as circulars for rate/exemption questions.
    # Pattern: 2 primary-law blocks (Acts/Rules/Case law), then 1 secondary block
    #          (Circular or Notification, alternating), repeat.
    _secondary_blocks, _primary_blocks = [], []
    for _b, _c in zip(context_blocks, chunks):
        _rpath = (
            _c.get("rel_path") or _c.get("metadata", {}).get("rel_path", "") or _c.get("source", "")
        ).lower()
        if "circular" in _rpath or "notification" in _rpath:
            _secondary_blocks.append(_b)
        else:
            _primary_blocks.append(_b)

    ordered_blocks = []
    _oi, _ci = 0, 0
    while _oi < len(_primary_blocks) or _ci < len(_secondary_blocks):
        for _ in range(2):
            if _oi < len(_primary_blocks):
                ordered_blocks.append(_primary_blocks[_oi]); _oi += 1
        if _ci < len(_secondary_blocks):
            ordered_blocks.append(_secondary_blocks[_ci]); _ci += 1

    sources_section = "\n\n".join(ordered_blocks)

    # ── Step 3: Assemble Full Context ─────────────────────────
    _header = (
        f"╔══════════════════════════════════════════╗\n"
        f"║   VERIFIED CITATION REGISTRY             ║\n"
        f"╚══════════════════════════════════════════╝\n"
        f"{registry}\n\n"
        f"╔══════════════════════════════════════════╗\n"
        f"║   RETRIEVED SOURCE DOCUMENTS             ║\n"
        f"╚══════════════════════════════════════════╝\n"
    )
    full_context = _header + sources_section

    if len(full_context) > max_context:
        # Block-aware truncation: never cut mid-document.
        # Rebuild incrementally, adding whole source blocks until budget is exhausted.
        _kept = _header
        _sep = ""
        for _blk in ordered_blocks:
            _candidate = _kept + _sep + _blk
            if len(_candidate) > max_context:
                break
            _kept = _candidate
            _sep = "\n\n"
        full_context = _kept + "\n\n[Context truncated to stay within token limits]"

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