def source_priority(source_path: str) -> int:
    """
    Lower number = higher priority in legal authority ordering.

    Priority ladder (1 = authoritative primary source):
      1 — Acts (CGST, IGST, UTGST, Compensation Cess)
      2 — Rules (CGST Rules, IGST Rules, etc.)
      3 — Notifications (rate schedules, exemptions)
      4 — Circulars (CBIC clarifications)
      5 — ICAI / academic commentary
      6 — AAR / Advance Rulings (persuasive, not binding)
      7 — High Court / Supreme Court judgments
      8 — Forms, APL documents
      9 — Excel / schedule files
     10 — Unrecognised

    Fix (2026-08-19): previous version gave AAR priority 1 (above Acts) and
    Rules fell through to priority 10.  Both are now corrected.
    Also handles Database_V2.0 folder naming ("CGST Acts", "CGST Rules 10-08-2026").
    """
    s = source_path.lower()

    # ── Primary legislation ───────────────────────────────────────────────────
    # Match: "act/", "cgst acts", "igst acts", "utgst", plus legacy flat names
    if ("cgst acts" in s or "igst acts" in s or "utgst" in s
            or s.startswith("act/") or "/act/" in s
            or (("cgst" in s or "igst" in s) and "act" in s and "rules" not in s)):
        return 1

    # ── Rules ─────────────────────────────────────────────────────────────────
    # Match: "cgst rules", "igst rules", "rules/", any rules folder
    if "rules" in s:
        return 2

    # ── Notifications ─────────────────────────────────────────────────────────
    if "notification" in s:
        return 3

    # ── Circulars ─────────────────────────────────────────────────────────────
    if "circular" in s:
        return 4

    # ── ICAI / commentary ─────────────────────────────────────────────────────
    if "icai" in s:
        return 5

    # ── AAR / Advance Rulings ─────────────────────────────────────────────────
    if "aar" in s or "advance" in s:
        return 6

    # ── Case law ─────────────────────────────────────────────────────────────
    if "high court" in s or "supreme court" in s:
        return 7

    # ── Forms / APL ───────────────────────────────────────────────────────────
    if "form" in s or "apl" in s:
        return 8

    # ── Excel / schedules ─────────────────────────────────────────────────────
    if "excel" in s or ".xlsx" in s:
        return 9

    return 10
