#!/usr/bin/env python3
"""
P4 patch: Fix CGST Act Section 8 (composite/mixed supply) provision tagging.

Problem: Chunk 1090 (act/cgst act.docx) contains the actual Section 8 text —
"tax liability on composite and mixed supplies" — but is tagged CGST_SEC_9
(ingestion bug). The two chunks correctly tagged CGST_SEC_8 are both just
headers: "section 8 8" (9 chars). They win the statute priority sort but have
no usable content. The substantive Section 8 chunk never surfaces for SUP-002.

Fix: Add CGST_SEC_8 to chunk 1090. With sort key (priority=0, -text_len),
it will rank above the 9-char headers and fill the first slot in the cap.
Also patch chunk 1025 (Section 2(30) composite supply definition, provs=[]).

Confirmed chunk indices from debug_sup002.py:
  1090 - act/cgst act.docx — actual Section 8 content, currently tagged CGST_SEC_9
  1025 - act/cgst act.docx — Section 2(30) composite supply definition, provs=[]
"""
import json, shutil
from pathlib import Path

CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "chunks" / "chunks.jsonl"
BACKUP_FILE = CHUNKS_FILE.with_suffix(".pre_p4_sec8_patch.bak")

# Indices: {idx: (description, keys_to_add)}
TARGETS = {
    1090: ("CGST Act Section 8 content (composite/mixed supply rule)", ["CGST_SEC_8"]),
    1025: ("CGST Act Section 2(30) composite supply definition",        ["CGST_SEC_8"]),
}

if not BACKUP_FILE.exists():
    print(f"Backing up to {BACKUP_FILE.name} ...")
    shutil.copy2(CHUNKS_FILE, BACKUP_FILE)
    print("  done.")
else:
    print(f"Backup already exists: {BACKUP_FILE.name}")

print(f"\nPatching {CHUNKS_FILE.name} ...")
patched = 0
lines_out = []

with open(CHUNKS_FILE, encoding="utf-8") as f:
    for i, line in enumerate(f):
        line = line.rstrip("\n")
        if i in TARGETS:
            try:
                chunk = json.loads(line)
            except Exception:
                lines_out.append(line)
                continue
            meta = chunk.setdefault("metadata", {})
            desc, new_keys = TARGETS[i]
            changed = False
            for key in new_keys:
                for store, field in [(chunk, "provisions"), (meta, "provisions")]:
                    cur = list(store.get(field) or [])
                    if key not in cur:
                        cur.append(key)
                        store[field] = cur
                        changed = True
            if changed:
                patched += 1
                rel = (chunk.get("rel_path") or meta.get("rel_path", "?"))[-60:]
                text = (chunk.get("content") or chunk.get("text") or "")[:120]
                print(f"  [{i:6d}] {desc}")
                print(f"           rel:   {rel}")
                print(f"           provs: {meta.get('provisions')}")
                print(f"           text:  {text!r}")
            lines_out.append(json.dumps(chunk, ensure_ascii=False))
        else:
            lines_out.append(line)

with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines_out))
    if lines_out:
        f.write("\n")

print(f"\nDone. Patched {patched} chunks. Provision index reloads on next startup.")
