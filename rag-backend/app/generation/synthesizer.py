import logging
from app.config import (
    LLM_PROVIDER,
    # OpenAI / Ollama
    OPENAI_API_KEY, OLLAMA_API_KEY, LLM_MODEL,
    # Claude
    ANTHROPIC_API_KEY, CLAUDE_MAIN_MODEL, CLAUDE_UTILITY_MODEL,
    CLAUDE_THINKING_BUDGET, CLAUDE_MAX_TOKENS, MAX_RESPONSE_POINTS,
    HAIKU_COMPLEXITY_THRESHOLD,
    BRIEF_RESPONSE_THRESHOLD, STANDARD_RESPONSE_THRESHOLD, SONNET_THINKING_THRESHOLD,
)
from app.generation.prompt import SYSTEM_PROMPT, BRIEF_PROMPT, STANDARD_PROMPT, DRAFTING_PROMPT
from app.generation.rules_engine import rules_engine

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Complexity scorer — decides Haiku vs Sonnet without an LLM call
# ─────────────────────────────────────────────────────────────────────────────

# Keywords that signal a complex multi-section legal analysis
_COMPLEX_SIGNALS = {
    "section", "rule", "notification", "circular", "itc", "input tax credit",
    "appeal", "penalty", "prosecution", "tribunal", "high court", "supreme court",
    "composite", "mixed supply", "place of supply", "time of supply", "reverse charge",
    "gstr", "annual return", "audit", "assessment", "demand", "adjudication",
    "fema", "company law", "income tax", "tds", "tcs", "capital gains",
    "export", "import", "customs", "sez", "e-way bill", "refund",
    "draft", "notice", "reply", "advisory", "legal draft", "observation", "written submission",
    "igst", "cgst", "sgst", "utgst", "intermediary", "zero rated", "export of service",
    "place of supply", "import of service", "cross border", "inter-state", "intra-state",
    "our understanding", "gst implications", "gst treatment", "tax position", "advise",
    "qualifying", "characterisation", "characterization", "section 2", "section 7", "section 9",
    "section 12", "section 13", "section 16", "section 17", "section 24", "section 74",
    "schedule ii", "schedule iii", "schedule i",
}

_SIMPLE_SIGNALS = {
    "what is", "define", "meaning of", "full form", "abbreviation",
    "rate of", "gst rate", "hsn", "sac", "due date", "last date",
    "deadline", "turnover limit", "threshold", "registration limit",
}


def _estimate_complexity(question: str) -> float:
    """
    Returns a complexity score 0.0–1.0.
    < HAIKU_COMPLEXITY_THRESHOLD  → route to Haiku (fast, cheap)
    >= HAIKU_COMPLEXITY_THRESHOLD → route to Sonnet (full power)
    """
    q_lower = question.lower()
    word_count = len(q_lower.split())

    complex_hits = sum(1 for kw in _COMPLEX_SIGNALS if kw in q_lower)
    simple_hits  = sum(1 for kw in _SIMPLE_SIGNALS  if kw in q_lower)

    # Base score from keyword signals - ITC and Drafting have higher weight
    base_weight = 0.18
    if "itc" in q_lower or "input tax credit" in q_lower:
        base_weight = 0.35
    if any(k in q_lower for k in ["draft", "notice", "reply", "scn", "show cause", "drc-01", "drc 01", "asmt-10", "appeal letter", "representation"]):
        base_weight = 0.35
    if any(k in q_lower for k in ["igst", "cgst", "intermediary", "place of supply", "zero rated", "export of service", "our understanding", "gst implications", "characteris"]):
        base_weight = max(base_weight, 0.28)

    score = min(1.0, complex_hits * base_weight) - min(0.3, simple_hits * 0.15)

    # Long questions are generally more complex
    if word_count > 40:
        score += 0.25
    elif word_count > 20:
        score += 0.15
    elif word_count > 10:
        score += 0.05

    # Multiple legal sections cited → definitely complex
    import re
    if len(re.findall(r'\bsec(?:tion)?\s*\d+', q_lower)) > 1:
        score += 0.3

    return max(0.0, min(1.0, score))


def _count_tokens_approx(text: str) -> int:
    """Rough token count: ~4 chars per token (good enough for budget gating)."""
    return len(text) // 4


def _select_response_mode(complexity: float) -> tuple:
    """
    Maps complexity score to (mode_name, prompt_template, max_tokens).

    brief    (< BRIEF_RESPONSE_THRESHOLD)    → prose, 150–300 words,  ~800 tokens
    standard (< STANDARD_RESPONSE_THRESHOLD) → prose, 400–700 words,  ~2000 tokens
    detailed (>= STANDARD_RESPONSE_THRESHOLD)→ prose, 700–1200 words, ~4000 tokens
    """
    if complexity < BRIEF_RESPONSE_THRESHOLD:
        return "brief", BRIEF_PROMPT, 900
    elif complexity < STANDARD_RESPONSE_THRESHOLD:
        return "standard", STANDARD_PROMPT, 2200
    else:
        return "detailed", SYSTEM_PROMPT, 3500


# ─────────────────────────────────────────────────────────────────────────────
# Client initialisation
# ─────────────────────────────────────────────────────────────────────────────

_claude_client = None
_oai_client = None

if LLM_PROVIDER == "anthropic":
    import anthropic as _anthropic
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not found — answer generation will fail")
    _claude_client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info(f"LLM Provider: Anthropic Claude ({CLAUDE_MAIN_MODEL}) with extended thinking")

elif LLM_PROVIDER == "ollama":
    import openai as _openai
    _oai_client = _openai.OpenAI(
        api_key=OLLAMA_API_KEY if OLLAMA_API_KEY else "ollama",
        base_url=f"http://localhost:11434/v1",
    )
    logger.info(f"LLM Provider: Local Ollama ({LLM_MODEL})")

else:  # openai
    import openai as _openai
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not found — answer generation will fail")
    _oai_client = _openai.OpenAI(api_key=OPENAI_API_KEY)
    logger.info(f"LLM Provider: OpenAI ({LLM_MODEL})")


# ─────────────────────────────────────────────────────────────────────────────
# One-shot example (provider-agnostic content)
# ─────────────────────────────────────────────────────────────────────────────

_ONESHOT_USER = "What is the GST on cars?"
_ONESHOT_ASSISTANT = (
    "<thinking>Analyzing Sec 17(5) for motor vehicles — checking ITC block conditions.</thinking>\n\n"
    "[POINT 1/7] **QUERY INTERPRETATION & KEY LEGAL ISSUE**: GST rate and ITC eligibility for motor vehicle purchase.\n"
    "[POINT 2/7] **CONCLUSIVE ANSWER (EXECUTIVE SUMMARY)**: GST is 28% + cess. ITC is blocked under Section 17(5)(a) for vehicles with seating ≤ 13.\n"
    "[POINT 3/7] **RELEVANT LEGAL PROVISIONS**: Section 17(5)(a) of the CGST Act 2017 — denies ITC on motor vehicles used for transportation of persons (seating ≤ 13), unless used for taxable onward supply.\n"
    "[POINT 4/7] **VERBATIM STATUTORY EXTRACTS**: \"Input tax credit shall not be available in respect of... "
    "motor vehicles for transportation of persons having approved seating capacity of not more than thirteen persons...\"\n"
    "[POINT 5/7] **LEGAL ANALYSIS, ADVERSARIAL CHECK & APPLICABLE NOTIFICATIONS**: ITC block applies unless the vehicle is used for (i) further supply of vehicles, (ii) transportation of passengers, or (iii) imparting training on driving. Circular 177/09/2022 clarifies no ITC on demo vehicles. No notification overrides Sec 17(5) for general purchase.\n"
    "[POINT 6/7] **NUMERIC DATA / RATES (TRUTH RULES ONLY)**: GST Rate: **28%** + applicable cess. ITC block threshold: seating capacity **≤ 13 persons**.\n"
    "[POINT 7/7] **FINAL TAX POSITION & CAVEATS**: **FINAL POSITION:** Taxable at 28% + cess. ITC Blocked under Sec 17(5)(a). Verify current cess rates from latest CBIC notification.\n"
    "[TERMINATE]"
)

_COT_INSTRUCTION = """
CRITICAL INSTRUCTION - INTERNAL REASONING:
Before generating your mandatory structured response, you MUST output a <thinking> block.
Inside this <thinking> block, you must:
1. **Factual Mapping**: Extract all relevant entities, dates, and intent.
2. **Statutory Anchoring**: Identify exact sections (e.g., Sec 16, Sec 17) and prioritize TRUTH RULES.
3. **Adversarial Check**: Actively search for reasons why the benefit/credit might be DENIED
   (e.g., Section 17(5), Section 12/13 time limits).
4. **Numerical Checklist**: List every rate, threshold, and time limit found in TRUTH RULES/Context.
5. **Supply Type**: Determine if the supply is Composite or Mixed.

After closing the </thinking> block, immediately begin the LETA_OUTPUT_V2.0 response.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Claude (Anthropic) streaming generator
# ─────────────────────────────────────────────────────────────────────────────

def _stream_claude(
    question: str,
    system_prompt: str,
    use_haiku: bool = False,
    use_thinking: bool = False,
    max_tokens_override: int = None,
    is_draft: bool = False,
):
    """
    3-tier model routing:
      use_haiku=True                          → Haiku, no thinking  (simple factual, ~9x cheaper)
      use_haiku=False, use_thinking=False     → Sonnet, no thinking  (standard analysis)
      use_haiku=False, use_thinking=True      → Sonnet + extended thinking  (complex drafting)

    Only visible text deltas are yielded; thinking tokens stay internal.
    """
    model = CLAUDE_UTILITY_MODEL if use_haiku else CLAUDE_MAIN_MODEL

    messages = [{"role": "user", "content": question}]

    # Anthropic prompt caching: pass system prompt as a content block with
    # cache_control so Anthropic caches it server-side.
    # Cache reads cost $0.30/MTok vs $3.00/MTok uncached — ~90% cheaper on
    # the system prompt + legal context (typically 70% of input tokens).
    # Split system prompt into two blocks so Anthropic can cache the static part.
    # All prompt templates use this exact separator before the dynamic context.
    # Block 1 (with cache_control) — instructions only, same every call → CACHED
    # Block 2 (no cache_control)   — retrieved chunks + truth rules → NOT cached
    _SEP = "\n-------------------------------------------------------\nRETRIEVED SOURCE DOCUMENTS\n-------------------------------------------------------\n"
    if _SEP in system_prompt:
        static_part, dynamic_part = system_prompt.split(_SEP, 1)
        system_blocks = [
            {
                "type": "text",
                "text": static_part,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": _SEP + dynamic_part,
            },
        ]
    else:
        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    resolved_max_tokens = max_tokens_override if max_tokens_override is not None else (
        4000 if use_haiku else CLAUDE_MAX_TOKENS
    )
    # Anthropic requires temperature=1 when extended thinking is enabled.
    # For regular (non-thinking) calls, temperature=0 produces more precise
    # and consistent legal answers, which is critical for a compliance tool.
    stream_kwargs = dict(
        model=model,
        max_tokens=resolved_max_tokens,
        system=system_blocks,
        messages=messages,
        stop_sequences=["[TERMINATE]"],
        temperature=1 if use_thinking else 0,
    )

    # Extended thinking: Sonnet only, and only when complexity warrants it
    if not use_haiku and use_thinking:
        stream_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": CLAUDE_THINKING_BUDGET,
        }
        # Anthropic requirement: max_tokens must be strictly greater than thinking budget
        if stream_kwargs["max_tokens"] <= CLAUDE_THINKING_BUDGET:
            stream_kwargs["max_tokens"] = CLAUDE_THINKING_BUDGET + 4000

    def _is_retryable(exc: Exception) -> bool:
        return type(exc).__name__ in {
            "APIConnectionError", "RateLimitError",
            "InternalServerError", "APITimeoutError",
        }

    full_content = ""
    max_attempts = 3
    for attempt in range(max_attempts):
        full_content = ""
        try:
            with _claude_client.messages.stream(**stream_kwargs) as stream:
                for event in stream:
                    try:
                        if (
                            getattr(event, "type", None) == "content_block_delta"
                            and getattr(getattr(event, "delta", None), "type", "") == "text_delta"
                        ):
                            text = event.delta.text
                            if text:
                                if not is_draft and full_content.count("[POINT") > MAX_RESPONSE_POINTS:
                                    break
                                full_content += text
                                yield text
                    except (AttributeError, TypeError):
                        continue

            logger.info(
                f"Claude stream complete | model={'haiku' if use_haiku else 'sonnet'} "
                f"| thinking={use_thinking} | attempt={attempt + 1} | chars={len(full_content)}"
            )
            return  # success — exit generator

        except Exception as e:
            if attempt < max_attempts - 1 and _is_retryable(e):
                wait = 2 ** attempt
                logger.warning(
                    f"Claude transient error (attempt {attempt + 1}/{max_attempts}), "
                    f"retrying in {wait}s: {e}"
                )
                import time as _time
                _time.sleep(wait)
                continue

            logger.error(f"Claude stream error: {e}", exc_info=True)
            if not use_haiku:
                logger.warning("Attempting emergency fallback to Haiku...")
                yield "\n[System: Falling back to fast-drafting mode...]\n\n"
                yield from _stream_claude(question, system_prompt, use_haiku=True)
            else:
                yield "Error generating answer. Please try again."
            return


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI / Ollama streaming generator (kept as fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _stream_openai(question: str, system_prompt: str, response_mode: str = "detailed"):
    if response_mode == "draft":
        messages = [{"role": "user", "content": question}]
    elif response_mode == "detailed":
        messages = [
            {"role": "system",    "content": system_prompt + "\n\n" + _COT_INSTRUCTION},
            {"role": "user",      "content": _ONESHOT_USER},
            {"role": "assistant", "content": _ONESHOT_ASSISTANT},
            {"role": "user",      "content": question},
        ]
    else:
        messages = [{"role": "user", "content": question}]

    api_params = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_completion_tokens": 3000,
        "stream": True,
        "stop": ["[TERMINATE]"],
    }

    if "o1" not in LLM_MODEL.lower() and "gpt-5" not in LLM_MODEL.lower():
        api_params["temperature"] = 0.0
        api_params["extra_body"] = {
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

    full_content = ""
    try:
        response_stream = _oai_client.chat.completions.create(**api_params)
        for chunk in response_stream:
            content = chunk.choices[0].delta.content
            if content:
                if full_content.count("[POINT") > MAX_RESPONSE_POINTS:
                    break
                full_content += content
                yield content

        logger.debug(f"OpenAI stream complete | chars={len(full_content)}")

    except Exception as e:
        logger.error(f"OpenAI stream error: {e}", exc_info=True)
        yield f"Error generating answer: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_answer_stream(
    question: str,
    context: str,
    session_is_draft: bool = False,
    force_haiku: bool = False,
):
    """
    Public API: Generates a streaming answer.
    Decides between Anthropic and OpenAI based on configuration,
    handles complexity/mode estimation, formats prompts and streams chunks.

    session_is_draft: set True when session history indicates an ongoing
    draft/advisory conversation, so follow-up messages (corrections, re-analysis
    requests) keep routing through DRAFTING_PROMPT even if the follow-up text
    alone doesn't contain draft keywords.

    force_haiku: force Haiku model regardless of complexity (used by /ask-sync
    to stay within API Gateway's 29-second integration timeout).
    """
    complexity = _estimate_complexity(question)
    # Keywords that route through DRAFTING_PROMPT (notices, drafts, and advisory opinions)
    _DRAFT_KW = [
        # Notice / SCN / demand drafting
        "draft", "notice", "reply", "appeal", "submission",
        "scn", "show cause", "drc-01", "drc 01", "asmt-10", "asmt 10",
        "drc-07", "drc 07", "drc-03", "drc 03",
        "write a letter", "write letter", "prepare reply", "prepare a reply",
        "letter to", "representation", "response to notice", "respond to",
        # Advisory / legal opinion triggers
        "advisory", "our understanding", "gst implications", "gst implication",
        "provide opinion", "provide advisory", "our comments", "tax position",
        "gst treatment of", "gst on this transaction", "advise on",
        "what would be the gst", "legal opinion", "our client is",
        "we are engaged in", "facts of the case",
    ]
    # Route as draft if: current message has draft keywords OR session history does
    is_draft = session_is_draft or any(kw in question.lower() for kw in _DRAFT_KW)

    if is_draft:
        prompt_template = DRAFTING_PROMPT
        use_haiku = force_haiku  # allow override even for draft in sync mode
        use_thinking = False  # Thinking disabled — DRAFTING_PROMPT is self-sufficient; all tokens go to output
        max_tokens = 4000 if force_haiku else 16000
    else:
        mode_name, prompt_template, max_tokens = _select_response_mode(complexity)
        use_haiku = force_haiku or (complexity < HAIKU_COMPLEXITY_THRESHOLD)
        use_thinking = (not use_haiku) and (complexity >= SONNET_THINKING_THRESHOLD)
        if force_haiku:
            max_tokens = min(max_tokens, 2200)

    truth_rules_text = rules_engine.get_all_rules_as_text()
    system_prompt = prompt_template.format(context=context, truth_rules=truth_rules_text)

    if LLM_PROVIDER == "anthropic":
        logger.info(
            f"Routing to Claude: complexity={complexity:.2f} | draft={is_draft} | "
            f"haiku={use_haiku} | thinking={use_thinking}"
        )
        yield from _stream_claude(
            question=question,
            system_prompt=system_prompt,
            use_haiku=use_haiku,
            use_thinking=use_thinking,
            max_tokens_override=max_tokens,
            is_draft=is_draft,
        )
    else:
        logger.info(
            f"Routing to OpenAI/Ollama: model={LLM_MODEL} | complexity={complexity:.2f} | draft={is_draft}"
        )
        yield from _stream_openai(
            question=question,
            system_prompt=system_prompt,
            response_mode="draft" if is_draft else "detailed",
        )


def synthesize_answer(question: str, context: str) -> str:
    """
    Public API: Synchronous answer generation wrapper.
    """
    chunks = []
    for chunk in synthesize_answer_stream(question, context):
        chunks.append(chunk)
    return "".join(chunks)
