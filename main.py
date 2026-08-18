import uvicorn
import sys
import os

print(f"Ref CWD: {os.getcwd()}")
try:
    print(f"Ref LS: {os.listdir('.')}")
    if 'rag-backend' in os.listdir('.'):
         print(f"Ref LS (rag-backend): {os.listdir('rag-backend')}")
    if 'app' in os.listdir('.'):
         print(f"Ref LS (app): {os.listdir('app')}")
except Exception as e:
    print(f"Ref LS Error: {e}")
print(f"Ref Path: {sys.path}")

try:
    import app
    print(f"Ref app found: {app}")
except ImportError as e:
    print(f"Ref app import error: {e}")

from app.api.app import app
from app.utils.s3_sync import sync_from_s3

@app.on_event("startup")
async def startup_event():
    print("🚀 App starting... Syncing data from S3")
    sync_from_s3()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
