import os
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("RAG_INFORMATION_DATABASE")
DOCS_JSONL = Path("data/chunks/documents.jsonl")

SUPPORTED_EXTS = {".pdf", ".docx", ".xlsx", ".xls", ".doc", ".php"}

# Step 1: Get all files in the database
all_files = set()
folder_counts = defaultdict(int)
for root, _, files in os.walk(DATA_DIR):
    if "__MACOSX" in root:
        continue
    for f in files:
        if f.startswith(".") or f.startswith("._"):
            continue
        fpath = Path(root) / f
        if fpath.suffix.lower() in SUPPORTED_EXTS:
            rel = str(fpath.relative_to(DATA_DIR.parent))
            all_files.add(rel)
            # Top-level folder
            parts = fpath.relative_to(DATA_DIR).parts
            folder = parts[0] if parts else "root"
            folder_counts[folder] += 1

print(f"\nTotal supported files in database: {len(all_files)}")

# Step 2: Get all indexed sources from documents.jsonl
indexed_files = set()
with open(DOCS_JSONL, encoding="utf-8", errors="ignore") as f:
    for line in f:
        try:
            data = json.loads(line)
            src = data.get("metadata", {}).get("source")
            if src:
                indexed_files.add(src)
        except:
            continue

print(f"Unique files indexed in documents.jsonl: {len(indexed_files)}")

# Step 3: Find what's missing
missing = all_files - indexed_files
missing_by_folder = defaultdict(list)
for m in missing:
    parts = Path(m).relative_to(DATA_DIR).parts
    folder = parts[0] if parts else "root"
    missing_by_folder[folder].append(m)

print(f"\nMissing files (not yet indexed): {len(missing)}")
print("\n--- Missing by Folder ---")
for folder in sorted(missing_by_folder):
    print(f"  [{len(missing_by_folder[folder])} files] {folder}")

print("\n--- Folders Fully Indexed ---")
for folder in sorted(folder_counts):
    in_folder = [f for f in indexed_files if f"\\{folder}\\" in f or f"/{folder}/" in f]
    total = folder_counts[folder]
    indexed_count = len(set(in_folder))
    if folder not in missing_by_folder:
        print(f"  ✅ {folder} — {total}/{total} files")
    else:
        missing_count = len(missing_by_folder[folder])
        print(f"  ⚠️  {folder} — {total - missing_count}/{total} files ({missing_count} missing)")
