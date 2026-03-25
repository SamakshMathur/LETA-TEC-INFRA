import os
from dotenv import load_dotenv

load_dotenv()

# LLM Config (Smart Budget Enterprise)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_API_KEY = ""  # Not used — Anthropic only

# Core Logic LLM
# Set LLM_PROVIDER=anthropic in .env to use Claude for answer generation
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "openai" | "anthropic" | "ollama"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")           # used only when provider=openai/ollama

# Claude Models (used when LLM_PROVIDER=anthropic)
# Main generation — full intelligence + extended thinking
CLAUDE_MAIN_MODEL = os.getenv("CLAUDE_MAIN_MODEL", "claude-sonnet-4-6")
# Utility calls (query expansion, topic classification) — fast & cheap
CLAUDE_UTILITY_MODEL = os.getenv("CLAUDE_UTILITY_MODEL", "claude-haiku-4-5-20251001")
# Thinking token budget for extended reasoning on complex legal questions
CLAUDE_THINKING_BUDGET = int(os.getenv("CLAUDE_THINKING_BUDGET", "3000"))

# Visual/UI Enhancement LLM (Anthropic)
VISUAL_LLM_MODEL = "claude-sonnet-4-6"

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")  # "openai" or "local"
# BAAI/bge-large-en-v1.5: 768-dim, significantly better than all-MiniLM-L6-v2 for
# domain-specific dense retrieval. Requires rebuilding the FAISS index after change.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
VECTOR_DIM = 1024 if EMBEDDING_PROVIDER == "local" else 3072

# Reranking & Optimization
RERANKING_MODEL = "ms-marco-MiniLM-L-12-v2"  # SOTA Accuracy (Slower but accurate)
CACHE_DIR = ".diskcache_v5"  # Persistent cache (Rotated to v5 to bust old cached responses)

# Vector DB Config
VECTOR_DB_PATH = "vectordb/index.faiss"
CHUNKS_PATH = "data/chunks/chunks.jsonl"

# Ingestion Config
DATA_DIR = "RAG_INFORMATION_DATABASE"

# S3 Config for AWS Deployment
S3_BUCKET_NAME = "gst-rag-documents"
LOCAL_DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
