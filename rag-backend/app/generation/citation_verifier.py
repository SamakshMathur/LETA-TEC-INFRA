"""
Citation Verifier — Post-generation accuracy layer.

After GPT-4o generates an answer, this module:
1. Extracts all legal citations from the generated text
2. Checks each one against the actual retrieved source chunks
3. Appends a CITATION VERIFICATION REPORT at the end of the answer

This prevents hallucinated citations from being served to the user.
"""
import re
from typing import List, Dict


# ─────────────────────────────────────────────────────────────
# Citation Pattern Extractors
# ─────────────────────────────────────────────────────────────

CITATION_PATTERNS = [
    # Section references: "Section 9(3)", "Sec. 17(5)", "s. 22"
    (r'\bSection\s+\d+[\(\w\)]*', 'Section'),
    (r'\bSec\.\s*\d+[\(\w\)]*', 'Section'),
    
    # Notification references: "Notification No. 13/2017-CTR", "No. 52/2020"
    (r'\bNotification\s+No\.?\s*[\w\/\-]+', 'Notification'),
    (r'\bNotification\s+[\d]+\/[\d]+', 'Notification'),
    
    # Circular references: "Circular No. 27/01/2018", "Circular 199"
    (r'\bCircular\s+No\.?\s*[\w\/\-\.]+', 'Circular'),
    (r'\bCircular\s+\d+\/\d+', 'Circular'),
    
    # Rule references: "Rule 36(4)", "Rule 86B"
    (r'\bRule\s+\d+[\(\w\)]*', 'Rule'),
    
    # Article references: "Article 246A", "Article 366(12A)"
    (r'\bArticle\s+\d+[\(\w\)]*', 'Article'),
]


def extract_citations(text: str) -> List[Dict]:
    """Extract all legal citations from generated text."""
    found = []
    for pattern, ctype in CITATION_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean = match.strip()
            if clean not in [c['citation'] for c in found]:
                found.append({'citation': clean, 'type': ctype})
    return found


def _normalise(text: str) -> str:
    """Collapse whitespace and lowercase for consistent matching."""
    return re.sub(r'\s+', ' ', text).strip().lower()


def _build_search_variants(citation: str, ctype: str) -> List[str]:
    """
    Build a prioritised list of progressively-relaxed match strings for a citation.
    We try the most-specific form first and fall back gracefully.

    Examples
    --------
    "Section 17(5)(a)"  → ["section 17(5)(a)", "section 17(5)", "section 17"]
    "Rule 36(4)"        → ["rule 36(4)", "rule 36"]
    "Notification No. 13/2017-CTR" → ["notification no. 13/2017-ctr",
                                       "notification no. 13/2017",
                                       "13/2017-ctr", "13/2017"]
    "Circular No. 27/01/2018-GST"  → ["circular no. 27/01/2018-gst",
                                       "circular no. 27/01/2018",
                                       "circular 27/01/2018"]
    """
    raw = _normalise(citation)
    variants: List[str] = [raw]  # always try full string first

    if ctype in ('Section', 'Rule', 'Article'):
        # Strip sub-clauses progressively: "17(5)(a)" → "17(5)" → "17"
        keyword = raw.split()[0]          # "section" / "rule" / "article"
        number_part = raw[len(keyword):].strip()
        # Remove nested brackets one at a time
        while re.search(r'\([^()]*\)$', number_part):
            number_part = re.sub(r'\([^()]*\)$', '', number_part).strip()
            candidate = f"{keyword} {number_part}"
            if candidate not in variants:
                variants.append(candidate)

    elif ctype in ('Notification', 'Circular'):
        # Try without the suffix code (e.g. "-CTR", "-GST")
        no_suffix = re.sub(r'-[A-Z]+$', '', raw)
        if no_suffix != raw:
            variants.append(no_suffix)
        # Try just the number/date portion
        num_match = re.search(r'(\d+[\/\-]\d+)', raw)
        if num_match:
            variants.append(num_match.group(1))

    return variants


def verify_citations_against_chunks(citations: List[Dict], chunks: List[Dict]) -> List[Dict]:
    """
    Strict citation verification using full-string matching with progressive fallback.

    Strategy (in order):
    1. Exact full-citation match in source text (most strict).
    2. Progressive sub-clause stripping — "Section 17(5)(a)" → "Section 17(5)" → "Section 17".
    3. For Notifications/Circulars, try number-only match after stripping suffix codes.

    A citation is ONLY marked verified if at least one variant is found as a
    contiguous substring in the retrieved source chunks.  Bare number matching
    (e.g. checking if "17" appears anywhere) is intentionally removed to prevent
    false positives from dates, form numbers, or page numbers.
    """
    all_source_text = _normalise(" ".join([c.get('text', '') for c in chunks]))

    results = []
    for cit in citations:
        variants = _build_search_variants(cit['citation'], cit['type'])
        verified = False
        matched_variant = None

        for variant in variants:
            if variant in all_source_text:
                verified = True
                matched_variant = variant
                break

        results.append({
            'citation': cit['citation'],
            'type': cit['type'],
            'verified': verified,
            'matched_as': matched_variant,   # useful for debugging
        })

    return results


def build_verification_report(verification_results: List[Dict], chunks: List[Dict]) -> str:
    """Build a formatted citation verification footer."""
    if not verification_results:
        return ""
    
    verified = [v for v in verification_results if v['verified']]
    unverified = [v for v in verification_results if not v['verified']]
    
    total = len(verification_results)
    score = len(verified) / total if total > 0 else 0
    
    lines = [
        "\n\n---",
        "## 📋 CITATION VERIFICATION REPORT",
        f"**Score: {len(verified)}/{total} citations verified against retrieved sources**",
        ""
    ]
    
    if verified:
        lines.append("### ✅ Verified Citations (found in retrieved documents)")
        for v in verified:
            lines.append(f"- `{v['citation']}` ({v['type']})")
        lines.append("")
    
    if unverified:
        lines.append("### ⚠️ Unverified Citations (not found in retrieved source chunks)")
        lines.append("*These may be correct from general knowledge but could not be confirmed from the retrieved documents. Verify independently before relying on them.*")
        for v in unverified:
            lines.append(f"- `{v['citation']}` ({v['type']}) — ⚠️ Not confirmed in sources")
        lines.append("")
    
    # List source documents used
    source_names = list({c.get('source', '').split('\\')[-1].split('/')[-1] 
                          for c in chunks if c.get('source')})[:8]
    if source_names:
        lines.append("### 📚 Documents Retrieved for This Query")
        for s in source_names:
            lines.append(f"- {s}")
    
    return "\n".join(lines)


def verify_and_annotate(answer: str, chunks: List[Dict]) -> str:
    """
    Main entry point: takes the LLM answer + retrieved chunks,
    extracts citations, verifies them, and appends a report.
    """
    try:
        citations = extract_citations(answer)
        if not citations:
            # No citations found — add a note listing the sources used
            source_names = list({c.get('source', '').split('\\')[-1].split('/')[-1] 
                                  for c in chunks if c.get('source')})[:8]
            if source_names:
                report = "\n\n---\n## 📚 Sources Retrieved\n"
                report += "\n".join(f"- {s}" for s in source_names)
                return answer + report
            return answer
        
        verification_results = verify_citations_against_chunks(citations, chunks)
        report = build_verification_report(verification_results, chunks)
        return answer + report
        
    except Exception as e:
        print(f"Citation verifier error: {e}")
        return answer  # Fail silently — always return original answer
