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
      - 6 concept-targeted search queries (Multi-Query Expansion)
      - 1 HyDE document written in corpus-authentic legal language
      - topic + subtopic classification

    Returns: {"queries": [...], "hyde_document": "...", "topic": "...", "subtopic": "..."}
    """
    system = """You are a Senior Partner-level Indian GST expert and retrieval engineer.
You have encyclopaedic knowledge of the CBIC corpus (2017–2025): CGST/IGST Acts and Rules,
CBIC Circulars, GST Rate Notifications, Trade Notices, AAR rulings, and Court judgments.

Your task: decompose a user query into 6 laser-focused sub-queries that will collectively
surface EVERY legal provision, circular, rule, and valuation concept relevant to the question.

── CRITICAL LEGAL MAPPING ────────────────────────────────────────────────────────────────────
Apply these mandatory expansions when the topic is present in the query:

cross charge / distinct person / inter-branch →
  MUST generate sub-queries for: Section 25(4) Section 25(5) CGST Act distinct person,
  ISD Input Service Distributor Section 20 CGST Act Rule 39, Circular 199/11/2023-GST
  cross charge ISD common expenses branches head office, Rule 28 valuation distinct person
  open market value second proviso, Schedule I supply without consideration distinct person.

ITC / input tax credit →
  MUST cover: Section 16, Section 17(5) blocked credit, Rule 42/43 apportionment,
  CBIC Circular clarification.

reverse charge / RCM →
  MUST cover: Section 9(3) Section 9(4), Notification 13/2017-CT(Rate), Rule 85/86.

export / zero-rated →
  MUST cover: Section 16 IGST Act, Rule 96, LUT, refund Section 54.

place of supply →
  MUST cover: Section 12/13 IGST Act, intermediary, OIDAR.

works contract →
  MUST cover: Section 17(5)(c)(d), Schedule II entry 6.

────────────────────────────────────────────────────────────────────────────────────────────

Output a valid JSON object with EXACTLY four keys:

1. "queries": A list of exactly 6 distinct search queries. Each query must target a DIFFERENT
   specific legal concept. MANDATORY structure:

   (a) PRIMARY STATUTORY — the single most important Act section + sub-section.
       Format: "Section X(Y)(Z) CGST Act 2017 [specific legal concept]"

   (b) SECONDARY STATUTORY — a DIFFERENT section/rule (NOT the same as (a)).
       For cross-charge: this MUST be "Section 20 CGST Act ISD Input Service Distributor Rule 39 distribution common input services"
       For ITC: this MUST be "Section 17(5) CGST Act blocked input tax credit [specific item]"

   (c) CBIC CIRCULAR — explicitly name Circular numbers when known.
       For cross-charge: MUST include "Circular 199/11/2023-GST cross charge ISD head office branches"
       Always start with: "CBIC Circular No." or "Circular clarification"

   (d) NOTIFICATION / RULE — target specific Rule numbers and Notifications.
       For cross-charge: MUST include "Rule 28 CGST Rules 2017 valuation related party distinct person open market value"
       Always include: "Rule" or "Notification" keyword.

   (e) DEFINITIONAL / DEEMING — target the definitional provision or Schedule entry.
       For cross-charge: MUST include "Schedule I Entry 2 supply without consideration distinct person CGST"
       For ITC: target Section 2(59) input service or Section 2(62) input tax.

   (f) SCENARIO / PRACTICAL — use ALL technical terms from the question including any
       amounts, business types, transaction structures. Include the most important keywords
       from angles (a)–(e) combined for maximum recall:
       "cross charge ISD Input Service Distributor distinct person Section 25(4) Circular 199
       Rule 28 valuation head office branch internally generated third party common expenses"

2. "hyde_document": A 5–6 sentence hypothetical document written to EXACTLY MATCH the style
   of official CBIC Circulars. Use their exact vocabulary:
   - Start: "It is hereby clarified that..." or "As per Circular No. 199/11/2023-GST dated..."
   - Include section numbers, rule numbers, sub-clauses, proviso references
   - Mention relevant year (2017–2025)
   - Use bureaucratic passive voice: "the registered person shall...", "as per the provisions of..."
   - Cover ALL key concepts from the query (statutory base + circular clarification + valuation rule)
   This is used for vector similarity — write it to semantically match the actual corpus documents.

3. "topic": Classify into exactly ONE from: [ITC, RCM, Export, Refund, Registration,
   Place_of_Supply, Time_of_Supply, Valuation, Exemption, Returns, Penalty, Audit,
   Classification, Supply, Payment, Appeals, Intermediary, Cross_Border_Services, General]

4. "subtopic": A specific subtopic string (e.g. "Cross Charge ISD", "Blocked Credit Section 17(5)",
   "Zero Rated Export LUT") or null if none.

Respond with ONLY the raw JSON object. No prose. No markdown fences."""

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


def retrieval_self_critique(query: str, retrieved_sources: list, taxonomy: dict) -> dict:
    """
    Priority 7 — Retrieval Self-Critique.
    Asks the utility model: 'Have we missed any governing authority?'

    Called ONLY when:
      (a) taxonomy confidence = 0 (unknown topic — taxonomy can't predict authorities), OR
      (b) mandatory coverage < 70% (deterministic check found gaps, ask LLM for deeper look)

    Returns: {"missing": [...], "confidence": "high/medium/low"}
    Cost: one Haiku call (~100-200 tokens) — cheap relative to the main LLM call.
    """
    import json as _json

    _source_summary = "; ".join(s.split("/")[-1] for s in retrieved_sources[:15] if s)
    _known_mandatory = _json.dumps({
        "sections":  taxonomy.get("sections",  []),
        "rules":     taxonomy.get("rules",     []),
        "circulars": taxonomy.get("circulars", []),
    }, ensure_ascii=False)

    system = """You are a Senior Partner-level Indian GST expert reviewing retrieved legal documents.
Your task: identify any GOVERNING legal authority that is MISSING from the retrieved sources.

RULES:
1. Only report authorities that are DEFINITIVELY REQUIRED for a complete legal answer.
2. Be specific — name the actual section number, rule number, or circular number.
3. Do NOT hallucinate. Only mention provisions you are certain govern this issue.
4. If nothing is missing, return an empty list.
5. Limit to maximum 5 missing items.

Respond with ONLY a valid JSON object:
{"missing": ["Section 25(4) CGST Act", "Circular No. 199/11/2023", ...], "confidence": "high"}"""

    user = (
        f"Legal question: {query}\n\n"
        f"Retrieved documents include: {_source_summary}\n\n"
        f"Already identified mandatory authorities: {_known_mandatory}\n\n"
        "What key governing authority (if any) is MISSING from the retrieved sources?"
    )

    raw = _call_llm_json(system, user, temperature=0.0)
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        result = _json.loads(raw)
        if "missing" not in result or not isinstance(result["missing"], list):
            result["missing"] = []
        if "confidence" not in result:
            result["confidence"] = "low"
        return result
    except Exception:
        return {"missing": [], "confidence": "low"}


def verify_answer_authority_coverage(
    query: str,
    answer: str,
    taxonomy: dict,
    coverage_result: dict,
) -> dict:
    """
    Priority 10 — Answer Verification Agent.
    After the LLM generates an answer, verify it actually cited the mandatory
    governing authorities.  If not, flag the gaps so the caller can append a
    disclaimer or trigger regeneration.

    Returns:
        {
          "cited":   list   — mandatory authorities the answer mentions
          "missing": list   — mandatory authorities the answer omitted
          "verdict": "pass" | "partial" | "fail"
          "note":    str    — human-readable gap summary (empty if pass)
        }

    Runs in ~50-100ms (string search, no LLM).  Only called when taxonomy
    confidence > 0 so it adds zero cost on unknown topics.
    """
    import json as _json
    if not answer or not taxonomy.get("sections") and not taxonomy.get("circulars"):
        return {"cited": [], "missing": [], "verdict": "pass", "note": ""}

    answer_lower = answer.lower()

    # For each mandatory authority, check if the answer text mentions it
    # Use simple keyword matching (no LLM needed — this is cheap and fast)
    def _is_cited(authority_key: str) -> bool:
        """Checks if the authority appears in the answer text."""
        # CGST_SEC_25 → look for "section 25" or "sec 25" or "sec. 25"
        # CGST_RUL_28 → look for "rule 28"
        # CIRCULAR_199 → look for "circular 199" or "circular no. 199" or "199/11/2023"
        ak = authority_key.lower()
        if "_sec_" in ak:
            num = ak.split("_sec_")[-1]
            return (f"section {num}" in answer_lower or f"sec {num}" in answer_lower
                    or f"sec. {num}" in answer_lower or f"sec.{num}" in answer_lower)
        elif "_rul_" in ak:
            num = ak.split("_rul_")[-1]
            return f"rule {num}" in answer_lower
        elif "circular_" in ak:
            num = ak.split("circular_")[-1]
            return (f"circular {num}" in answer_lower
                    or f"circular no. {num}" in answer_lower
                    or f"circular no {num}" in answer_lower
                    or f"/{num}/" in answer_lower)
        return False

    all_mandatory = (
        taxonomy.get("sections", []) +
        taxonomy.get("rules",    []) +
        taxonomy.get("circulars",[])
    )
    cited   = [a for a in all_mandatory if _is_cited(a)]
    missing = [a for a in all_mandatory if not _is_cited(a)]

    if not missing:
        verdict = "pass"
        note    = ""
    elif len(missing) <= len(all_mandatory) // 2:
        verdict = "partial"
        note    = f"Answer may not have addressed: {', '.join(missing)}"
    else:
        verdict = "fail"
        note    = f"Answer missed key authorities: {', '.join(missing)}"

    logger.info(
        f"Answer verification: verdict={verdict} cited={cited} missing={missing}"
    )
    return {"cited": cited, "missing": missing, "verdict": verdict, "note": note}


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
