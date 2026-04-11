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
CLAUDE_THINKING_BUDGET = int(os.getenv("CLAUDE_THINKING_BUDGET", "3000"))
VISUAL_LLM_MODEL = "claude-sonnet-4-6"

# ─── Embedding Config ─────────────────────────────────────────────────────
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")  # "openai" or "local"
# BAAI/bge-large-en-v1.5: 1024-dim dense retrieval model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
VECTOR_DIM = 1024 if EMBEDDING_PROVIDER == "local" else 3072

# ─── Retrieval Tuning (externalized magic numbers) ─────────────────────────
VECTOR_SEARCH_TOP_K = int(os.getenv("VECTOR_SEARCH_TOP_K", "150"))
VECTOR_EXPANDED_TOP_K = int(os.getenv("VECTOR_EXPANDED_TOP_K", "50"))
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "100"))
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.7"))
MAX_RESPONSE_POINTS = int(os.getenv("MAX_RESPONSE_POINTS", "12"))

# ─── Reranking & Optimization ─────────────────────────────────────────────
RERANKING_MODEL = "ms-marco-MiniLM-L-12-v2"
CACHE_DIR = ".diskcache_v5"

# ─── Token Budget & Cost Controls ─────────────────────────────────────────
# Hard cap on input tokens sent to the LLM. Queries exceeding this are rejected
# before hitting the API — prevents runaway costs from adversarial inputs.
MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "8000"))

# Haiku routing: queries whose complexity score is below this threshold are
# answered by the cheaper Haiku model instead of Sonnet.
# Scale: 0.0 (trivial) → 1.0 (highly complex multi-section analysis)
HAIKU_COMPLEXITY_THRESHOLD = float(os.getenv("HAIKU_COMPLEXITY_THRESHOLD", "0.4"))

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
DATA_DIR = str(_APP_ROOT / "RAG_INFORMATION_DATABASE")

# ─── S3 Config for AWS Deployment ─────────────────────────────────────────
S3_BUCKET_NAME = "gst-rag-documents"
LOCAL_DATA_ROOT = str(_APP_ROOT)


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
