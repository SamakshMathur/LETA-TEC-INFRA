"""
Shared Anthropic client factory.

All Anthropic client construction goes through here so that timeout
policy is set in one place. Past bugs:
  - synthesizer.py had 900s timeout → invisible 15-minute hang when API slow
  - answer_verifier.py had NO timeout (default 600s) → same class of hang
  - intent_classifier.py had 5s timeout (correct) but set independently

Usage:
    from app.utils.anthropic_client import get_anthropic_client

    # Utility calls (query expansion, verification, classification) — short timeout
    client = get_anthropic_client(timeout=8.0)

    # Main synthesis streaming — longer timeout, still bounded
    client = get_anthropic_client(timeout=45.0)

    # Ingestion-time enrichment — offline, can be more generous
    client = get_anthropic_client(timeout=30.0)
"""
import logging
import httpx

logger = logging.getLogger(__name__)

# Default timeouts by use-case category
TIMEOUT_UTILITY = 8.0    # query expansion, classification, verification
TIMEOUT_SYNTHESIS = 45.0  # main answer generation (streaming)
TIMEOUT_INGESTION = 30.0  # offline contextual enrichment


def get_anthropic_client(timeout: float = TIMEOUT_UTILITY, connect: float = 4.0):
    """
    Returns an ``anthropic.Anthropic`` client with explicit timeout bounds.

    Args:
        timeout:  Read timeout in seconds (how long to wait for a response).
                  Use one of the TIMEOUT_* module constants for clarity.
        connect:  Connect timeout in seconds. 4s is enough to detect DNS/network
                  failures quickly without false-positive timeouts on a warm cluster.

    Returns:
        anthropic.Anthropic instance with the given timeouts applied.

    Raises:
        ImportError: if the ``anthropic`` package is not installed.
        RuntimeError: if ANTHROPIC_API_KEY is not set.
    """
    import anthropic
    from app.config import ANTHROPIC_API_KEY

    if not ANTHROPIC_API_KEY:
        logger.warning("get_anthropic_client: ANTHROPIC_API_KEY not set — calls will fail")

    return anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        timeout=httpx.Timeout(timeout=timeout, connect=connect),
    )
