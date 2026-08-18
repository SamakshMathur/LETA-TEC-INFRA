def source_priority(source_path: str) -> int:
    """
    Lower number = higher priority
    """
    s = source_path.lower()

    if "aar" in s or "advance" in s:
        return 1

    if "act" in s or "notification" in s:
        return 2

    if "circular" in s:
        return 3

    if "form" in s or "apl" in s:
        return 4

    if "excel" in s or ".xlsx" in s:
        return 5

    return 10
