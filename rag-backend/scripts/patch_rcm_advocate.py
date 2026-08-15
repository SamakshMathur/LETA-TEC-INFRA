#!/usr/bin/env python3
"""
P4b patch: Add CGST_SEC_9_ADVOCATE provision key to advocate+RCM chunks.

CGST_SEC_9_RCM (from patch_rcm_provisions.py) has 6 entries; _PER_KEY_CAP=3
picks the 3 longest — those are the GTA/ICAI chunks (14186,14187,14188).
Advocate chunks (5358, 5400) are at positions 4-5 and never get pinned.

Fix: separate key CGST_SEC_9_ADVOCATE for advocate content only.
Taxonomy "rcm" topic will pin BOTH keys, so GTA AND advocate content surface.

Chunks to patch:
  5358 - FAQ: "advocate providing interstate supply chargeable under reverse charge"
  5400 - sectoral FAQ: "whether legal services provided by advocate"
"""
import json, shutil
from pathlib import Path

CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "chunks" / "chunks.jsonl"

TARGET_INDICES = {
    5358:  "FAQ: advocate under reverse charge",
    5400:  "sectoral FAQ: legal services under RCM",
}
NEW_KEY = "CGST_SEC_9_ADVOCATE"

print(f"Patching {CHUNKS_FILE.name} ...")
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
            top_provs = list(chunk.get("provisions") or [])
            meta_provs = list(meta.get("provisions") or [])
            changed = False
            if NEW_KEY not in top_provs:
                top_provs.append(NEW_KEY); chunk["provisions"] = top_provs; changed = True
            if NEW_KEY not in meta_provs:
                meta_provs.append(NEW_KEY); meta["provisions"] = meta_provs; changed = True
            if changed:
                patched += 1
                desc = TARGET_INDICES[i]
                rel = (chunk.get("rel_path") or meta.get("rel_path", "?"))[-60:]
                print(f"  [{i:6d}] {desc}")
                print(f"           provs now: {meta_provs}")
            lines_out.append(json.dumps(chunk, ensure_ascii=False))
        else:
            lines_out.append(line)

with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines_out))
    if lines_out: f.write("\n")

print(f"\nDone. Patched {patched} chunks with {NEW_KEY}.")
