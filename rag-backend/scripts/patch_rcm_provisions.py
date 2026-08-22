#!/usr/bin/env python3
"""
P4 patch: Add CGST_SEC_9_RCM provision key to GTA and advocate RCM chunks.

Problem: CGST_SEC_9 has 709 entries; _PER_KEY_CAP=3 means only top-3 statutes
get pinned (Section 9 header/levy text), burying the FAQ/ICAI chunks that
actually contain "goods transport agency" and "advocate" under reverse charge.

Fix: A new key CGST_SEC_9_RCM with 5-6 targeted chunks. The authority taxonomy
"rcm" topic will pin this key, so all GTA+advocate chunks surface in top-15.

Target chunks identified via debug_find_rcm_notif.py:
  5403  - sectoral FAQs: "reverse charge under section 9(3)" + GTA
  14186 - ICAI Vol-1:   GTA analysis, already has CGST_SEC_9
  14187 - ICAI Vol-1:   GTA forward-charge option, provs=[]
  14188 - ICAI Vol-1:   GTA amendment text
  5358  - FAQs:         "advocate" + "reverse charge" + registration
  5400  - sectoral FAQs: "legal services" under RCM
"""
import json, shutil
from pathlib import Path

CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "chunks" / "chunks.jsonl"
BACKUP_FILE = CHUNKS_FILE.with_suffix(".pre_p4_rcm_patch.bak")

# Chunk indices to patch: (index, description)
TARGET_INDICES = {
    5403:  "sectoral FAQ: GTA under reverse charge section 9(3)",
    14186: "ICAI Vol-1: GTA reverse charge analysis",
    14187: "ICAI Vol-1: GTA forward charge option",
    14188: "ICAI Vol-1: GTA amendments",
    5358:  "FAQ: advocate under reverse charge registration",
    5400:  "sectoral FAQ: legal services under RCM",
}

NEW_KEY = "CGST_SEC_9_RCM"

# --- Backup ---
if not BACKUP_FILE.exists():
    print(f"Backing up to {BACKUP_FILE.name} ...")
    shutil.copy2(CHUNKS_FILE, BACKUP_FILE)
    print("  backup done.")
else:
    print(f"Backup already exists: {BACKUP_FILE.name}")

# --- Patch ---
print(f"\nPatching {CHUNKS_FILE.name} ...")
patched = 0
lines_out = []

with open(CHUNKS_FILE, encoding="utf-8") as f:
    for i, line in enumerate(f):
        line = line.rstrip("\n")
        if i in TARGET_INDICES:
            try:
                chunk = json.loads(line)
            except Exception:
                lines_out.append(line)
                continue

            meta = chunk.setdefault("metadata", {})

            # Get current provisions (both top-level and metadata)
            top_provs = chunk.get("provisions") or []
            meta_provs = meta.get("provisions") or []

            # Add new key if not already present
            changed = False
            if NEW_KEY not in top_provs:
                top_provs = list(top_provs) + [NEW_KEY]
                chunk["provisions"] = top_provs
                changed = True
            if NEW_KEY not in meta_provs:
                meta_provs = list(meta_provs) + [NEW_KEY]
                meta["provisions"] = meta_provs
                changed = True

            if changed:
                patched += 1
                desc = TARGET_INDICES[i]
                rel = (chunk.get("rel_path") or meta.get("rel_path", "?"))[-60:]
                print(f"  [{i:6d}] {desc}")
                print(f"           rel: {rel}")
                print(f"           provisions now: {meta_provs}")

            lines_out.append(json.dumps(chunk, ensure_ascii=False))
        else:
            lines_out.append(line)

with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines_out))
    if lines_out:
        f.write("\n")

print(f"\nDone. Patched {patched} chunks with {NEW_KEY}.")
print("Provision index will reload on next retriever startup.")
