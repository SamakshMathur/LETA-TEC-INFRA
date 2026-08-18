def apply_safety_guards(answer: str, confidence: float, sources: str) -> str:
    """
    Adds safety messaging to the final answer.
    """

    # Very low confidence → refuse politely
    # Very low confidence → refuse politely
    if confidence < 0.45:
        return (
            "⚠️ The system could not determine a reliable answer "
            "based on the provided documents."
        )

    # Medium confidence → warn user
    if confidence < 0.7:
        return (
            f"{answer}\n\n"
            "⚠️ Note: The answer is based on limited information "
            "from the available documents."
        )

    # High confidence → normal output
    return answer
