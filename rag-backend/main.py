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
print("Ref: Imported app.api.app")
try:
    from app.utils.s3_sync import sync_from_s3
    print("Ref: Imported sync_from_s3")
except ImportError as e:
    print(f"Ref: Error importing sync_from_s3: {e}")
    # Define dummy function if missing
    def sync_from_s3(): pass

@app.on_event("startup")
async def startup_event():
    print("App starting... Syncing data from S3 (Skipping for Local Dev)")
    # try:
    #     sync_from_s3()
    # except Exception as e:
    #     print(f"S3 Sync Skipped: {e}")

if __name__ == "__main__":
    print("Ref: Starting uvicorn.run...")
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000
        )
    except Exception as e:
        print(f"Ref: Uvicorn crashed: {e}")
        import traceback
        traceback.print_exc()
