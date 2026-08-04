@echo off
set EMBEDDING_PROVIDER=local
set EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
set VECTOR_DIM=1024
set S3_DATA_BUCKET=gst-rag-data-721082558531
set AWS_DEFAULT_REGION=ap-south-1
cd /d "c:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend"
"c:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\.venv_win\Scripts\python.exe" scripts\ingest_all_to_s3.py >> "c:\Users\HP\Desktop\RAG-20260130T152632Z-3-001\RAG\rag-backend\scripts\ingest_all.log" 2>&1
