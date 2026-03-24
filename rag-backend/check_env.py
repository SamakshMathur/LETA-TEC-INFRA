from dotenv import load_dotenv
import os

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")

if key:
    masked_key = key[:10] + "*" * (len(key) - 10)
    print(f"SUCCESS: Found API Key: {masked_key}")
else:
    print("ERROR: No OPENROUTER_API_KEY found in environment.")
