"""
Contextual Enrichment — Anthropic Contextual Retrieval
-------------------------------------------------------
For every chunk, Claude Haiku generates a 1-2 sentence context that situates
the chunk within its source document.  That context is prepended to the chunk
text before embedding so the vector captures *meaning*, not just keywords.

Reference: https://www.anthropic.com/news/contextual-retrieval
Tested impact on RAG: ~49% reduction in retrieval failures.

Usage (called by scripts/full_contextual_rebuild.py):
    from app.chunking.contextual_enricher import enrich_document_chunks
    enriched = enrich_document_chunks(doc_chunks, document_text, rel_path, doc_type)
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import anthropic

from app.config import ANTHROPIC_API_KEY, CLAUDE_UTILITY_MODEL

logger = logging.getLogger(__name__)

# ── Singleton Haiku client ────────────────────────────────────────────────────
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY,
            timeout=anthropic.Timeout(60.0, connect=10.0),
        )
    return _client


# ── Context generation prompt ─────────────────────────────────────────────────
_SYSTEM = (
    "You are a GST (Goods and Services Tax) legal document indexing assistant. "
    "Your job is to write precise, brief contextual descriptions that help a "
    "retrieval system find the right legal chunks for user queries."
)

_USER_TMPL = """\
Here is the GST legal document this chunk comes from:
<document>
{document}
</document>

Here is the specific chunk to situate within the document:
<chunk>
{chunk}
</chunk>

Write 1-2 sentences that situate this chunk in the document for search retrieval. Include:
- Document type (Circular / Notification / Section of Act / Rule / Case Law / FAQ / Response Template)
- Specific section, rule, or circular number if identifiable
- Core legal topic covered (e.g. ITC block under Section 17(5), RCM under Section 9(3))
- How this chunk relates to the broader document (clarifies, prescribes, establishes exception, etc.)

Output ONLY the context description. No preamble, no labels, no bullet points:"""


def _generate_context(
    document_text: str,
    chunk_text: str,
    max_retries: int = 3,
) -> str:
    """Call Haiku to generate a context description for one chunk."""
    prompt = _USER_TMPL.format(
        document=document_text[:7000],   # cap doc context to ~1750 tokens
        chunk=chunk_text[:1500],
    )
    for attempt in range(max_retries):
        try:
            response = _get_client().messages.create(
                model=CLAUDE_UTILITY_MODEL,
                max_tokens=120,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except anthropic.RateLimitError:
            wait = 2 ** (attempt + 2)   # 4s, 8s, 16s
            logger.warning(f"Rate limited — waiting {wait}s (attempt {attempt+1})")
            time.sleep(wait)
        except anthropic.APIError as e:
            logger.warning(f"API error on attempt {attempt+1}: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"Unexpected error: {e}")
            break
    return ""   # graceful degradation — chunk is still embedded without context


def enrich_document_chunks(
    chunks: list[dict],
    document_text: str,
    rel_path: str = "",
    max_workers: int = 8,
) -> list[dict]:
    """
    Add context to all chunks belonging to one document.

    Each chunk gets:
      chunk["context"]           — the Haiku-generated context string
      chunk["text_with_context"] — context + "\\n\\n" + original text (used for embedding)
      chunk["text"]              — original text (preserved for display / citations)

    Args:
        chunks       — list of chunk dicts from chunks.jsonl for ONE source file
        document_text — concatenated text of the whole document (all chunks joined)
        rel_path      — used only for logging
        max_workers   — parallel Haiku threads (keep ≤ 10 to respect rate limits)
    """
    if not chunks:
        return chunks

    results: dict[int, str] = {}

    def _task(idx_chunk):
        idx, chunk = idx_chunk
        ctx = _generate_context(document_text, chunk["text"])
        return idx, ctx

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_task, (i, c)): i for i, c in enumerate(chunks)}
        for future in as_completed(futures):
            try:
                idx, ctx = future.result()
                results[idx] = ctx
            except Exception as e:
                logger.error(f"Context future failed: {e}")
                results[futures[future]] = ""

    enriched = []
    for i, chunk in enumerate(chunks):
        ctx = results.get(i, "")
        ec = dict(chunk)
        ec["context"] = ctx
        ec["text_with_context"] = (f"{ctx}\n\n{chunk['text']}" if ctx else chunk["text"])
        enriched.append(ec)

    ok = sum(1 for c in enriched if c["context"])
    logger.debug(f"{rel_path}: {ok}/{len(enriched)} chunks contextualized")
    return enriched
