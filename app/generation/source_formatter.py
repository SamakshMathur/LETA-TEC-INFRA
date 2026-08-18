from pathlib import Path


def format_sources(chunks: list) -> str:
    """
    Create a clean, human-readable source summary.
    """
    seen = set()
    sources = []

    for c in chunks:
        src = c.get("source")
        page = c.get("page")

        if not src:
            continue

        key = (src, page)
        if key in seen:
            continue

        seen.add(key)

        name = Path(src).name
        if page:
            sources.append(f"{name} (Page {page})")
        else:
            sources.append(name)

    if not sources:
        return "Source: Not specified"

    return "Source: " + "; ".join(sources)
