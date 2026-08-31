import logging
from app.config import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    OLLAMA_API_KEY,
)

logger = logging.getLogger(__name__)

_claude_client = None
_oai_client = None
_ollama_client = None

def get_claude_client():
    global _claude_client
    if _claude_client is None:
        import anthropic as _anthropic
        if not ANTHROPIC_API_KEY:
            raise ValueError("Anthropic API key (ANTHROPIC_API_KEY) is missing or not configured in environment.")
        _claude_client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Request-scoped Claude client initialized dynamically")
    return _claude_client

def get_openai_client():
    global _oai_client
    if _oai_client is None:
        import openai as _openai
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key (OPENAI_API_KEY) is missing or not configured in environment.")
        _oai_client = _openai.OpenAI(api_key=OPENAI_API_KEY)
        logger.info("Request-scoped OpenAI client initialized dynamically")
    return _oai_client

def get_ollama_client():
    global _ollama_client
    if _ollama_client is None:
        import openai as _openai
        _ollama_client = _openai.OpenAI(
            api_key=OLLAMA_API_KEY if OLLAMA_API_KEY else "ollama",
            base_url="http://localhost:11434/v1",
        )
        logger.info("Request-scoped Ollama client initialized dynamically")
    return _ollama_client
