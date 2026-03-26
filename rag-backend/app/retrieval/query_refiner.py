import json
import logging
from app.config import (
    LLM_PROVIDER,
    OPENAI_API_KEY, LLM_MODEL, OLLAMA_API_KEY,
    ANTHROPIC_API_KEY, CLAUDE_UTILITY_MODEL,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Client initialisation
# ─────────────────────────────────────────────────────────────────────────────

if LLM_PROVIDER == "anthropic":
    import anthropic as _anthropic
    _claude = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
else:
    import openai as _openai
    if LLM_PROVIDER == "ollama":
        _oai = _openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    else:
        _oai = _openai.OpenAI(api_key=OPENAI_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper: single-turn LLM call → plain text
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, temperature: float = 0.0) -> str:
    """
    Fires a single non-streaming LLM call and returns the text response.
    Uses claude-haiku (fast & cheap) when provider=anthropic,
    otherwise uses the configured OpenAI/Ollama model.
    """
    try:
        if LLM_PROVIDER == "anthropic":
            resp = _claude.messages.create(
                model=CLAUDE_UTILITY_MODEL,
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.content[0].text.strip()
        else:
            resp = _oai.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"_call_llm failed: {e}")
        return ""


def _call_llm_json(system: str, user: str, temperature: float = 0.0) -> str:
    """
    Like _call_llm but requests JSON output.
    For Claude, JSON reliability comes from prompt instructions (no special API param needed).
    For OpenAI, uses response_format=json_object.
    """
    try:
        if LLM_PROVIDER == "anthropic":
            # Claude follows JSON instructions reliably without a special mode
            resp = _claude.messages.create(
                model=CLAUDE_UTILITY_MODEL,
                max_tokens=1024,
                system=system + "\n\nYou MUST respond with ONLY a valid JSON object. No prose, no markdown fences.",
                messages=[{"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.content[0].text.strip()
        else:
            resp = _oai.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"_call_llm_json failed: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def refine_query(raw_query: str) -> str:
    """
    Corrects spelling, expands GST acronyms, and completes incomplete queries
    BEFORE retrieval.  Uses the cheap utility model for speed.
    """
    system = """You are a GST Search Optimizer.
Rewrite the user's search query for better retrieval.

RULES:
1. Correct spelling mistakes (e.g., "reverce charge" -> "reverse charge").
2. Expand standard GST acronyms (e.g., "ITC" -> "Input Tax Credit").
3. If the query is incomplete but intent is clear, complete it.
4. Do NOT answer the question. Output ONLY the cleaned query string."""

    result = _call_llm(system, raw_query, temperature=0.0)
    return result if result else raw_query


def generate_advanced_queries(raw_query: str) -> dict:
    """
    Single LLM call that produces:
      - 3 diverse search queries (Multi-Query Expansion)
      - 1 HyDE document for dense vector matching
      - topic + subtopic classification

    Returns: {"queries": [...], "hyde_document": "...", "topic": "...", "subtopic": "..."}
    """
    system = """You are an advanced expert in Indian GST Law.
Optimise a user query for a vector database search.
Output a valid JSON object with EXACTLY four keys:
1. "queries": A list of exactly 3 distinct, highly technical search queries derived
   from the user's raw query. Cover different angles (Section numbers, specific rules,
   terminology).
2. "hyde_document": A 3 to 4 sentence hypothetical, perfect legal answer to the user's
   query using the dense, formal vocabulary of official GST Acts, Rules, or Notifications.
3. "topic": Classify into exactly ONE topic from: [ITC, RCM, Export, Refund, Registration,
   Place_of_Supply, Time_of_Supply, Valuation, Exemption, Returns, Penalty, Audit,
   Classification, Supply, Payment, Appeals, General]
4. "subtopic": A specific subtopic or null if none applies.

Respond with ONLY the raw JSON object."""

    raw = _call_llm_json(system, raw_query, temperature=0.2)

    # Strip markdown fences if any model wraps the response
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(raw)
        if "queries" not in result or not isinstance(result["queries"], list):
            result["queries"] = [raw_query]
        if "hyde_document" not in result:
            result["hyde_document"] = ""
        if "topic" not in result:
            result["topic"] = "General"
        if "subtopic" not in result:
            result["subtopic"] = None
        return result
    except Exception as e:
        logger.error(f"generate_advanced_queries parse error: {e} | raw={raw[:200]}")
        return {"queries": [raw_query], "hyde_document": "", "topic": "General", "subtopic": None}


def extract_query_topic(query: str) -> dict:
    """
    Classifies the query into a GST topic and subtopic.
    Returns: {"topic": "...", "subtopic": "..."}
    """
    system = """You are a GST Topic & Subtopic Classifier.
Classify the following query into exactly ONE topic and ONE subtopic.

Topics: [ITC, RCM, Export, Refund, Registration, Place of Supply, Time of Supply,
          Valuation, Exemption, Returns, Penalty, Audit, General]

Sample Subtopics:
- ITC: [Blocked ITC, Apportionment, Availability, Capital Goods]
- Export: [Zero Rated, Refund on Export]
- RCM: [Services, Goods]

Respond with ONLY a JSON object: {"topic": "TOPIC_NAME", "subtopic": "SUBTOPIC_OR_NONE"}"""

    raw = _call_llm_json(system, query, temperature=0.0)

    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(raw)
    except Exception:
        return {"topic": "General", "subtopic": None}
