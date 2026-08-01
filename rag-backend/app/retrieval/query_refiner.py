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
      - 4 diverse search queries (Multi-Query Expansion — statutory, circular, notification, factual)
      - 1 HyDE document written in corpus-authentic legal language
      - topic + subtopic classification

    Returns: {"queries": [...], "hyde_document": "...", "topic": "...", "subtopic": "..."}
    """
    system = """You are an advanced expert in Indian GST Law with deep knowledge of the CBIC
document corpus (2017–2025): CGST/IGST Acts, Rules, CBIC Circulars, GST Rate Notifications,
Trade Notices, AAR rulings, and High Court judgments.

Your task: optimise a user query for retrieval from a vector database that contains all
the above documents indexed as text chunks.

Output a valid JSON object with EXACTLY four keys:

1. "queries": A list of exactly 4 distinct search queries, each targeting a different slice
   of the corpus. MANDATORY structure — one query per angle:
   (a) STATUTORY angle — cite the relevant CGST/IGST Act section number or CGST Rule number.
       Use formal statutory language: "Section 16(2)(b) CGST Act input tax credit conditions"
   (b) CBIC CIRCULAR angle — explicitly target CBIC Circulars and Instructions.
       Always include keywords: "CBIC Circular clarification" or "Instruction No."
       Example: "CBIC Circular clarification input tax credit motor vehicle section 17(5)"
   (c) NOTIFICATION angle — explicitly target GST rate and exemption notifications.
       Always include: "GST Notification" or "Central Tax Rate notification" or "IGST exemption"
       Example: "Notification No. Central Tax Rate GST exemption software services 2017 2018 2023"
   (d) SCENARIO/FACT angle — use the technical terminology of the specific facts given.
       Include any amounts, business type, transaction structure, or year mentioned.

2. "hyde_document": A 4–5 sentence hypothetical document written to EXACTLY MATCH the style
   of official CBIC Circulars and GST Notifications. Use their exact vocabulary:
   - Start with: "It is hereby clarified that..." or "As per Circular No. [X]/[Y]/[YEAR]-GST dated..."
   - Include section numbers, rule numbers, sub-clauses
   - Mention the relevant year range (2017–2025)
   - Use passive-voice bureaucratic register: "the registered person shall be eligible...",
     "as per the provisions of Section X of the CGST Act 2017..."
   This document is used for vector similarity search, so it must read like the actual
   documents in the corpus — not a summary, but an authentic-sounding extract.

3. "topic": Classify into exactly ONE topic from: [ITC, RCM, Export, Refund, Registration,
   Place_of_Supply, Time_of_Supply, Valuation, Exemption, Returns, Penalty, Audit,
   Classification, Supply, Payment, Appeals, Intermediary, Cross_Border_Services, General]

4. "subtopic": A specific subtopic string or null if none applies.

Respond with ONLY the raw JSON object. No prose. No markdown."""

    raw = _call_llm_json(system, raw_query, temperature=0.15)

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
