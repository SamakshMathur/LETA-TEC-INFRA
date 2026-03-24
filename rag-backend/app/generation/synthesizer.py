import logging
from app.config import (
    LLM_PROVIDER,
    # OpenAI / Ollama
    OPENAI_API_KEY, OLLAMA_API_KEY, LLM_MODEL,
    # Claude
    ANTHROPIC_API_KEY, CLAUDE_MAIN_MODEL, CLAUDE_THINKING_BUDGET,
)
from app.generation.prompt import SYSTEM_PROMPT
from app.generation.rules_engine import rules_engine

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Client initialisation
# ─────────────────────────────────────────────────────────────────────────────

if LLM_PROVIDER == "anthropic":
    import anthropic as _anthropic
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not found. Answer generation will fail.")
    _claude_client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info(f"LLM Provider: Anthropic Claude ({CLAUDE_MAIN_MODEL}) with extended thinking")

elif LLM_PROVIDER == "ollama":
    import openai as _openai
    _oai_client = _openai.OpenAI(
        api_key=OLLAMA_API_KEY if OLLAMA_API_KEY else "ollama",
        base_url="http://localhost:11434/v1",
    )
    logger.info(f"LLM Provider: Local Ollama ({LLM_MODEL})")

else:  # openai
    import openai as _openai
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not found. Answer generation will fail.")
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

def _stream_claude(question: str, system_prompt: str):
    """
    Streams the answer using Claude with Extended Thinking enabled.

    Extended Thinking means Claude performs genuine multi-step legal reasoning
    in hidden token space BEFORE writing the visible answer.  The <thinking>
    block in the system prompt becomes real hardware-level reasoning rather than
    simulated text — it will correctly catch adversarial cases (blocked ITC,
    provisos, time limits) before committing to the final answer.

    Only the visible text deltas are yielded; thinking tokens stay internal.
    """
    messages = [
        {"role": "user",      "content": _ONESHOT_USER},
        {"role": "assistant", "content": _ONESHOT_ASSISTANT},
        {"role": "user",      "content": question},
    ]

    full_content = ""
    try:
        with _claude_client.messages.stream(
            model=CLAUDE_MAIN_MODEL,
            max_tokens=8000,          # must cover thinking_budget + visible output
            thinking={
                "type": "enabled",
                "budget_tokens": CLAUDE_THINKING_BUDGET,   # default 3000
            },
            system=system_prompt,
            messages=messages,
            stop_sequences=["[TERMINATE]"],
            temperature=1,            # required when extended thinking is enabled
        ) as stream:
            for event in stream:
                # Only yield visible text deltas — skip thinking block deltas
                if (
                    hasattr(event, "type")
                    and event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"
                ):
                    text = event.delta.text
                    if text:
                        if full_content.count("[POINT") > 12:
                            break
                        full_content += text
                        yield text

        logger.debug(f"Claude stream complete | chars={len(full_content)}")

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
                if full_content.count("[POINT") > 12:
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

    When LLM_PROVIDER=anthropic (default):
      - Uses Claude with Extended Thinking for genuine legal reasoning
      - Thinking tokens are internal; only the structured LETA output is yielded

    When LLM_PROVIDER=openai or ollama:
      - Falls back to GPT-4o / local model via OpenAI-compatible API
    """
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        yield "## Error: ANTHROPIC_API_KEY not configured."
        return
    if LLM_PROVIDER != "anthropic" and not OPENAI_API_KEY and not OLLAMA_API_KEY:
        yield "## Error: No LLM API Key configured."
        return

    truth_rules_text = rules_engine.get_all_rules_as_text()
    formatted_system_prompt = SYSTEM_PROMPT.format(
        context=context,
        truth_rules=truth_rules_text,
    )

    logger.debug(f"synthesize_answer_stream | provider={LLM_PROVIDER} | question={question[:80]}")

    if LLM_PROVIDER == "anthropic":
        # Claude uses native Extended Thinking (API-level) for reasoning —
        # do NOT inject text-based <thinking> instructions which conflict
        # with the hardware-level thinking and waste tokens.
        yield from _stream_claude(question, formatted_system_prompt)
    else:
        # OpenAI/Ollama lack native thinking — use prompt-based CoT
        yield from _stream_openai(question, formatted_system_prompt)


def synthesize_answer(question: str, context: str) -> str:
    return "".join(synthesize_answer_stream(question, context))
