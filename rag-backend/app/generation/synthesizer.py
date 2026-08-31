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
    # Answer evaluation
    ANSWER_LLM_PROVIDER, ANSWER_LLM_MODEL,
)
from app.generation.prompt import SYSTEM_PROMPT, BRIEF_PROMPT, STANDARD_PROMPT, DRAFTING_PROMPT
from app.generation.rules_engine import rules_engine
import contextvars

input_tokens_var = contextvars.ContextVar("input_tokens", default=None)
output_tokens_var = contextvars.ContextVar("output_tokens", default=None)

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
    detailed (>= STANDARD_RESPONSE_THRESHOLD)→ prose, 700–1200 words, ~3500 tokens
    """
    if complexity < BRIEF_RESPONSE_THRESHOLD:
        return "brief", BRIEF_PROMPT, 800
    elif complexity < STANDARD_RESPONSE_THRESHOLD:
        return "standard", STANDARD_PROMPT, 2000
    else:
        return "detailed", SYSTEM_PROMPT, 3500


# ─────────────────────────────────────────────────────────────────────────────
# Client initialisation
# ─────────────────────────────────────────────────────────────────────────────

import app.generation.clients as _clients


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
    model_override: str = None,
    usage_tracker: dict = None,
):
    """
    3-tier model routing:
      use_haiku=True                          → Haiku, no thinking  (simple factual, ~9x cheaper)
      use_haiku=False, use_thinking=False     → Sonnet, no thinking  (standard analysis)
      use_haiku=False, use_thinking=True      → Sonnet + extended thinking  (complex drafting)

    Only visible text deltas are yielded; thinking tokens stay internal.
    """
    model = model_override if model_override else (CLAUDE_UTILITY_MODEL if use_haiku else CLAUDE_MAIN_MODEL)

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
        thinking_budget = max(1024, min(CLAUDE_THINKING_BUDGET, resolved_max_tokens))
        stream_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget,
        }
        # Anthropic's max_tokens parameter must be strictly greater than budget_tokens.
        # Set it to thinking_budget + resolved_max_tokens.
        # This keeps the output tokens budget (visible text) strictly bounded by resolved_max_tokens.
        stream_kwargs["max_tokens"] = thinking_budget + resolved_max_tokens
        logger.info(f"Claude thinking configured: budget={thinking_budget} | max_tokens={stream_kwargs['max_tokens']}")

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
            client = _clients.get_claude_client()
            with client.messages.stream(**stream_kwargs) as stream:
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

            try:
                final_msg = stream.get_final_message()
                if final_msg and getattr(final_msg, "usage", None):
                    input_tokens_var.set(final_msg.usage.input_tokens)
                    output_tokens_var.set(final_msg.usage.output_tokens)
                    if usage_tracker is not None:
                        usage_tracker["input_tokens"] = final_msg.usage.input_tokens
                        usage_tracker["output_tokens"] = final_msg.usage.output_tokens
            except Exception as ue:
                logger.warning(f"Failed to retrieve final token usage from stream: {ue}")

            # Fallback token estimation if not set
            if input_tokens_var.get() is None:
                input_tokens_var.set((len(system_prompt) + len(question)) // 4)
            if output_tokens_var.get() is None:
                output_tokens_var.set(len(full_content) // 4)
            if usage_tracker is not None:
                if usage_tracker.get("input_tokens") is None:
                    usage_tracker["input_tokens"] = input_tokens_var.get()
                if usage_tracker.get("output_tokens") is None:
                    usage_tracker["output_tokens"] = output_tokens_var.get()

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
                yield from _stream_claude(question, system_prompt, use_haiku=True, usage_tracker=usage_tracker)
            else:
                yield "Error generating answer. Please try again."
            return


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI-Compatible streaming generator (shared helper)
# ─────────────────────────────────────────────────────────────────────────────

def _stream_openai_compatible(client, question: str, system_prompt: str, response_mode: str = "detailed", model_override: str = None, usage_tracker: dict = None):
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

    model_to_use = model_override if model_override else (ANSWER_LLM_MODEL if ANSWER_LLM_MODEL else LLM_MODEL)

    api_params = {
        "model": model_to_use,
        "messages": messages,
        "max_completion_tokens": 3000,
        "stream": True,
        "stop": ["[TERMINATE]"],
        "stream_options": {"include_usage": True},
    }

    if "o1" not in model_to_use.lower() and "gpt-5" not in model_to_use.lower():
        api_params["temperature"] = 0.0
        api_params["extra_body"] = {
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

    full_content = ""
    try:
        response_stream = client.chat.completions.create(**api_params)
        for chunk in response_stream:
            if hasattr(chunk, "usage") and chunk.usage:
                try:
                    input_tokens_var.set(chunk.usage.prompt_tokens)
                    output_tokens_var.set(chunk.usage.completion_tokens)
                    if usage_tracker is not None:
                        usage_tracker["input_tokens"] = chunk.usage.prompt_tokens
                        usage_tracker["output_tokens"] = chunk.usage.completion_tokens
                except Exception:
                    pass
            if chunk.choices:
                content = chunk.choices[0].delta.content
                if content:
                    if full_content.count("[POINT") > MAX_RESPONSE_POINTS:
                        break
                    full_content += content
                    yield content

        logger.debug(f"OpenAI-compatible stream complete | chars={len(full_content)}")

    except Exception as e:
        logger.error(f"OpenAI-compatible stream error: {e}", exc_info=True)
        # Raise explicit error for A/B testing instead of silent recovery
        raise RuntimeError(f"OpenAI-compatible generation error: {str(e)}")

    finally:
        # Fallback token estimation if usage wasn't received in the stream
        if input_tokens_var.get() is None:
            input_tokens_var.set(len(system_prompt + question) // 4)
        if output_tokens_var.get() is None:
            output_tokens_var.set(len(full_content) // 4)
        if usage_tracker is not None:
            if usage_tracker.get("input_tokens") is None:
                usage_tracker["input_tokens"] = input_tokens_var.get()
            if usage_tracker.get("output_tokens") is None:
                usage_tracker["output_tokens"] = output_tokens_var.get()


def _stream_openai(question: str, system_prompt: str, response_mode: str = "detailed", model_override: str = None, usage_tracker: dict = None):
    try:
        client = _clients.get_openai_client()
    except Exception as e:
        logger.error(f"OpenAI routing failed: {e}")
        # Return a clear provider configuration error as requested
        yield f"\n[Provider Configuration Error: {str(e)}]"
        return
    yield from _stream_openai_compatible(client, question, system_prompt, response_mode, model_override, usage_tracker=usage_tracker)


def _stream_ollama(question: str, system_prompt: str, response_mode: str = "detailed", model_override: str = None, usage_tracker: dict = None):
    try:
        client = _clients.get_ollama_client()
    except Exception as e:
        logger.error(f"Ollama routing failed: {e}")
        yield f"\n[Provider Configuration Error: {str(e)}]"
        return
    yield from _stream_openai_compatible(client, question, system_prompt, response_mode, model_override, usage_tracker=usage_tracker)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_answer_stream(
    question: str,
    context: str,
    session_is_draft: bool = False,
    force_haiku: bool = False,
    provider: str = None,
    model: str = None,
    usage_tracker: dict = None,
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
    # Definition/explanation queries MUST bypass DRAFTING_PROMPT even if session history
    # has draft signals. A query like "define X" or "provide definition of X" has no
    # missing facts and should never trigger the CHECK-3 clarification flow.
    import re as _re
    _NEVER_DRAFT_PATTERNS = [
        r'\b(what\s+is|what\s+are|define|definition\s+of|explain|meaning\s+of)\b',
        r'\b(provide|give|state|share)\s+(the\s+)?(definition|meaning|explanation|rate|provision)',
        r'\b(relevant\s+circular|applicable\s+circular|circular\s+on)\b',
        r'\b(full\s+form|abbreviation)\b',
    ]
    _is_never_draft = any(_re.search(p, question.lower()) for p in _NEVER_DRAFT_PATTERNS)

    # Route as draft only when: current or session has draft signals, AND query is not
    # a pure definition/knowledge query.
    is_draft = (not _is_never_draft) and (
        session_is_draft or any(kw in question.lower() for kw in _DRAFT_KW)
    )

    mode_name = None
    if is_draft:
        prompt_template = DRAFTING_PROMPT
        use_haiku = force_haiku  # allow override even for draft in sync mode
        use_thinking = False  # Thinking disabled — DRAFTING_PROMPT is self-sufficient; all tokens go to output
        max_tokens = 4000 if force_haiku else 5000
    else:
        mode_name, prompt_template, max_tokens = _select_response_mode(complexity)
        use_haiku = force_haiku or (complexity < HAIKU_COMPLEXITY_THRESHOLD)
        use_thinking = (not use_haiku) and (complexity >= SONNET_THINKING_THRESHOLD)
        if force_haiku:
            max_tokens = min(max_tokens, 2200)

    # Determine intent instruction for prompt steering
    intent_instruction = ""
    if is_draft:
        intent_instruction = "\n\n[INTENT]\nGenerate a complete, high-quality, professional draft notice reply or representation. Maintain rigor and statutory anchors, but avoid duplication, unnecessary circularity, or verbose phrasing. Keep the generation focused and concise."
    else:
        if mode_name == "brief":
            intent_instruction = "\n\n[INTENT]\nProvide a short, direct, factual answer. Keep it within 150-250 words. Do not include detailed explanations or non-essential background."
        elif mode_name == "standard":
            intent_instruction = "\n\n[INTENT]\nProvide a standard legal analysis. Keep it within 300-500 words. Balance detail with conciseness."
        else:
            intent_instruction = "\n\n[INTENT]\nProvide a detailed legal opinion. Walk through all provisions and arguments clearly, but keep it within 700-1000 words. Avoid repetition."

    truth_rules_text = rules_engine.get_all_rules_as_text()
    system_prompt = prompt_template.format(context=context, truth_rules=truth_rules_text) + intent_instruction

    # Scoped target provider and model overrides (Fix 4)
    active_provider = provider if provider else ANSWER_LLM_PROVIDER
    if active_provider == "claude":
        active_provider = "anthropic"

    active_model = model if model else ANSWER_LLM_MODEL

    model_name = "unknown"
    if active_provider == "anthropic":
        if active_model:
            model_name = active_model
        else:
            model_name = CLAUDE_UTILITY_MODEL if use_haiku else CLAUDE_MAIN_MODEL
    else:
        model_name = active_model if active_model else LLM_MODEL

    from app.ai_logger import update_ai_log
    update_ai_log(
        model_used=model_name,
        draft_type="draft" if is_draft else None,
        estimated_prompt_tokens=(len(system_prompt) + len(question)) // 4
    )

    if active_provider == "anthropic":
        logger.info(
            f"Routing to Claude: model={model_name} | complexity={complexity:.2f} | draft={is_draft} | "
            f"haiku={use_haiku} | thinking={use_thinking}"
        )
        yield from _stream_claude(
            question=question,
            system_prompt=system_prompt,
            use_haiku=use_haiku,
            use_thinking=use_thinking,
            max_tokens_override=max_tokens,
            is_draft=is_draft,
            model_override=model_name,
            usage_tracker=usage_tracker,
        )
    elif active_provider == "openai":
        logger.info(
            f"Routing to OpenAI: model={model_name} | complexity={complexity:.2f} | draft={is_draft}"
        )
        yield from _stream_openai(
            question=question,
            system_prompt=system_prompt,
            response_mode="draft" if is_draft else "detailed",
            model_override=model_name,
            usage_tracker=usage_tracker,
        )
    elif active_provider == "ollama":
        logger.info(
            f"Routing to Ollama: model={model_name} | complexity={complexity:.2f} | draft={is_draft}"
        )
        yield from _stream_ollama(
            question=question,
            system_prompt=system_prompt,
            response_mode="draft" if is_draft else "detailed",
            model_override=model_name,
            usage_tracker=usage_tracker,
        )
    else:
        logger.error(f"Unsupported provider specified: {active_provider}")
        yield f"\n[System Error: Unsupported provider {active_provider}]"


def synthesize_answer(question: str, context: str, provider: str = None, model: str = None) -> str:
    """
    Public API: Synchronous answer generation wrapper.
    """
    chunks = []
    for chunk in synthesize_answer_stream(question, context, provider=provider, model=model):
        chunks.append(chunk)
    return "".join(chunks)
