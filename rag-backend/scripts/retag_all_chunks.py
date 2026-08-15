#!/usr/bin/env python3
"""
LETA GST — Full Corpus Re-tagger
=================================
Fixes the normalize_citation() bug that stamped every provision key with
'CGST_' regardless of source act.  Runs over all 64,378 chunks WITHOUT
touching FAISS vectors (text content unchanged — only metadata is fixed).

What this script does
---------------------
1. Detects source act for every chunk from its rel_path:
     igst/...              → IGST
     act/igst.docx         → IGST
     igst/igst act.pdf     → IGST
     utgst/...             → UTGST
     act/cgst act.docx     → CGST
     rules/...             → CGST  (CGST Rules 2017)
     circulars/...         → CGST  (CBIC circulars cite CGST sections)
     notification/...      → CGST or IGST (detected from filename)
     faqs/, icai/, aar/    → CGST  (default; text-hint override applies)
     export/...            → CGST  (CBIC export circulars)

2. Re-extracts citations from chunk text using improved patterns:
     Section 9(3)  → CGST_SEC_9    (base number only — sub-clauses stripped)
     Section 2(6)  → IGST_SEC_2    (when chunk is from IGST Act)
     Rule 42       → CGST_RUL_42
     Circular No. 199/19/2023 → CIRCULAR_199
     Circular filename pattern → CIRCULAR_N

3. Merges new keys with existing ones:
     • IGST source chunks: CGST_SEC_X → IGST_SEC_X (the core bug fix)
     • CGST source chunks: existing CGST tags preserved + new ones added
     • Custom keys ALWAYS preserved regardless of source
       (CGST_SEC_9_RCM, CGST_SEC_9_ADVOCATE, etc.)

4. Writes corrected chunks.jsonl (both top-level and metadata.provisions).

5. Provision index rebuilds automatically on next server restart from the
   corrected file.  FAISS rebuild NOT required.

Tested on: 64,378 chunks, ~118 MB chunks.jsonl
Runtime:   ~8–12 minutes on CPU (pure JSON I/O + regex, no GPU needed)
"""

import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

# ─── Paths ────────────────────────────────────────────────────────────────────
CHUNKS_FILE  = Path(__file__).resolve().parent.parent / "data" / "chunks" / "chunks.jsonl"
BACKUP_FILE  = CHUNKS_FILE.with_name("chunks.pre_retag.bak")
REPORT_FILE  = CHUNKS_FILE.with_name("retag_report.json")

# ─── Custom provision keys to ALWAYS preserve (never rename, never remove) ────
# These were manually created to fix specific ingestion gaps and are intentional.
CUSTOM_PRESERVE: set[str] = {
    "CGST_SEC_9_RCM",
    "CGST_SEC_9_ADVOCATE",
}
# Any provision key matching this pattern is a custom sub-key → preserve
_CUSTOM_SUFFIX_RE = re.compile(
    r'^(CGST|IGST|UTGST|SGST)_(SEC|RUL)_\d+[A-Z]*_[A-Z]',
    re.IGNORECASE,
)

def _is_custom_key(key: str) -> bool:
    return key in CUSTOM_PRESERVE or bool(_CUSTOM_SUFFIX_RE.match(key))


# ─── Source-act detection from rel_path ───────────────────────────────────────
# Maps path patterns → act prefix used when normalising "Section X" citations.

def detect_act_prefix(rel_path: str, text: str = "") -> str:
    """
    Returns 'IGST', 'UTGST', or 'CGST' based on the chunk's source document.
    CGST is the safe default for all mixed/unknown sources (circulars, FAQs, etc.)
    because the vast majority of GST practice references CGST sections.
    """
    path = rel_path.lower().replace("\\", "/")

    # ── Definitive IGST sources ───────────────────────────────────────────────
    # Top-level igst/ folder OR any file whose name explicitly says igst act/rules
    if (
        path.startswith("igst/")
        or path.startswith("act/igst")          # act/igst.docx
        or "/igst act" in path
        or "igst act.pdf" in path
        or "igst act.docx" in path
        or "igst.docx" in path
        or "section-" in path and "/igst" in path   # igst/section-13_igst.pdf
        or "igst_act" in path
    ):
        return "IGST"

    # ── UTGST ─────────────────────────────────────────────────────────────────
    if "utgst" in path:
        return "UTGST"

    # ── Notifications: check for "integrated" in filename (IGST Rate notifs) ──
    # e.g. notification_1_2017_integrated_tax_rate.pdf → IGST
    if "notification" in path and ("integrated" in path or "_it_" in path):
        return "IGST"

    # ── Everything else defaults to CGST ──────────────────────────────────────
    # Covers: CGST Act, CGST Rules, CBIC Circulars, Notifications, FAQs, ICAI,
    #         AARs, HC/SC judgments, Sectoral FAQs, Export circulars.
    return "CGST"


# ─── Circular-number extraction from filename ─────────────────────────────────
_CIR_FNAME_PATTERNS = [
    re.compile(r'circular[-_](?:no[-_.]?)?(\d{2,3})', re.IGNORECASE),
    re.compile(r'cir[-_.](?:cgst[-_.])?(\d{2,3})', re.IGNORECASE),
    re.compile(r'cir(?=\d)(\d{2,3})', re.IGNORECASE),
    re.compile(r'circularno[-_.](\d{2,3})', re.IGNORECASE),
    re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE),   # 199-19-2023-gst.pdf
]

def extract_circular_from_path(rel_path: str) -> Optional[str]:
    fname = rel_path.replace("\\", "/").split("/")[-1]
    for pat in _CIR_FNAME_PATTERNS:
        m = pat.search(fname)
        if m:
            return f"CIRCULAR_{m.group(1)}"
    return None


# ─── Citation extraction from text ────────────────────────────────────────────
# Patterns extracted from LegalParser.CITATION_PATTERNS — improved.

_SEC_RE  = re.compile(
    r'(?:Section|Sec\.)\s+(\d+[A-Z]?)(?:\s*\(\d+[A-Z]?\))*(?:\s*\([a-z]+\))*',
    re.IGNORECASE,
)
_RUL_RE  = re.compile(
    r'Rule\s+(\d+[A-Z]?)(?:\s*\(\d+[A-Z]?\))*(?:\s*\([a-z]+\))*',
    re.IGNORECASE,
)
_CIR_TEXT_RE = re.compile(
    r'Circular\s+No\.?\s*(\d{2,3})',
    re.IGNORECASE,
)
_NOTIF_TEXT_RE = re.compile(
    r'Notification\s+No\.?\s*(\d+/\d+(?:-[A-Z\s\(\)]+)?)',
    re.IGNORECASE,
)


def extract_new_provisions(text: str, act_prefix: str, rel_path: str) -> list[str]:
    """
    Re-extract provision keys from chunk text using the CORRECTED prefix.
    Returns a deduplicated list of keys like CGST_SEC_9, IGST_SEC_2, CIRCULAR_199.
    """
    keys: list[str] = []
    seen: set[str] = set()

    def _add(k: str):
        if k and k not in seen:
            seen.add(k)
            keys.append(k)

    # Section citations → base section number only (strip sub-clauses)
    for m in _SEC_RE.finditer(text):
        sec_num = m.group(1).upper()          # e.g. "9", "17", "2", "16A"
        _add(f"{act_prefix}_SEC_{sec_num}")

    # Rule citations
    for m in _RUL_RE.finditer(text):
        rul_num = m.group(1).upper()
        _add(f"CGST_RUL_{rul_num}")            # Rules are always CGST

    # Circular numbers from text
    for m in _CIR_TEXT_RE.finditer(text):
        _add(f"CIRCULAR_{m.group(1)}")

    # Circular number from filename (more reliable than text for circular files)
    cir_from_path = extract_circular_from_path(rel_path)
    if cir_from_path:
        _add(cir_from_path)

    return keys


# ─── Provision list merger ─────────────────────────────────────────────────────

def _translate_key(key: str, from_prefix: str, to_prefix: str) -> str:
    """CGST_SEC_X → IGST_SEC_X etc. Leaves custom suffix keys untouched."""
    if _is_custom_key(key):
        return key
    if key.startswith(f"{from_prefix}_SEC_"):
        return key.replace(f"{from_prefix}_SEC_", f"{to_prefix}_SEC_", 1)
    if key.startswith(f"{from_prefix}_RUL_"):
        return key.replace(f"{from_prefix}_RUL_", f"{to_prefix}_RUL_", 1)
    return key


def merge_provisions(
    existing: list,
    new_keys:  list,
    act_prefix: str,
) -> tuple[list, bool]:
    """
    Merges existing provision list with newly extracted keys.
    Returns (final_list, changed: bool).

    Logic:
    • IGST source (act_prefix='IGST'): translate every CGST_SEC_X → IGST_SEC_X
      in the existing list (fixes the core bug). Custom keys preserved as-is.
    • CGST/UTGST source: existing CGST keys are correct; just union with new keys.
    • Final list is deduplicated, order-preserving.
    """
    existing = [k for k in (existing or []) if k]   # strip None/empty

    if act_prefix == "IGST":
        translated = [_translate_key(k, "CGST", "IGST") for k in existing]
    elif act_prefix == "UTGST":
        translated = [_translate_key(k, "CGST", "UTGST") for k in existing]
    else:
        translated = list(existing)

    merged: list[str] = []
    seen: set[str]    = set()
    for k in translated + new_keys:
        if k and k not in seen:
            seen.add(k)
            merged.append(k)

    changed = merged != existing
    return merged, changed


# ─── Main re-tagger ───────────────────────────────────────────────────────────

def main():
    if not CHUNKS_FILE.exists():
        print(f"ERROR: chunks.jsonl not found at {CHUNKS_FILE}")
        sys.exit(1)

    # Backup
    if not BACKUP_FILE.exists():
        print(f"Backing up → {BACKUP_FILE.name} ...")
        shutil.copy2(CHUNKS_FILE, BACKUP_FILE)
        print("  done.\n")
    else:
        print(f"Backup already exists: {BACKUP_FILE.name}\n")

    # Count lines for progress bar
    print("Counting chunks ...", end=" ", flush=True)
    total_lines = sum(1 for _ in open(CHUNKS_FILE, encoding="utf-8"))
    print(f"{total_lines:,}\n")

    # ── Pass: re-tag ──────────────────────────────────────────────────────────
    stats = {
        "total":          total_lines,
        "changed":        0,
        "igst_fixed":     0,
        "utgst_fixed":    0,
        "new_keys_added": 0,
        "circ_from_path": 0,
        "errors":         0,
        "by_act": {"IGST": 0, "CGST": 0, "UTGST": 0},
    }

    lines_out: list[str] = []
    t0 = time.time()
    report_samples: list[dict] = []

    with open(CHUNKS_FILE, encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh):
            raw_line = raw_line.rstrip("\n")

            # Progress every 5 000 chunks
            if line_no % 5000 == 0:
                elapsed = time.time() - t0
                pct     = line_no / total_lines * 100
                eta     = (elapsed / max(line_no, 1)) * (total_lines - line_no)
                print(f"  [{line_no:6d}/{total_lines}] {pct:5.1f}%  "
                      f"elapsed={elapsed:.0f}s  eta={eta:.0f}s  "
                      f"changed={stats['changed']}", flush=True)

            try:
                chunk = json.loads(raw_line)
            except Exception:
                stats["errors"] += 1
                lines_out.append(raw_line)
                continue

            meta     = chunk.setdefault("metadata", {}) or {}
            rel_path = (chunk.get("rel_path") or meta.get("rel_path") or "").replace("\\", "/")
            text     = chunk.get("content") or chunk.get("text") or ""

            # ── Detect source act ──────────────────────────────────────────
            act_prefix = detect_act_prefix(rel_path, text)
            stats["by_act"][act_prefix] = stats["by_act"].get(act_prefix, 0) + 1

            # ── Get existing provision lists ───────────────────────────────
            top_provs  = list(chunk.get("provisions") or [])
            meta_provs = list(meta.get("provisions")  or [])

            # ── Extract fresh citations from text ─────────────────────────
            new_keys = extract_new_provisions(text, act_prefix, rel_path)

            # Track circular-from-path additions
            cir_path = extract_circular_from_path(rel_path)
            if cir_path and cir_path not in (top_provs + meta_provs):
                stats["circ_from_path"] += 1

            # ── Merge + fix prefix bug ─────────────────────────────────────
            fixed_top,  top_changed  = merge_provisions(top_provs,  new_keys, act_prefix)
            fixed_meta, meta_changed = merge_provisions(meta_provs, new_keys, act_prefix)

            changed = top_changed or meta_changed

            if changed:
                stats["changed"] += 1
                if act_prefix == "IGST":
                    stats["igst_fixed"] += 1
                elif act_prefix == "UTGST":
                    stats["utgst_fixed"] += 1

                # Count truly new keys added vs. just prefix-translated
                added = len(set(fixed_meta) - set(meta_provs))
                stats["new_keys_added"] += added

                # Sample 20 examples for the report
                if len(report_samples) < 20:
                    report_samples.append({
                        "line":      line_no,
                        "rel_path":  rel_path[-70:],
                        "act":       act_prefix,
                        "before":    meta_provs[:6],
                        "after":     fixed_meta[:6],
                    })

                # Write back
                chunk["provisions"]       = fixed_top
                meta["provisions"]        = fixed_meta
                chunk["metadata"]         = meta

            lines_out.append(json.dumps(chunk, ensure_ascii=False))

    # ── Write corrected file ───────────────────────────────────────────────────
    print(f"\nWriting corrected chunks.jsonl ({len(lines_out):,} lines) ...")
    with open(CHUNKS_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines_out))
        if lines_out:
            fh.write("\n")

    elapsed_total = time.time() - t0

    # ── Write report ──────────────────────────────────────────────────────────
    report = {**stats, "elapsed_seconds": round(elapsed_total, 1), "samples": report_samples}
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  RE-TAG COMPLETE")
    print("=" * 65)
    print(f"  Total chunks processed : {stats['total']:>8,}")
    print(f"  Chunks modified        : {stats['changed']:>8,}  ({stats['changed']/stats['total']*100:.1f}%)")
    print(f"  IGST prefix fixes      : {stats['igst_fixed']:>8,}")
    print(f"  UTGST prefix fixes     : {stats['utgst_fixed']:>8,}")
    print(f"  New keys added (net)   : {stats['new_keys_added']:>8,}")
    print(f"  Circular keys (path)   : {stats['circ_from_path']:>8,}")
    print(f"  Parse errors skipped   : {stats['errors']:>8,}")
    print(f"  Elapsed                : {elapsed_total:.0f}s")
    print(f"\n  Chunks by source act:")
    for act, cnt in sorted(stats["by_act"].items()):
        print(f"    {act:6s}: {cnt:>8,}")
    print(f"\n  Report written → {REPORT_FILE.name}")
    print(f"  Backup kept    → {BACKUP_FILE.name}")
    print("\n  ✓  Restart the server — provision index rebuilds automatically.")
    print("=" * 65)


if __name__ == "__main__":
    main()
