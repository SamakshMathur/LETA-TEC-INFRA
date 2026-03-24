from diskcache import Cache
from app.config import CACHE_DIR
import shutil
import os

print(f"Clearing Cache at {CACHE_DIR}...")
try:
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
        print("Cache directory removed.")
    else:
        print("Cache directory not found.")
        
    # Recreate empty
    os.makedirs(CACHE_DIR, exist_ok=True)
    print("Empty cache directory created.")
    
except Exception as e:
    print(f"Error clearing cache: {e}")
