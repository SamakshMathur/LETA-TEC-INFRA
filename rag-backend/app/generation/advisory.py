"""
Legal Advisory Generator — generates formal Legal Advisory Opinion from
retrieved statutory context and user-supplied facts.

Timeout architecture:
  - Anthropic client: 120s hard read timeout, 10s connect timeout
  - ALB idle timeout: 60s (bytes must flow; blocking calls must finish < 60s)
  - For the /generate endpoint (non-streaming): single Sonnet call, max_tokens=4000,
    typically 20-35s — within the 60s window.
  - Self-correction retry REMOVED: it doubled latency (second full Sonnet call) and
    was firing on almost every query due to over-aggressive keyword validators.
    Contradiction detection is now handled by answer_verifier.py (Phase 1).
"""
import os
import hashlib
import logging
from diskcache import Cache
from app.config import (
    ANTHROPIC_API_KEY,
    LLM_PROVIDER,
    CLAUDE_MAIN_MODEL,
    CACHE_DIR,
    DATA_DIR,
    PROMPT_VERSION,
)
from app.generation.prompts.advisory_prompt import ADVISORY_SYSTEM_PROMPT
from app.generation.pdf_report import PDFReportGenerator

logger = logging.getLogger(__name__)

# ── Cache + PDF ───────────────────────────────────────────────────────────────
cache      = Cache(CACHE_DIR)
REPORTS_DIR = os.path.join(DATA_DIR, "generated_reports")
pdf_gen    = PDFReportGenerator(output_dir=REPORTS_DIR)

# ── Anthropic client — created once, has explicit timeouts ───────────────────
_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    from app.utils.anthropic_client import get_anthropic_client, TIMEOUT_SYNTHESIS
    _client = get_anthropic_client(timeout=TIMEOUT_SYNTHESIS, connect=10.0)
    return _client


def _build_user_message(user_input: str, context: str) -> str:
    trimmed = context[:6000] if len(context) > 6000 else context
    return (
        "RETRIEVED STATUTORY CONTEXT (cite ONLY directly relevant provisions from here):\n"
        f"{trimmed}\n\n"
        "══════════════════════════════════════════════════════\n"
        "CLIENT'S QUERY — INCLUDING THEIR FACTUAL UNDERSTANDING:\n"
        "══════════════════════════════════════════════════════\n"
        f"{user_input}\n\n"
        "══════════════════════════════════════════════════════\n"
        "Produce ONLY section b) — 'Our comments from GST perspective:'\n"
        "• One bullet per distinct GST issue, in logical sequence.\n"
        "• Address every issue completely and correctly — do not truncate.\n"
        "• Drop every sentence that does not carry a legal point.\n"
        "• Use a markdown table where a comparison or eligibility matrix is clearer than prose.\n"
        "• End with a ready-to-use draft GST/tax clause or compliance checklist.\n"
        "• Do NOT re-state the facts — the client already wrote section (a).\n"
        "• Cite only provisions directly on point — no tangential padding."
    )


def generate_legal_advisory(user_input: str, context: str, subject: str = "GST Query") -> dict:
    """
    Generate a formal Legal Advisory Opinion.

    Single Sonnet call (max_tokens=4000, ~20-35s).
    Result is cached by (user_input[:200] + context[:100]) hash.

    Returns: {"content": str, "pdf_url": str | None, "cached": bool}
    """
    # ── Cache check ───────────────────────────────────────────────────────────
    query_hash = hashlib.md5((user_input + context[:100]).encode()).hexdigest()
    cache_key  = f"advisory_{PROMPT_VERSION}_{query_hash}"

    if cache_key in cache:
        logger.info(f"Advisory cache hit: {cache_key}")
        return cache[cache_key]

    try:
        from app.generation.rules_engine import rules_engine
        rules_text   = rules_engine.get_all_rules_as_text()
        system_prompt = ADVISORY_SYSTEM_PROMPT.format(rules_context=rules_text)
        user_message  = _build_user_message(user_input, context)

        # ── Single LLM call ───────────────────────────────────────────────────
        # max_tokens=4000 gives a thorough multi-issue advisory in ~20-35s —
        # within the 60s ALB idle timeout window.
        # Self-correction retry removed: it doubled latency without a reliable
        # quality gain, and answer_verifier.py now catches contradictions.
        client = _get_client()
        logger.info(f"Calling {CLAUDE_MAIN_MODEL} for advisory (max_tokens=4000)...")
        response = client.messages.create(
            model=CLAUDE_MAIN_MODEL,
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        advisory_content = response.content[0].text.strip()
        logger.info(f"Advisory generated: {len(advisory_content)} chars")

        # ── PDF ───────────────────────────────────────────────────────────────
        pdf_url = None
        try:
            filename = f"Advisory_{query_hash[:8]}.pdf"
            pdf_gen.generate_report(advisory_content, filename=filename)
            pdf_url = f"/api/documents/view?category=reports&filename={filename}"
        except Exception as pdf_err:
            logger.warning(f"PDF generation failed (non-fatal): {pdf_err}")

        result = {
            "content":  advisory_content,
            "pdf_url":  pdf_url,
            "cached":   False,
        }

        # ── Cache store ───────────────────────────────────────────────────────
        if advisory_content and len(advisory_content) > 100:
            cache[cache_key] = {**result, "cached": True}

        return result

    except Exception as e:
        logger.error(f"Advisory generation failed: {e}", exc_info=True)
        return {
            "content": f"## Error Generating Advisory\n\nWe encountered an issue: {str(e)}",
            "pdf_url": None,
            "cached":  False,
        }
