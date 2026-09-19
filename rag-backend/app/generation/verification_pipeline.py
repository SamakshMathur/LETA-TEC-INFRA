"""
Post-generation verification pipeline.

Runs all accuracy checks on the generated answer in parallel before it is
saved and shown to the user.  Previously these were 4 ad-hoc async closures
defined inline inside ``stream_and_save`` — pulling them here means there is
one place to reason about "what does LETA TEC check before showing an answer",
add new checks, adjust timeouts, or disable a pass.

Checks (run concurrently with a shared 12-second ceiling):
  1. CitationValidator   — cross-checks cited [Sn] sections against retrieved chunks
  2. HallucinationGuard — flags ungrounded numeric claims (rate/rupee figures)
  3. AuthorityVerifier   — verifies every mandatory authority predicted by the
                           query taxonomy was actually cited (1ms, no LLM call)
  4. AnswerVerifier      — LLM second-pass (Haiku) for logical consistency;
                           emits a visible warning to the user if a contradiction
                           is found (e.g., cites Sec 17(5) but says ITC allowed)
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
    gate_verdict: str = "PASS"               # PASS | REPAIR | BLOCK
    is_verified: bool = True
    unsupported_citations: list[str] = field(default_factory=list)
    safe_fallback_answer: str = ""
    evidence_ledger: list[dict[str, Any]] = field(default_factory=list)


def build_citations_block(answer: str, marker_map: list[dict] | None) -> str:
    """
    Build the streamed __CITATIONS__:...__END_CITATIONS__ frame from the
    (Sn) markers actually present in the answer.
    """
    if not marker_map:
        return ""
    try:
        from app.generation.context_builder import parse_markers
        citation_result = parse_markers(answer, marker_map)
        if not citation_result:
            return ""
        import json as _json
        return f"__CITATIONS__:{_json.dumps(citation_result)}__END_CITATIONS__"
    except Exception as exc:
        logger.debug(f"[VERIFY] Citation marker parse failed (non-fatal): {exc}")
        return ""


def verify_substantive_claim_support(
    claim_text: str,
    s_refs: list[Any],
    avail_refs: list[Any],
    sn_chunk_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Verify claim-to-evidence binding for an individual statement or bullet:
    1. Statute Match: Ensure that the cited (S#) chunk's statute matches the claim's asserted statute.
       (e.g., claiming CGST Act while citing an IGST Act chunk).
    2. Rule Identity: Ensure rules are attributed to their correct parent statute (e.g. Rule 96 is CGST Rules).
    3. Marker Laundering Prevention: Verify that cited authorities in the claim are substantively
       supported by the specific (S#) chunk(s) referenced. Attaching a valid marker (S1) to an ungrounded
       provision (e.g. Section 73 when S1 is Section 17) must fail.
    4. Direct vs Cross-Reference Verification: If an authority appears in evidence only as an
       incidental statutory cross-reference, verify that the claim does not assert substantive operational
       rules without primary direct evidence.
    5. Contradiction & Unrestricted Entitlement Check: Detect assertions of unrestricted entitlement
       or credit availability when statutory evidence denies or blocks credit.
    """
    import re as _re
    from app.retrieval.reference_resolver import ReferenceResolver

    claim_lower = claim_text.lower()
    markers = _re.findall(r'[\(\[]S(\d+)[\)\]]', claim_text)
    issues: list[str] = []
    statute_match = True

    # Inspect cited markers and their specific chunks
    marker_chunks = []
    for m in markers:
        chunk = sn_chunk_map.get(f"S{m}")
        if chunk:
            marker_chunks.append((m, chunk))

    # Determine default statute from cited markers if any
    marker_default_statute = None
    if marker_chunks:
        has_igst_chunk = any(
            "igst" in (c.get("rel_path") or (c.get("metadata") or {}).get("rel_path") or c.get("source") or "").lower()
            for _, c in marker_chunks
        )
        has_cgst_chunk = any(
            "cgst" in (c.get("rel_path") or (c.get("metadata") or {}).get("rel_path") or c.get("source") or "").lower()
            for _, c in marker_chunks
        )
        if has_igst_chunk and not has_cgst_chunk:
            marker_default_statute = "IGST"
        elif has_cgst_chunk and not has_igst_chunk:
            marker_default_statute = "CGST"

    # If s_refs wasn't passed or is empty, resolve references from the claim
    claim_refs = s_refs or ReferenceResolver.resolve_references(claim_text, default_statute=marker_default_statute)

    for m, chunk in marker_chunks:
        rel = (chunk.get("rel_path") or (chunk.get("metadata") or {}).get("rel_path") or chunk.get("source") or "").lower()
        chunk_text = (chunk.get("text") or chunk.get("content") or "").lower()

        is_chunk_igst = "igst" in rel or "integrated goods" in rel or "integrated" in rel
        is_chunk_cgst = "cgst" in rel or "central goods" in rel

        # Check statute mismatch in claim
        if ("cgst act" in claim_lower or "central goods and services tax act" in claim_lower) and is_chunk_igst and not is_chunk_cgst:
            issues.append(f"STATUTE_MISMATCH: Claim asserts CGST Act while citing (S{m}) which is IGST Act")
            statute_match = False
        elif ("igst act" in claim_lower or "integrated goods and services tax act" in claim_lower) and is_chunk_cgst and not is_chunk_igst:
            issues.append(f"STATUTE_MISMATCH: Claim asserts IGST Act while citing (S{m}) which is CGST Act")
            statute_match = False

        if "igst rules" in claim_lower and "rule 96" in claim_lower:
            issues.append("STATUTE_MISMATCH: Rule 96 belongs to CGST Rules, not IGST Rules")
            statute_match = False

        # Contradiction and Unrestricted Entitlement Check
        asserts_allowed = any(p in claim_lower for p in ["itc is allowed", "itc is available", "itc can be claimed", "credit is allowed", "credit is available", "eligible for itc"])
        asserts_denied_in_source = any(p in chunk_text for p in ["input tax credit shall not be available", "shall not be entitled to take credit", "blocked credit"])
        if asserts_allowed and asserts_denied_in_source:
            if not any(exc in claim_lower for exc in ["except", "unless", "subject to", "provided that", "other than"]):
                issues.append(f"CONTRADICTION: Claim asserts credit allowed but (S{m}) source text specifies credit is not available")

        asserts_unrestricted = any(p in claim_lower for p in [
            "unrestricted entitlement",
            "unconditional right",
            "unlimited credit",
            "always eligible without restriction",
            "entitled to full itc without restriction",
            "all construction expenses",
        ])
        if asserts_unrestricted and asserts_denied_in_source:
            issues.append(f"UNSUPPORTED_PROPOSITION: Claim asserts unrestricted entitlement contrary to statutory restrictions in (S{m})")

    # Marker Laundering Prevention
    if marker_chunks and claim_refs:
        marker_avails = [
            ReferenceResolver.extract_available_chunk_references([c])
            for _, c in marker_chunks
        ]
        for r in claim_refs:
            if r.ref_type in ("SCHEDULE", "CASE_LAW") or not r.provision_num:
                continue
            is_supported_by_any = any(
                ReferenceResolver.verify_citation_against_evidence(r, m_avail)[0]
                for m_avail in marker_avails
            )
            if not is_supported_by_any:
                issues.append(
                    f"MARKER_LAUNDERING: Claim asserts {r.display_name} citing ({', '.join(f'S{m}' for m in markers)}), but none of the cited markers contain this authority"
                )
                statute_match = False

    # Cross-Reference vs Direct Authority Verification
    operational_keywords = ["due date", "interest rate", "file within", "mandatory penalty", "late fee", "detailed procedure"]
    for r in claim_refs:
        if r.ref_type == "SECTION" and any(k in claim_lower for k in operational_keywords):
            has_direct_primary = False
            for c in (list(sn_chunk_map.values()) if sn_chunk_map else []):
                meta = c.get("metadata") or {}
                pks = meta.get("provision_keys") or []
                sec_lbl = (meta.get("section_label") or "").lower()
                if f"SEC_{r.provision_num}" in "".join(pks) or f"section {r.provision_num.lower()}" in sec_lbl:
                    has_direct_primary = True
                    break
            if not has_direct_primary and marker_chunks:
                issues.append(f"CROSS_REFERENCE_NOT_DIRECT: Substantive operational rules asserted for {r.display_name} without direct primary chunk evidence")

    is_supported = (len(issues) == 0) and statute_match

    # If claim has references not supported in overall available refs
    if claim_refs and avail_refs and not marker_chunks:
        for r in claim_refs:
            supported, _ = ReferenceResolver.verify_citation_against_evidence(r, avail_refs)
            if not supported:
                is_supported = False
                issues.append(f"UNSUPPORTED_AUTHORITY: {r.display_name} has no evidentiary support in retrieved chunks")

    return {
        "claim_text": claim_text,
        "markers": [f"(S{m})" for m in markers],
        "statute_match": statute_match,
        "supported": is_supported,
        "issues": issues,
    }


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
    Run all post-generation accuracy checks concurrently and enforce the Final Answer Gate.

    Args:
        answer:          Full generated answer text.
        query:           Original user query.
        chunks:          Retrieved chunks (from supplement_and_rerank).
        context:         Citation block sent to the LLM (for hallucination guard).
        truth_rules_text: Current truth rules text (for hallucination guard).
        marker_map:      [Sn] → chunk mapping for structured citation resolution.
        is_draft:        Skip verifiers on advisory/drafting answers.

    Returns:
        VerificationResult with gate_verdict and all check outputs.
    """
    if not answer.strip() or not chunks:
        return VerificationResult(verified_answer=answer, gate_verdict="PASS", is_verified=True)

    # ── 1. Citation audit (Canonical Reference Verification) ─────────────────
    from app.generation.citation_validator import CitationValidator, CitationValidationReport
    citation_report: CitationValidationReport = CitationValidator.audit_citations(answer, chunks)

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

    # ── Run async checks in parallel ──────────────────────────────────────────
    try:
        hallu_warn, _, verifier_warn = await asyncio.wait_for(
            asyncio.gather(
                _hallucination_guard(),
                _authority_verifier(),
                _answer_verifier(),
            ),
            timeout=_VERIFY_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("[VERIFY] Post-generation pipeline timed out")
        hallu_warn, verifier_warn = "", None

    if hallu_warn:
        logger.warning(f"[VERIFY] HallucinationGuard: {hallu_warn[:300]}")
    if verifier_warn:
        logger.warning(f"[VERIFY] AnswerVerifier flagged: {verifier_warn[:200]}")

    # ── 5. Citation block (structured [Sn] → doc resolution) ─────────────────
    citations_block = build_citations_block(answer, marker_map)

    # ── 6. Substantive Claim Support & Evidence Ledger ───────────────────────
    sn_chunk_map = {f"S{i+1}": chunks[i] for i in range(len(chunks))} if chunks else {}
    from app.retrieval.reference_resolver import ReferenceResolver
    import re as _re

    avail_refs = ReferenceResolver.extract_available_chunk_references(chunks)
    query_default_statute = "IGST" if ("igst" in query.lower() and "cgst" not in query.lower()) else None
    requested_refs = ReferenceResolver.resolve_references(query, default_statute=query_default_statute)

    def _resolve_unit_refs(text: str) -> list[Any]:
        u_markers = _re.findall(r'[\(\[]S(\d+)[\)\]]', text)
        statute = query_default_statute
        if u_markers:
            m_chunks = [sn_chunk_map.get(f"S{m}") for m in u_markers if sn_chunk_map.get(f"S{m}")]
            has_igst = any("igst" in (c.get("rel_path") or (c.get("metadata") or {}).get("rel_path") or c.get("source") or "").lower() for c in m_chunks)
            has_cgst = any("cgst" in (c.get("rel_path") or (c.get("metadata") or {}).get("rel_path") or c.get("source") or "").lower() for c in m_chunks)
            if has_igst and not has_cgst:
                statute = "IGST"
            elif has_cgst and not has_igst:
                statute = "CGST"
        return ReferenceResolver.resolve_references(text, default_statute=statute)

    # Decompose answer into claim units (bullets vs paragraph sentences)
    evidence_ledger: list[dict[str, Any]] = []
    lines = answer.split("\n")
    claim_units: list[tuple[str, str]] = []

    cur_para: list[str] = []
    sent_split_re = _re.compile(r'(?:(?<=[!?])|(?<!\bNo)(?<!\bno)(?<!\bSec)(?<!\bsec)(?<!\bLtd)(?<!\bPvt)\.)\s+')
    def _flush_para(p_lines: list[str]):
        if not p_lines:
            return
        full_p = " ".join(p_lines).strip()
        if full_p:
            sents = sent_split_re.split(full_p)
            for s in sents:
                s_clean = s.strip()
                if s_clean:
                    claim_units.append(("sentence", s_clean))

    for line in lines:
        line_s = line.strip()
        if not line_s:
            _flush_para(cur_para)
            cur_para = []
            claim_units.append(("blank", ""))
        elif line_s.startswith(("•", "-", "*")) or _re.match(r'^\d+\.\s+', line_s):
            _flush_para(cur_para)
            cur_para = []
            claim_units.append(("bullet", line_s))
        else:
            cur_para.append(line_s)
    _flush_para(cur_para)

    has_substantive_issues = False
    for utype, utext in claim_units:
        if utype == "blank" or not utext:
            continue
        u_refs = _resolve_unit_refs(utext)
        chk = verify_substantive_claim_support(utext, u_refs, avail_refs, sn_chunk_map)
        if not chk["supported"]:
            has_substantive_issues = True
        evidence_ledger.append({
            "claim": utext,
            "unit_type": utype,
            "markers": chk["markers"],
            "statute_match": chk["statute_match"],
            "supported": chk["supported"],
            "issues": chk["issues"],
            "references": [r.display_name for r in u_refs],
        })

    # ── 7. Final Answer Gate Decision (PASS | REPAIR | BLOCK) ────────────────
    gate_verdict = "PASS"
    is_verified = True
    safe_fallback = ""
    final_text = answer

    needs_remediation = (not citation_report.is_valid and bool(citation_report.unsupported_citations)) or has_substantive_issues

    if needs_remediation:
        primary_supported = (
            all(
                ReferenceResolver.verify_citation_against_evidence(req, avail_refs)[0]
                for req in requested_refs
                if req.ref_type in ("SECTION", "RULE", "CIRCULAR", "NOTIFICATION", "CASE_LAW")
            )
            if requested_refs else bool(avail_refs)
        )

        repaired = False
        if primary_supported:
            repaired_lines: list[str] = []
            for utype, utext in claim_units:
                if utype == "blank":
                    repaired_lines.append("")
                    continue
                u_refs = _resolve_unit_refs(utext)
                has_unsupported = any(
                    not ReferenceResolver.verify_citation_against_evidence(sr, avail_refs)[0]
                    for sr in u_refs
                )
                chk = verify_substantive_claim_support(utext, u_refs, avail_refs, sn_chunk_map)

                if not has_unsupported and chk["supported"]:
                    repaired_lines.append(utext)
                else:
                    has_primary = (
                        any(
                            any(sr.canonical_key == req.canonical_key or sr.is_exact_or_child_of(req) for req in requested_refs)
                            for sr in u_refs
                        )
                        if requested_refs else False
                    )
                    if not has_primary:
                        continue
                    else:
                        cleaned_unit = utext
                        for sr in u_refs:
                            if not ReferenceResolver.verify_citation_against_evidence(sr, avail_refs)[0]:
                                if sr.raw_text and sr.raw_text in cleaned_unit:
                                    cleaned_unit = cleaned_unit.replace(sr.raw_text, "").strip()
                        cleaned_refs = _resolve_unit_refs(cleaned_unit)
                        if cleaned_unit and verify_substantive_claim_support(cleaned_unit, cleaned_refs, avail_refs, sn_chunk_map)["supported"]:
                            repaired_lines.append(cleaned_unit)

            candidate_text = "\n".join(repaired_lines).strip()
            candidate_text = _re.sub(r'\n{3,}', '\n\n', candidate_text)

            if candidate_text:
                reaudit = CitationValidator.audit_citations(candidate_text, chunks)
                candidate_refs = ReferenceResolver.resolve_references(candidate_text, default_statute=query_default_statute)
                still_has_requested = (
                    all(
                        any(cr.canonical_key == req.canonical_key or cr.is_exact_or_child_of(req) for cr in candidate_refs)
                        for req in requested_refs
                    )
                    if requested_refs else (len(reaudit.verified_citations) > 0)
                )

                candidate_issues = any(
                    not verify_substantive_claim_support(unit, _resolve_unit_refs(unit), avail_refs, sn_chunk_map)["supported"]
                    for unit in repaired_lines if unit.strip()
                )

                if reaudit.is_valid and still_has_requested and not candidate_issues:
                    gate_verdict = "REPAIR"
                    is_verified = True
                    final_text = candidate_text
                    repaired = True

        if not repaired:
            gate_verdict = "BLOCK"
            is_verified = False
            unsupported_items = list(dict.fromkeys(
                citation_report.unsupported_citations
                + [iss for item in evidence_ledger for iss in item.get("issues", [])]
            ))
            unsupported_str = ", ".join(unsupported_items[:5])
            safe_fallback = (
                f"\n\n⚠ **LETA TEC Legal Integrity Notice:** The requested legal authority or claim "
                f"(`{unsupported_str}`) could not be verified in the retrieved official statutory records. "
                f"To uphold sovereign accuracy, unverified statements have been withheld.\n\n"
                f"Please verify the citation or query the specific statutory provision directly."
            )
            final_text = safe_fallback

    return VerificationResult(
        verified_answer=final_text,
        hallu_warning=hallu_warn or "",
        verifier_warning=verifier_warn,
        citations_block=citations_block if gate_verdict != "BLOCK" else "",
        gate_verdict=gate_verdict,
        is_verified=is_verified,
        unsupported_citations=citation_report.unsupported_citations,
        safe_fallback_answer=safe_fallback,
        evidence_ledger=evidence_ledger,
    )
