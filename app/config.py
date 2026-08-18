import os
from dotenv import load_dotenv

load_dotenv()

# LLM Config (OpenRouter)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_MODEL = "google/gemini-2.0-flash-exp:free" # Upgraded for better accuracy

# Vector DB Config
VECTOR_DB_PATH = "vectordb/index.faiss"
CHUNKS_PATH = "data/chunks/chunks.jsonl"

# Ingestion Config
DATA_DIR = "RAG_INFORMATION_DATABASE"

# S3 Config for AWS Deployment
S3_BUCKET_NAME = "gst-rag-documents"
LOCAL_DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
