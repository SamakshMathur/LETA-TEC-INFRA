def estimate_confidence(context: str) -> float:
    """
    Very simple, honest confidence estimator.
    """
    if not context or len(context.strip()) < 50:
        return 0.4

    if any(rate in context for rate in ["12%", "18%", "5%", "28%"]):
        return 0.9

    if "notification" in context.lower() or "section" in context.lower():
        return 0.8

    return 0.6
