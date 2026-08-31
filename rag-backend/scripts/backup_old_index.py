import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# Resolve app root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import CHUNKS_PATH, VECTOR_DB_PATH

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backup") / f"pre_v2_rebuild_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"Target backup directory created: {backup_dir}")

    files_to_backup = [
        Path(CHUNKS_PATH),
        Path(VECTOR_DB_PATH),
        Path(VECTOR_DB_PATH).parent / "index.meta.json",
        Path(VECTOR_DB_PATH).parent / "index_manifest.json"
    ]

    backed_up = 0
    for f in files_to_backup:
        if f.exists():
            dest = backup_dir / f.name
            shutil.copy2(f, dest)
            print(f"Backed up: {f} -> {dest}")
            backed_up += 1
        else:
            print(f"File not found (skipped): {f}")

    print(f"Backup complete. Backed up {backed_up} files successfully to: {backup_dir}")

if __name__ == "__main__":
    main()
