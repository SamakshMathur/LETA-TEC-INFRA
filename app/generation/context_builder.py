def build_context(chunks: list[dict]) -> str:
    context = []
    for c in chunks:
        context.append(
            f"[Source: {c['source']}, Page: {c.get('page')}]\n{c['text']}"
        )
    return "\n\n".join(context)