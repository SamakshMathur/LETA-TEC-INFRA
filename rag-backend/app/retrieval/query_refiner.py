import json
import logging
from app.config import (
    LLM_PROVIDER,
    OPENAI_API_KEY, LLM_MODEL, OLLAMA_API_KEY,
    ANTHROPIC_API_KEY, CLAUDE_UTILITY_MODEL,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
import app.generation.clients as _clients


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper: single-turn LLM call → plain text
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, temperature: float = 0.0, provider: str = None, model: str = None) -> str:
    """
    Fires a single non-streaming LLM call and returns the text response.
    Uses dynamically resolved client and model according to request scope.
    """
    active_provider = provider if provider else LLM_PROVIDER
    if active_provider == "claude":
        active_provider = "anthropic"

    try:
        if active_provider == "anthropic":
            client = _clients.get_claude_client()
            model_to_use = model if model else CLAUDE_UTILITY_MODEL
            resp = client.messages.create(
                model=model_to_use,
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.content[0].text.strip()
        elif active_provider == "openai":
            client = _clients.get_openai_client()
            model_to_use = model if model else LLM_MODEL
            resp = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
        elif active_provider == "ollama":
            client = _clients.get_ollama_client()
            model_to_use = model if model else LLM_MODEL
            resp = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
        else:
            raise ValueError(f"Unsupported provider: {active_provider}")
    except Exception as e:
        logger.error(f"_call_llm failed: {e}", exc_info=True)
        return ""


def _call_llm_json(system: str, user: str, temperature: float = 0.0, provider: str = None, model: str = None) -> str:
    """
    Like _call_llm but requests JSON output.
    For Claude, JSON reliability comes from prompt instructions (no special API param needed).
    For OpenAI/Ollama, uses response_format=json_object.
    """
    active_provider = provider if provider else LLM_PROVIDER
    if active_provider == "claude":
        active_provider = "anthropic"

    try:
        if active_provider == "anthropic":
            client = _clients.get_claude_client()
            model_to_use = model if model else CLAUDE_UTILITY_MODEL
            resp = client.messages.create(
                model=model_to_use,
                max_tokens=1024,
                system=system + "\n\nYou MUST respond with ONLY a valid JSON object. No prose, no markdown fences.",
                messages=[{"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.content[0].text.strip()
        elif active_provider == "openai":
            client = _clients.get_openai_client()
            model_to_use = model if model else LLM_MODEL
            resp = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content.strip()
        elif active_provider == "ollama":
            client = _clients.get_ollama_client()
            model_to_use = model if model else LLM_MODEL
            resp = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content.strip()
        else:
            raise ValueError(f"Unsupported provider: {active_provider}")
    except Exception as e:
        logger.error(f"_call_llm_json failed: {e}", exc_info=True)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def refine_query(raw_query: str, provider: str = None, model: str = None) -> str:
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

    result = _call_llm(system, raw_query, temperature=0.0, provider=provider, model=model)
    return result if result else raw_query


_statute_topics = None

def get_statute_topics() -> list:
    global _statute_topics
    if _statute_topics is None:
        try:
            import os
            import json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            index_path = os.path.join(current_dir, "statute_index.json")
            if os.path.exists(index_path):
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                _statute_topics = list(index_data.keys())
            else:
                logger.warning(f"statute_index.json not found at {index_path} — using defaults")
                _statute_topics = ["ITC", "RCM", "Export", "Refund", "Registration", "Composition Scheme", "Valuation", "Time of Supply", "Place of Supply", "Exemption", "Demand and Recovery", "Penalty", "Appeals", "Returns", "Invoice", "E-Way Bill", "Audit and Investigation", "Supply Definition", "Payment", "TDS TCS", "Real Estate", "E-Commerce", "Accounts and Records", "Job Work", "Anti Profiteering", "Assessment", "Intermediary", "Cross_Border_Services", "General"]
        except Exception as e:
            logger.error(f"Failed to load topics dynamically: {e}")
            _statute_topics = ["ITC", "RCM", "Export", "Refund", "Registration", "Composition Scheme", "Valuation", "Time of Supply", "Place of Supply", "Exemption", "Demand and Recovery", "Penalty", "Appeals", "Returns", "Invoice", "E-Way Bill", "Audit and Investigation", "Supply Definition", "Payment", "TDS TCS", "Real Estate", "E-Commerce", "Accounts and Records", "Job Work", "Anti Profiteering", "Assessment", "Intermediary", "Cross_Border_Services", "General"]
    return _statute_topics


def generate_advanced_queries(raw_query: str, provider: str = None, model: str = None) -> dict:
    """
    Single LLM call that produces:
      - 3 diverse search queries (Multi-Query Expansion)
      - 1 HyDE document for dense vector matching
      - topic + subtopic classification

    Returns: {"queries": [...], "hyde_document": "...", "topic": "...", "subtopic": "..."}
    """
    topics_list = get_statute_topics()
    system = f"""You are an advanced expert in Indian GST Law.
Optimise a user query for a vector database search.
Output a valid JSON object with EXACTLY four keys:
1. "queries": A list of exactly 3 distinct, highly technical search queries derived
   from the user's raw query. MANDATORY query structure:
   (a) Statutory angle — focus on the relevant CGST/IGST Act section or Rule number.
   (b) CBIC Circular/Notification angle — rephrase to specifically find CBIC Circulars,
       Instructions, or Notifications that clarify, address or interpret this topic.
       Always include "CBIC Circular" or "Notification" in this query.
   (c) Factual/scenario angle — use the technical scenario terminology and any
       specific facts from the original query.
2. "hyde_document": A 3 to 4 sentence hypothetical, perfect legal answer to the user's
   query using the dense, formal vocabulary of official GST Acts, Rules, Circulars, and
   Notifications. Mention the relevant CBIC Circular number if known.
3. "topic": Classify into exactly ONE topic from: [{', '.join(topics_list)}]
4. "subtopic": A specific subtopic or null if none applies.

Respond with ONLY the raw JSON object."""

    raw = _call_llm_json(system, raw_query, temperature=0.2, provider=provider, model=model)

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


def extract_query_topic(query: str, provider: str = None, model: str = None) -> dict:
    """
    Classifies the query into a GST topic and subtopic.
    Returns: {"topic": "...", "subtopic": "..."}
    """
    topics_list = get_statute_topics()
    system = f"""You are a GST Topic & Subtopic Classifier.
Classify the following query into exactly ONE topic and ONE subtopic.

Topics: [{', '.join(topics_list)}]

Sample Subtopics:
- ITC: [Blocked ITC, Apportionment, Availability, Capital Goods]
- Export: [Zero Rated, Refund on Export]
- RCM: [Services, Goods]

Respond with ONLY a JSON object: {{"topic": "TOPIC_NAME", "subtopic": "SUBTOPIC_OR_NONE"}}"""

    raw = _call_llm_json(system, query, temperature=0.0, provider=provider, model=model)

    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(raw)
    except Exception:
        return {"topic": "General", "subtopic": None}



import re

class TopicRule:
    def __init__(self, topic: str, subtopic: str = None, citations: list = None, patterns: list = None, priority: int = 0):
        self.topic = topic
        self.subtopic = subtopic
        self.citations = citations or []
        self.patterns = [re.compile(p, re.IGNORECASE) for p in (patterns or [])]
        self.priority = priority

    def matches(self, query: str, query_citations: list) -> bool:
        # Check citations first
        for cit in self.citations:
            if cit in query_citations:
                return True
        # Check patterns
        for pat in self.patterns:
            if pat.search(query):
                return True
        return False


# Topic Rule Registry
TOPIC_RULES = [
    # Place of Supply rules
    TopicRule(
        topic="Place_of_Supply",
        citations=["IGST_SEC_10", "IGST_SEC_11", "IGST_SEC_12", "IGST_SEC_13"],
        patterns=[
            r"place\s+of\s+supply",
            r"\bpos\b",
            r"other\s+territory",
            r"foreign\s+country",
            r"transportation\s+of\s+goods\s+for\s+export"
        ],
        priority=12
    ),
    # ITC rules
    TopicRule(
        topic="ITC",
        subtopic="Blocked ITC",
        citations=["CGST_SEC_17"],
        patterns=[r"motor\s+vehicles?", r"block(?:ed)?\s+itc", r"sections?\s+17", r"sec(?:tion)?s?\s+17\(5\)"],
        priority=10
    ),
    TopicRule(
        topic="ITC",
        subtopic="Availability",
        citations=["CGST_SEC_16"],
        patterns=[r"input\s+tax\s+credits?", r"claims?\s+itc", r"eligibility\s+itc", r"itc\s+conditions?"],
        priority=5
    ),
    # Export rules
    TopicRule(
        topic="Export",
        subtopic="Without payment of tax",
        citations=["IGST_SEC_16"],
        patterns=[r"exports?\s+without\s+payment", r"zero\s+rated", r"luts?", r"letters?\s+of\s+undertaking"],
        priority=10
    ),
    TopicRule(
        topic="Export",
        patterns=[r"exports?", r"sezs?", r"special\s+economic\s+zones?"],
        priority=5
    ),
    # Valuation / Discount rules
    TopicRule(
        topic="Valuation",
        subtopic="Discounts",
        citations=["CGST_SEC_15"],
        patterns=[r"post[-_\s]supply\s+discounts?", r"post[-_\s]sale\s+discounts?", r"secondary\s+discounts?", r"discounts?", r"taxable\s+values?", r"sections?\s+15"],
        priority=10
    ),
    TopicRule(
        topic="Valuation",
        subtopic="Credit Note",
        citations=["CGST_SEC_34"],
        patterns=[r"credit\s+notes?"],
        priority=10
    ),
    # RCM rules
    TopicRule(
        topic="RCM",
        subtopic="Services",
        citations=["CGST_SEC_9", "IGST_SEC_5"],
        patterns=[r"reverse\s+charges?", r"rcms?", r"directors?\s+remuneration", r"legal\s+services?", r"gtas?"],
        priority=10
    ),
    # Refund rules
    TopicRule(
        topic="Refund",
        citations=["CGST_SEC_54", "CGST_RUL_89"],
        patterns=[r"refunds?", r"inverted\s+dut(?:y|ies)", r"rules?\s+89"],
        priority=10
    ),
]


def extract_query_refs_local(query: str) -> list:
    q = query.lower()
    refs = []
    seen = set()
    act_code_map = [
        ("cgst", "CGST"), ("igst", "IGST"), ("sgst", "SGST"), ("utgst", "UTGST"),
        ("central goods", "CGST"), ("integrated goods", "IGST"),
        ("union territory", "UTGST"),
    ]
    def _act_codes(ctx: str) -> list:
        found = [code for kw, code in act_code_map if kw in ctx]
        seen_codes = set()
        deduped = []
        for c in found:
            if c not in seen_codes:
                seen_codes.add(c)
                deduped.append(c)
        return deduped if deduped else ["CGST", "IGST"]

    for m in re.finditer(r'\bsec(?:tion)?\s*\.?\s*(\d+)(?:\s*\([^)]{0,12}\))*', q):
        sec = m.group(1)
        ctx = q[max(0, m.start() - 40): m.end() + 40]
        for code in _act_codes(ctx):
            key = f"{code}_SEC_{sec}"
            if key not in seen:
                seen.add(key)
                refs.append(key)

    for m in re.finditer(r'\brule\s+(\d+)(?:\s*\([^)]{0,12}\))*', q):
        rule = m.group(1)
        ctx = q[max(0, m.start() - 40): m.end() + 40]
        for code in _act_codes(ctx):
            key = f"{code}_RUL_{rule}"
            if key not in seen:
                seen.add(key)
                refs.append(key)

    for m in re.finditer(r'\bschedule\s+([ivxlcdm]+|\d+)\b', q):
        sch = m.group(1).upper()
        key = f"CGST_SCH_{sch}"
        if key not in seen:
            seen.add(key)
            refs.append(key)

    for m in re.finditer(r'\bcircular\s+(?:no\.?\s*)?(\d{2,3})\b', q):
        cir_num = m.group(1)
        key = f"CIRCULAR_{cir_num}"
        if key not in seen:
            seen.add(key)
            refs.append(key)

    return refs


def classify_topic_rules(query: str) -> dict:
    citations = extract_query_refs_local(query)
    matched_rule = None

    # Find matching rule with highest priority
    for rule in sorted(TOPIC_RULES, key=lambda x: x.priority, reverse=True):
        if rule.matches(query, citations):
            if matched_rule is None or rule.priority > matched_rule.priority:
                matched_rule = rule

    if matched_rule:
        logger.info(f"Rule-based classification match: topic={matched_rule.topic}, subtopic={matched_rule.subtopic}")
        return {"topic": matched_rule.topic, "subtopic": matched_rule.subtopic}

    return {"topic": None, "subtopic": None}
