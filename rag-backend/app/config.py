import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Base Paths (resolved absolute, safe from cwd changes) ────────────────
_APP_ROOT = Path(__file__).resolve().parent.parent  # rag-backend/

# ─── LLM Config ───────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_API_KEY = ""  # Not used — Anthropic only

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "openai" | "anthropic" | "ollama"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")           # used only when provider=openai/ollama

# Claude Models (used when LLM_PROVIDER=anthropic)
CLAUDE_MAIN_MODEL = os.getenv("CLAUDE_MAIN_MODEL", "claude-sonnet-4-6")
CLAUDE_UTILITY_MODEL = os.getenv("CLAUDE_UTILITY_MODEL", "claude-haiku-4-5-20251001")
CLAUDE_THINKING_BUDGET = int(os.getenv("CLAUDE_THINKING_BUDGET", "5000"))
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "16000"))
VISUAL_LLM_MODEL = "claude-sonnet-4-6"

# ─── Embedding Config ─────────────────────────────────────────────────────
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")  # "openai" or "local"
# BAAI/bge-large-en-v1.5: 1024-dim dense retrieval model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
VECTOR_DIM = 1024 if EMBEDDING_PROVIDER == "local" else 3072

# ─── Retrieval Tuning (externalized magic numbers) ─────────────────────────
VECTOR_SEARCH_TOP_K = int(os.getenv("VECTOR_SEARCH_TOP_K", "50"))
VECTOR_EXPANDED_TOP_K = int(os.getenv("VECTOR_EXPANDED_TOP_K", "25"))
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "45"))
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.72"))
MAX_RESPONSE_POINTS = int(os.getenv("MAX_RESPONSE_POINTS", "15"))

# ─── Reranking & Optimization ─────────────────────────────────────────────
RERANKING_MODEL = "BAAI/bge-reranker-v2-m3"
CACHE_DIR = ".diskcache_v5"

# ─── Token Budget & Cost Controls ─────────────────────────────────────────
# Hard cap on input tokens sent to the LLM. Queries exceeding this are rejected
# before hitting the API — prevents runaway costs from adversarial inputs.
MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "150000"))

# Haiku routing: queries whose complexity score is below this threshold are
# answered by the cheaper Haiku model instead of Sonnet.
# Scale: 0.0 (trivial) → 1.0 (highly complex multi-section analysis)
HAIKU_COMPLEXITY_THRESHOLD = float(os.getenv("HAIKU_COMPLEXITY_THRESHOLD", "0.20"))

# Response-length routing thresholds (independent of model routing above):
#   score < BRIEF_RESPONSE_THRESHOLD          → 3-point compact answer
#   BRIEF <= score < STANDARD_RESPONSE_THRESHOLD → 5-point focused analysis
#   score >= STANDARD_RESPONSE_THRESHOLD      → full 10-point legal opinion
BRIEF_RESPONSE_THRESHOLD    = float(os.getenv("BRIEF_RESPONSE_THRESHOLD",    "0.25"))
STANDARD_RESPONSE_THRESHOLD = float(os.getenv("STANDARD_RESPONSE_THRESHOLD", "0.60"))

# Extended-thinking gate: Sonnet is used for complexity >= HAIKU_COMPLEXITY_THRESHOLD,
# but extended thinking (expensive) is only switched ON when complexity is high enough
# to justify it (drafting, multi-section disputes, adversarial analysis).
#   0.4–0.7 → Sonnet, NO thinking  (standard legal analysis, saves ~8 000 thinking tokens)
#   >= 0.7  → Sonnet + thinking    (complex drafting / ITC disputes / SCN replies)
SONNET_THINKING_THRESHOLD = float(os.getenv("SONNET_THINKING_THRESHOLD", "0.65"))

# ─── Prompt Version (bump this whenever the prompt/output format changes) ─────
# All cache keys include this version. Changing it instantly invalidates every
# cached answer — old entries are bypassed (not deleted; they expire via TTL).
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v6")

# Redis Cache Config
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Similarity threshold for semantic cache hits (0.92 = very close match required)
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.92"))
# Minimum answer confidence to store in cache (low-confidence answers are never cached)
CACHE_MIN_CONFIDENCE = float(os.getenv("CACHE_MIN_CONFIDENCE", "0.85"))
# TTL in seconds: 48h for legal content (GST rules/circulars change frequently)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(48 * 3600)))

# ─── Vector DB Config (absolute paths) ────────────────────────────────────
VECTOR_DB_PATH = str(_APP_ROOT / "vectordb" / "index.faiss")
CHUNKS_PATH = str(_APP_ROOT / "data" / "chunks" / "chunks.jsonl")

# ─── Ingestion Config ─────────────────────────────────────────────────────
DATA_DIR = str(_APP_ROOT / "Database_V2.0")

# ─── S3 Config for AWS Deployment ─────────────────────────────────────────
S3_BUCKET_NAME = "gst-rag-documents"
LOCAL_DATA_ROOT = str(_APP_ROOT)

# ─── Legal Taxonomy & Authority Weights ───────────────────────────────────
# Used by scoring_policy.py to weight document types in retrieval scoring.
# Higher = more authoritative in GST law hierarchy.
AUTHORITY_WEIGHTS = {
    "PRIMARY_LAW":    5.0,   # CGST/IGST/UTGST Acts
    "RULES":          4.0,   # CGST Rules
    "CIRCULAR":       3.0,   # CBIC Circulars
    "NOTIFICATION":   3.0,   # Rate/exemption notifications
    "CASE_LAW":       2.0,   # High Court / Supreme Court / AAR
    "ADVANCE_RULING": 2.0,
    "ICAI_GUIDANCE":  1.0,
    "REFERENCE":      0.5,
    "OTHER":          0.5,
}

# GST sections whose subject-matter is substantive (eligibility / liability rules)
# vs procedural (appeals, advance ruling process) — used by reranker
SUBSTANTIVE_SECTIONS = ["7", "8", "9", "10", "11", "12", "13", "15", "16", "17", "54"]
PROCEDURAL_SECTIONS  = ["97", "98", "100", "101", "107", "112"]


# ─── Startup Validation ───────────────────────────────────────────────────
def validate_config():
    """Run at app startup to catch misconfigurations early."""
    warnings = []
    errors = []

    # API key checks
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        warnings.append("ANTHROPIC_API_KEY not set — answer generation will fail")
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY not set — answer generation will fail")

    # File existence checks
    if not Path(VECTOR_DB_PATH).exists():
        warnings.append(f"FAISS index not found at {VECTOR_DB_PATH} — run build_vector_store first")
    if not Path(CHUNKS_PATH).exists():
        errors.append(f"Chunks file not found at {CHUNKS_PATH} — run ingestion + chunking first")
    if not Path(DATA_DIR).exists():
        warnings.append(f"Data directory not found at {DATA_DIR}")

    for w in warnings:
        logger.warning(f"[CONFIG] {w}")
    for e in errors:
        logger.error(f"[CONFIG] {e}")

    return len(errors) == 0


import contextvars
ai_log_context = contextvars.ContextVar("ai_log_context", default=None)
