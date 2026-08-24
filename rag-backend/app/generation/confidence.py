"""
Confidence estimator — measures how well the RETRIEVED CONTEXT supports
an answer, NOT how verbose the answer itself is.

Signals (all measured against the context string passed in):
  1. Authoritative source types present (statute, notification, circular)
  2. Numeric specificity in the context (rates, rupee thresholds, time limits)
  3. Context density — a thin context can't support a confident answer
  4. Chunk coverage — how many distinct chunks back this query

Range: 0.0 – 1.0
  < 0.45 → safety.apply_safety_guards() refuses the answer
  < 0.70 → append uncertainty caveat
  ≥ 0.70 → full answer
"""
from __future__ import annotations

import re
from typing import List, Dict, Any, Optional


def estimate_confidence(context: str, chunks: Optional[List[Dict[str, Any]]] = None) -> float:
    """
    Estimate confidence from the *retrieved context string*, not the generated answer.

    Args:
        context: The assembled RAG context block passed to the LLM (not the answer).
        chunks:  The raw chunk list — used for coverage scoring.

    Returns:
        float in [0.0, 1.0]
    """
    if not context or len(context.strip()) < 80:
        return 0.35  # near-empty retrieval → low confidence

    score = 0.0
    ctx_lower = context.lower()

    # ── Signal 1: Statutory authority present in retrieved text ──────────────
    authority_score = 0.0
    if re.search(r'\bsection\s+\d+', ctx_lower):
        authority_score += 0.20   # Act section cited in source
    if "notification" in ctx_lower:
        authority_score += 0.10
    if "circular" in ctx_lower:
        authority_score += 0.08
    if "rule" in ctx_lower and re.search(r'\brule\s+\d+', ctx_lower):
        authority_score += 0.07
    score += min(authority_score, 0.35)

    # ── Signal 2: Numeric specificity (rates, rupees, periods) ───────────────
    rates_found   = len(re.findall(r'\d+(?:\.\d+)?%', context))
    rupees_found  = len(re.findall(r'rs\.?\s*[\d,]+', ctx_lower))
    days_found    = len(re.findall(r'\d+\s*(?:days?|months?|years?)', ctx_lower))
    numeric_hits  = rates_found + rupees_found + days_found
    score += min(numeric_hits * 0.04, 0.20)  # capped at 0.20

    # ── Signal 3: Context density (more text = more evidence) ────────────────
    word_count = len(context.split())
    if word_count >= 800:
        score += 0.25
    elif word_count >= 400:
        score += 0.18
    elif word_count >= 150:
        score += 0.10
    else:
        score += 0.04

    # ── Signal 4: Chunk coverage ─────────────────────────────────────────────
    if chunks:
        n = len(chunks)
        if n >= 6:
            score += 0.20
        elif n >= 3:
            score += 0.12
        elif n >= 1:
            score += 0.05

    return round(min(score, 1.0), 3)
