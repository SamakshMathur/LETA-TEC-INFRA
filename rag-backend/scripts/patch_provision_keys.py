"""
patch_provision_keys.py — One-shot metadata patch for production chunks.jsonl

Adds missing provision_keys to chunks that lack them:
1. IGST Act chunks → IGST_SEC_X (extracted from "Section X" in text)
2. CGST Rules chunks → CGST_RUL_X (extracted from "Rule X" in text)

These keys were missing from the V2.0 ingestion, causing authority lookup to
fail for all IGST section and CGST rule checks.

Run:
    python scripts/patch_provision_keys.py

Writes patched output to data/chunks/chunks.jsonl (in-place, with backup).
"""
import json, re, shutil
from pathlib import Path

ROOT        = Path(__file__).parent.parent
CHUNKS_PATH = ROOT / "data/chunks/chunks.jsonl"
BACKUP_PATH = ROOT / "data/chunks/chunks.jsonl.pre_patch_bak"

# ── Regexes to extract provision numbers ─────────────────────────────────────

# Section X / Section X of the ... Act
_SEC_RE = re.compile(r'\bsection\s+(\d+)\b', re.IGNORECASE)

# Sub-section e.g. "Section 16(1)" — we want just the section number
# Rule X / Rule No. X / Rule - X (CGST Rules format uses "Rule - 28")
_RULE_RE   = re.compile(r'\brule\s*[-–]?\s*(\d+)\b', re.IGNORECASE)
# Filename-based: "rule 28.pdf" → 28
_FILE_RULE_RE = re.compile(r'\brule\s+(\d+)\.pdf', re.IGNORECASE)
# Filename-based for IGST Act: "section 16" or "sec 16" in filename
_FILE_SEC_RE  = re.compile(r'\bsec(?:tion)?\s+(\d+)\.pdf', re.IGNORECASE)

# ── Category detection (mirrors retriever.py) ─────────────────────────────────
def _is_igst_act(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    return "igst acts" in r or "igst act" in r.split("/")[-1] if r else False

def _is_cgst_rules(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    return "cgst rules" in r

def _is_igst_rules(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    return "igst rules" in r

# ── Extract section numbers from text ─────────────────────────────────────────
def _extract_sections(text: str, prefix: str, max_sec: int = 60) -> list:
    """Return IGST_SEC_X / CGST_SEC_X keys for sections mentioned in text."""
    nums = {int(m.group(1)) for m in _SEC_RE.finditer(text)}
    return [f"{prefix}_{n}" for n in sorted(nums) if 1 <= n <= max_sec]

def _extract_rules(text: str, fname: str, prefix: str, max_rule: int = 170) -> list:
    """Return CGST_RUL_X / IGST_RUL_X keys for rules mentioned in text or filename."""
    nums: set = set()
    # From filename (most reliable: "rule 28.pdf")
    m = _FILE_RULE_RE.search(fname)
    if m:
        nums.add(int(m.group(1)))
    # From text body ("Rule - 28" / "Rule 28" patterns)
    nums.update(int(m.group(1)) for m in _RULE_RE.finditer(text))
    return [f"{prefix}_{n}" for n in sorted(nums) if 1 <= n <= max_rule]

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Reading {CHUNKS_PATH} …")
    chunks = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    print(f"  {len(chunks)} chunks loaded")

    # Backup
    shutil.copy2(CHUNKS_PATH, BACKUP_PATH)
    print(f"  Backup saved to {BACKUP_PATH}")

    igst_patched   = 0
    cgst_r_patched = 0
    igst_r_patched = 0
    total_keys_added = 0

    for chunk in chunks:
        meta = chunk.get("metadata", {}) or {}
        rel  = chunk.get("rel_path") or meta.get("rel_path", "")
        text = chunk.get("text", "")

        # ── IGST Act chunks ───────────────────────────────────────────────────
        if _is_igst_act(rel):
            existing = set(meta.get("provision_keys", []) or [])
            new_keys = _extract_sections(text, "IGST_SEC", max_sec=30)
            added    = [k for k in new_keys if k not in existing]
            if added:
                meta["provision_keys"] = sorted(existing | set(new_keys))
                chunk["metadata"] = meta
                igst_patched   += 1
                total_keys_added += len(added)

        # ── CGST Rules chunks ─────────────────────────────────────────────────
        elif _is_cgst_rules(rel):
            fname    = rel.replace("\\", "/").split("/")[-1]
            existing = set(meta.get("provision_keys", []) or [])
            new_keys = _extract_rules(text, fname, "CGST_RUL", max_rule=170)
            added    = [k for k in new_keys if k not in existing]
            if added:
                meta["provision_keys"] = sorted(existing | set(new_keys))
                chunk["metadata"] = meta
                cgst_r_patched   += 1
                total_keys_added  += len(added)

        # ── IGST Rules chunks ─────────────────────────────────────────────────
        elif _is_igst_rules(rel):
            fname    = rel.replace("\\", "/").split("/")[-1]
            existing = set(meta.get("provision_keys", []) or [])
            new_keys = _extract_rules(text, fname, "IGST_RUL", max_rule=50)
            new_keys += _extract_sections(text, "IGST_SEC", max_sec=30)
            added    = [k for k in new_keys if k not in existing]
            if added:
                meta["provision_keys"] = sorted(existing | set(new_keys))
                chunk["metadata"] = meta
                igst_r_patched   += 1
                total_keys_added  += len(added)

    print(f"\nPatched:")
    print(f"  IGST Act chunks:   {igst_patched} / 59")
    print(f"  CGST Rules chunks: {cgst_r_patched} / 550")
    print(f"  IGST Rules chunks: {igst_r_patched} / 33")
    print(f"  Total keys added:  {total_keys_added}")

    # Write patched file
    print(f"\nWriting patched chunks to {CHUNKS_PATH} …")
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print("  Done.")

    # Verify spot-check
    print("\nVerification spot-check:")
    target = ["IGST_SEC_16", "IGST_SEC_5", "IGST_SEC_2", "CGST_RUL_28", "CGST_RUL_42"]
    from collections import Counter
    found = Counter()
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            pk = c.get("metadata", {}).get("provision_keys", []) or []
            for t in target:
                if t in pk:
                    found[t] += 1
    for t in target:
        print(f"  {t:20s}: {found[t]} chunks")

if __name__ == "__main__":
    main()
