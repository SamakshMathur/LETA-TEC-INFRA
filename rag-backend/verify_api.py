import requests
import sys

try:
    print("Testing /api/documents/categories...")
    resp = requests.get("http://127.0.0.1:8000/api/documents/categories")
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
    
    if resp.status_code == 200:
        data = resp.json()
        total = sum(data.values())
        print(f"Total documents found: {total}")
        if total == 0:
            print("FAILURE: Backend returning 0 documents.")
            sys.exit(1)
        else:
            print("SUCCESS: Backend finding documents.")
    else:
        print("FAILURE: API Error.")

except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
