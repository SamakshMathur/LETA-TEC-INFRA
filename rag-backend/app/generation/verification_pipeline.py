"""
Post-generation verification pipeline.

Runs all accuracy checks on the generated answer in parallel before it is
saved and shown to the user.  Previously these were 4 ad-hoc async closures
defined inline inside ``stream_and_save`` — pulling them here means there is
one place to reason about "what does LETA check before showing an answer",
add new checks, adjust timeouts, or disable a pass.

Checks (run concurrently with a shared 12-second ceiling):
  1. CitationValidator   — cross-checks cited [Sn] sections against retrieved chunks
  2. HallucinationGuard — flags ungrounded numeric claims (rate/rupee figures)
  3. AuthorityVerifier   — verifies every mandatory authority predicted by the
                           query taxonomy was actually cited (1ms, no LLM call)
  4. AnswerVerifier      — LLM second-pass (Haiku) for logical consistency;
                           emits a visible warning to the user if a contradiction
                           is found (e.g., cites Sec 17(5) but says ITC allowed)

Usage::

    from app.generation.verification_pipeline import run_verification_pipeline

    result = await run_verification_pipeline(
        answer=full_answer,
        query=user_query,
        chunks=chunks,
        context=citation_block,
        truth_rules_text=truth_rules_text,
        marker_map=_marker_map,
        is_draft=_is_draft,
    )
    # result.verified_answer  — citation-validated answer text
    # result.hallu_warning    — non-empty if numeric hallucination detected
    # result.verifier_warning — non-empty if logical contradiction detected
    # result.citations_block  — structured __CITATIONS__:...  payload string (or "")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_VERIFY_TIMEOUT = 12.0   # seconds — generous for AnswerVerifier's Haiku call


@dataclass
class VerificationResult:
    verified_answer: str = ""
    hallu_warning: str = ""
    verifier_warning: str | None = None
    citations_block: str = ""


async def run_verification_pipeline(
    *,
    answer: str,
    query: str,
    chunks: list[dict[str, Any]],
    context: str,
    truth_rules_text: str,
    marker_map: list[dict] | None,
    is_draft: bool,
) -> VerificationResult:
    """
    Run all post-generation accuracy checks concurrently.

    Args:
        answer:          Full generated answer text.
        query:           Original user query.
        chunks:          Retrieved chunks (from supplement_and_rerank).
        context:         Citation block sent to the LLM (for hallucination guard).
        truth_rules_text: Current truth rules text (for hallucination guard).
        marker_map:      [Sn] → chunk mapping for structured citation resolution.
        is_draft:        Skip verifiers on advisory/drafting answers (they work
                         differently and the verifiers produce false positives on
                         procedural / narrative content).

    Returns:
        VerificationResult with all check outputs.
    """
    if not answer.strip() or not chunks:
        # Nothing to verify — return answer unchanged
        return VerificationResult(verified_answer=answer)

    # ── 1. Citation validator ─────────────────────────────────────────────────
    async def _citation_validator() -> str:
        try:
            from app.generation.citation_validator import CitationValidator
            return CitationValidator.validate_citations(answer, chunks)
        except Exception as exc:
            logger.warning(f"[VERIFY] CitationValidator failed (non-fatal): {exc}")
            return answer   # fall back to original

    # ── 2. Hallucination guard ────────────────────────────────────────────────
    async def _hallucination_guard() -> str:
        try:
            from app.generation.hallucination_guard import check_hallucinated_numbers
            _sn_map = (
                {f"S{i+1}": (chunks[i].get("text") or "") for i in range(len(chunks))}
                if chunks else None
            )
            return check_hallucinated_numbers(
                answer, context, truth_rules_text, chunks,
                sn_text_map=_sn_map,
            )
        except Exception as exc:
            logger.warning(f"[VERIFY] HallucinationGuard failed (non-fatal): {exc}")
            return ""

    # ── 3. Authority verifier (1ms, no LLM call) ─────────────────────────────
    async def _authority_verifier() -> None:
        try:
            from app.dependencies import get_retriever
            from app.retrieval.query_refiner import verify_answer_authority_coverage
            ret = get_retriever()
            tax = getattr(ret, "_last_taxonomy", {})
            cov = getattr(ret, "_last_coverage", {})
            if tax.get("confidence", 0) > 0 and (tax.get("sections") or tax.get("circulars")):
                av = verify_answer_authority_coverage(query, answer, tax, cov)
                if av["verdict"] != "pass":
                    logger.warning(
                        f"[AUTHORITY_VERIFY] verdict={av['verdict']} | "
                        f"topics={tax.get('topics')} | "
                        f"cited={av['cited']} | missing={av['missing']} | "
                        f"note={av['note']}"
                    )
        except Exception as exc:
            logger.warning(f"[VERIFY] AuthorityVerifier failed (non-fatal): {exc}")
        return None

    # ── 4. Answer verifier (LLM Haiku, ~2-5s) — skip on drafts ──────────────
    async def _answer_verifier() -> str | None:
        if is_draft:
            return None
        try:
            from app.generation.answer_verifier import verify_answer
            return await asyncio.to_thread(verify_answer, query, answer, chunks)
        except Exception as exc:
            logger.warning(f"[VERIFY] AnswerVerifier failed (non-fatal): {exc}")
            return None

    # ── Run all checks in parallel ────────────────────────────────────────────
    try:
        validated_answer, hallu_warn, _, verifier_warn = await asyncio.wait_for(
            asyncio.gather(
                _citation_validator(),
                _hallucination_guard(),
                _authority_verifier(),
                _answer_verifier(),
            ),
            timeout=_VERIFY_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("[VERIFY] Post-generation pipeline timed out — returning answer unchanged")
        return VerificationResult(verified_answer=answer)

    if hallu_warn:
        logger.warning(f"[VERIFY] HallucinationGuard: {hallu_warn[:300]}")
    if verifier_warn:
        logger.warning(f"[VERIFY] AnswerVerifier flagged: {verifier_warn[:200]}")

    # ── 5. Citation block (structured [Sn] → doc resolution) ─────────────────
    citations_block = ""
    if marker_map:
        try:
            from app.generation.context_builder import parse_markers
            citation_result = parse_markers(answer, marker_map)
            if citation_result:
                import json as _json
                citations_block = (
                    f"__CITATIONS__:{_json.dumps({'citations': citation_result})}__END_CITATIONS__"
                )
        except Exception as exc:
            logger.debug(f"[VERIFY] Citation marker parse failed (non-fatal): {exc}")

    return VerificationResult(
        verified_answer=validated_answer or answer,
        hallu_warning=hallu_warn or "",
        verifier_warning=verifier_warn,
        citations_block=citations_block,
    )
