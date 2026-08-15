#!/usr/bin/env python3
"""
P3 Provision-Key Patch — IGST Act chunks
=========================================
Patches chunks.jsonl IN-PLACE to add correct CGST_SEC_* provision keys to
IGST Act chunks that were missed or mis-tagged during ingestion.

Root cause: normalize_citation() in legal_parser.py always uses CGST_ prefix
regardless of which Act the chunk comes from; IGST-specific provisions like
the Section 2 definitions block end up with provisions=[] (untagged).

What this script fixes:
  1. IGST Section 2 definitions (intermediary, export of services, etc.)
     → adds CGST_SEC_2 to chunks from igst/ paths whose text matches
       the Section 2 definitions pattern
  2. IGST Section 13 (place of supply – services outside India)
     → adds CGST_SEC_13 to chunks from igst/ paths whose text matches
       the POS pattern but were mis-tagged as CGST_SEC_45A or untagged
  3. IGST Section 2(6) export of services definition
     → ensures chunks with "convertible foreign exchange" get CGST_SEC_2

No FAISS rebuild is required — only provision_index is affected (rebuilt
from chunks.jsonl at Retriever startup).

Run from rag-backend/:
    python scripts/patch_igst_provisions.py
"""
import json
import re
import shutil
from pathlib import Path

CHUNKS = Path(__file__).parent.parent / "data" / "chunks" / "chunks.jsonl"
BACKUP = CHUNKS.with_suffix(".jsonl.pre_p3_patch.bak")

# ── patterns that identify IGST Section 2 definitions chunks ─────────────────
_SEC2_PATTERNS = [
    re.compile(r'\bintermediary\b', re.IGNORECASE),
    re.compile(r'convertible foreign exchange', re.IGNORECASE),
    re.compile(r'export of services.*?conditions', re.IGNORECASE | re.DOTALL),
    re.compile(r'\(\s*13\s*\)\s+"intermediary"', re.IGNORECASE),
    re.compile(r'"intermediary"\s+means', re.IGNORECASE),
    # Definitions list pattern — sequential numbered defs typical of Sec 2
    re.compile(r'\(\s*(?:6|7|8|12|13|14|15|16|17|18|19|20)\s*\)\s+"', re.IGNORECASE),
]

# ── patterns that identify IGST Section 13 (POS for cross-border services) ───
_SEC13_PATTERNS = [
    re.compile(r'place of supply of services where location of supplier.{0,60}outside india', re.IGNORECASE | re.DOTALL),
    re.compile(r'location of supplier or location of recipient is outside', re.IGNORECASE),
    re.compile(r'section\s+13.*?outside india', re.IGNORECASE | re.DOTALL),
]

# ── IGST path detector ────────────────────────────────────────────────────────
def _is_igst_path(rp: str) -> bool:
    rp = rp.lower().replace("\\", "/")
    return "igst" in rp or "integrated" in rp

def _matches_any(text: str, patterns: list) -> bool:
    for p in patterns:
        if p.search(text):
            return True
    return False

def patch():
    if not CHUNKS.exists():
        print(f"ERROR: chunks.jsonl not found at {CHUNKS}")
        return

    # Backup
    shutil.copy2(CHUNKS, BACKUP)
    print(f"Backed up to {BACKUP.name}")

    updated = 0
    total = 0
    sec2_added = 0
    sec13_added = 0

    patched_lines = []
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            total += 1
            try:
                c = json.loads(line)
                rp = (c.get("rel_path") or c.get("metadata", {}).get("rel_path", ""))
                text = (c.get("content") or c.get("text") or "")

                if not _is_igst_path(rp):
                    patched_lines.append(line)
                    continue

                meta = c.get("metadata") or {}
                provs = list(meta.get("provisions", []))
                cits  = list(meta.get("citations",  []))
                changed = False

                # ── Fix 1: IGST Section 2 definitions ─────────────────────────
                if _matches_any(text, _SEC2_PATTERNS) and "CGST_SEC_2" not in provs:
                    provs.append("CGST_SEC_2")
                    cits.append("CGST_SEC_2")
                    changed = True
                    sec2_added += 1

                # ── Fix 2: IGST Section 13 (POS services cross-border) ────────
                if _matches_any(text, _SEC13_PATTERNS) and "CGST_SEC_13" not in provs:
                    provs.append("CGST_SEC_13")
                    cits.append("CGST_SEC_13")
                    changed = True
                    sec13_added += 1

                if changed:
                    meta["provisions"] = list(dict.fromkeys(provs))  # dedup
                    meta["citations"]  = list(dict.fromkeys(cits))
                    c["metadata"] = meta
                    patched_lines.append(json.dumps(c, ensure_ascii=False) + "\n")
                    updated += 1
                else:
                    patched_lines.append(line)

            except Exception as e:
                patched_lines.append(line)  # keep original on error

    # Write patched file
    with CHUNKS.open("w", encoding="utf-8") as f:
        f.writelines(patched_lines)

    print(f"Patch complete.")
    print(f"  Total chunks       : {total:,}")
    print(f"  Chunks patched     : {updated}")
    print(f"  CGST_SEC_2 added   : {sec2_added}")
    print(f"  CGST_SEC_13 added  : {sec13_added}")
    print()
    print("Restart the retriever (or re-run regression) to pick up new provision keys.")
    print("FAISS index does NOT need rebuilding — only provision_index is affected.")


if __name__ == "__main__":
    patch()
