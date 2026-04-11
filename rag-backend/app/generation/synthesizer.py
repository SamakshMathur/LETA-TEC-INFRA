import logging
from app.config import (
    LLM_PROVIDER,
    # OpenAI / Ollama
    OPENAI_API_KEY, OLLAMA_API_KEY, LLM_MODEL,
    # Claude
    ANTHROPIC_API_KEY, CLAUDE_MAIN_MODEL, CLAUDE_UTILITY_MODEL,
    CLAUDE_THINKING_BUDGET, MAX_RESPONSE_POINTS,
    MAX_INPUT_TOKENS, HAIKU_COMPLEXITY_THRESHOLD,
)
from app.generation.prompt import SYSTEM_PROMPT
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

    # Base score from keyword signals
    score = min(1.0, complex_hits * 0.15) - min(0.3, simple_hits * 0.15)

    # Long questions are generally more complex
    if word_count > 40:
        score += 0.2
    elif word_count > 20:
        score += 0.1

    # Multiple legal sections cited → definitely complex
    import re
    if len(re.findall(r'\bsec(?:tion)?\s*\d+', q_lower)) > 1:
        score += 0.3

    return max(0.0, min(1.0, score))


def _count_tokens_approx(text: str) -> int:
    """Rough token count: ~4 chars per token (good enough for budget gating)."""
    return len(text) // 4


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
    "<thinking>Analyzing Sec 17(5) for motor vehicles.</thinking>\n\n"
    "[POINT 1/10] **LETA INTERPRETATION OF USER QUERY**: Assessment of GST rate and ITC eligibility for motor vehicles.\n"
    "[POINT 2/10] **MAIN CONCLUSIVE ANSWER (EXECUTIVE SUMMARY)**: GST is generally 28% plus cess. ITC is blocked under Section 17(5).\n"
    "[POINT 3/10] **FACTUAL UNDERSTANDING / ASSUMPTIONS**: User is asking about standard motor vehicle purchase.\n"
    "[POINT 4/10] **RELEVANT LEGAL PROVISIONS**: Section 17(5)(a) of the CGST Act 2017.\n"
    "[POINT 5/10] **VERBATIM STATUTORY EXTRACTS**: \"Input tax credit shall not be available in respect of... "
    "motor vehicles for transportation of persons having approved seating capacity of not more than thirteen persons...\"\n"
    "[POINT 6/10] **LEGAL ANALYSIS & ADVERSARIAL CHECK**: ITC is blocked unless used for further supply, "
    "transportation of passengers, or training.\n"
    "[POINT 7/10] **APPLICATION TO PRESENT CASE**: If seating capacity <= 13, ITC is blocked.\n"
    "[POINT 8/10] **NUMERIC DATA / RATES (TRUTH RULES)**: Rate: **28%**. Thresholds: **N/A**.\n"
    "[POINT 9/10] **RELEVANT NOTIFICATIONS / CIRCULARS / PRECEDENTS**: Circular 177/08/2022.\n"
    "[POINT 10/10] **FINAL TAX POSITION & CAVEATS**: **FINAL POSITION:** ITC Blocked. Taxable at 28%.\n"
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

def _stream_claude(question: str, system_prompt: str, use_haiku: bool = False):
    """
    Streams the answer using Claude.

    use_haiku=False  → Sonnet with Extended Thinking (full legal analysis)
    use_haiku=True   → Haiku (simple factual queries, ~9x cheaper, no thinking)

    Only visible text deltas are yielded; thinking tokens stay internal.
    """
    model = CLAUDE_UTILITY_MODEL if use_haiku else CLAUDE_MAIN_MODEL
    messages = [
        {"role": "user",      "content": _ONESHOT_USER},
        {"role": "assistant", "content": _ONESHOT_ASSISTANT},
        {"role": "user",      "content": question},
    ]

    # Anthropic prompt caching: pass system prompt as a content block with
    # cache_control so Anthropic caches it server-side.
    # Cache reads cost $0.30/MTok vs $3.00/MTok uncached — ~90% cheaper on
    # the system prompt + legal context (typically 70% of input tokens).
    system_blocks = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    stream_kwargs = dict(
        model=model,
        max_tokens=4000 if use_haiku else 8000,
        system=system_blocks,
        messages=messages,
        stop_sequences=["[TERMINATE]"],
        temperature=1,
    )

    # Extended thinking only on Sonnet (Haiku doesn't support it)
    if not use_haiku:
        stream_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": CLAUDE_THINKING_BUDGET,
        }

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
                            if full_content.count("[POINT") > MAX_RESPONSE_POINTS:
                                break
                            full_content += text
                            yield text
                except (AttributeError, TypeError):
                    continue

        logger.info(
            f"Claude stream complete | model={'haiku' if use_haiku else 'sonnet'} "
            f"| chars={len(full_content)}"
        )

    except Exception as e:
        logger.error(f"Claude stream error: {e}", exc_info=True)
        yield f"Error generating answer: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI / Ollama streaming generator (kept as fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _stream_openai(question: str, system_prompt: str):
    messages = [
        {"role": "system",    "content": system_prompt + "\n\n" + _COT_INSTRUCTION},
        {"role": "user",      "content": _ONESHOT_USER},
        {"role": "assistant", "content": _ONESHOT_ASSISTANT},
        {"role": "user",      "content": question},
    ]

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

def synthesize_answer_stream(question: str, context: str):
    """
    Generates a streaming legal answer using the configured LLM provider.

    Routing logic (Anthropic only):
      - Estimates query complexity (0.0–1.0) without an LLM call
      - Simple queries (score < HAIKU_COMPLEXITY_THRESHOLD) → Haiku (~9x cheaper)
      - Complex queries → Sonnet with extended thinking (full accuracy)

    Token budget guard:
      - Rejects queries where estimated input tokens exceed MAX_INPUT_TOKENS
      - Prevents runaway API spend from adversarial or oversized inputs
    """
    if not question or not question.strip():
        logger.warning("synthesize_answer_stream called with empty question")
        yield "Error: No question provided."
        return

    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        yield "## Error: ANTHROPIC_API_KEY not configured."
        return
    if LLM_PROVIDER != "anthropic" and not OPENAI_API_KEY and not OLLAMA_API_KEY:
        yield "## Error: No LLM API Key configured."
        return

    try:
        truth_rules_text = rules_engine.get_all_rules_as_text()
        formatted_system_prompt = SYSTEM_PROMPT.format(
            context=context,
            truth_rules=truth_rules_text,
        )
    except KeyError as e:
        logger.error(f"System prompt template error — missing placeholder: {e}")
        yield f"Error: System prompt misconfigured (missing {e})"
        return

    # ── Token budget guard ────────────────────────────────────────────────────
    estimated_tokens = _count_tokens_approx(formatted_system_prompt + question)
    if estimated_tokens > MAX_INPUT_TOKENS:
        logger.warning(
            f"Token budget exceeded | estimated={estimated_tokens} | "
            f"limit={MAX_INPUT_TOKENS} | question={question[:80]}"
        )
        yield (
            "## Query Too Large\n"
            "Your query with the retrieved context exceeds the processing limit. "
            "Please narrow your question to a specific section or provision."
        )
        return

    if LLM_PROVIDER == "anthropic":
        # ── Haiku routing ─────────────────────────────────────────────────────
        complexity = _estimate_complexity(question)
        use_haiku = complexity < HAIKU_COMPLEXITY_THRESHOLD
        logger.info(
            f"synthesize | complexity={complexity:.2f} | "
            f"model={'haiku' if use_haiku else 'sonnet'} | q={question[:80]}"
        )
        yield from _stream_claude(question, formatted_system_prompt, use_haiku=use_haiku)
    else:
        logger.debug(f"synthesize_answer_stream | provider={LLM_PROVIDER} | question={question[:80]}")
        yield from _stream_openai(question, formatted_system_prompt)


def synthesize_answer(question: str, context: str) -> str:
    return "".join(synthesize_answer_stream(question, context))
