def generate_answer(question: str, context: str) -> str:
    """
    Deterministic, demo-safe answer generator.
    Uses retrieved context only.
    """

    if not context or context.strip() == "":
        return "The answer is not available in the provided documents."

    # Simple conclusion-first formatting
    lines = context.strip().split("\n")

    summary = []
    for line in lines:
        if len(line.strip()) > 30:
            summary.append(line.strip())
        if len(summary) == 3:
            break

    if not summary:
        return "The answer is not available in the provided documents."

    return (
        "Based on the documents:\n"
        + " ".join(summary)
    )
