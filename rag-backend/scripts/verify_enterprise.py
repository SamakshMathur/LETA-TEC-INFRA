import sys
import os

print("--- Verifying Enterprise Legal AI Setup ---")

# 1. Check Dependencies
try:
    import flashrank
    print("✅ FlashRank installed")
except ImportError:
    print("❌ FlashRank NOT installed")

try:
    import diskcache
    print("✅ DiskCache installed")
except ImportError:
    print("❌ DiskCache NOT installed")

try:
    import reportlab
    print("✅ ReportLab installed")
except ImportError:
    print("❌ ReportLab NOT installed")

# 2. Check Config
try:
    from app.config import LLM_MODEL, EMBEDDING_PROVIDER, EMBEDDING_MODEL, VECTOR_DIM, RERANKING_MODEL
    print(f"✅ Config Loaded:")
    print(f"   - LLM: {LLM_MODEL}")
    print(f"   - Embedding: {EMBEDDING_PROVIDER} ({EMBEDDING_MODEL}, {VECTOR_DIM} dim)")
    print(f"   - Reranker: {RERANKING_MODEL}")
except Exception as e:
    print(f"❌ Config Error: {e}")

# 3. Check Modules
try:
    from app.embeddings.embedder import embed_texts
    print("✅ Embedder Module OK")
except Exception as e:
    print(f"❌ Embedder Import Error: {e}")

try:
    from app.retrieval.retriever import Retriever
    print("✅ Retriever Module OK")
except Exception as e:
    print(f"❌ Retriever Import Error: {e}")

try:
    from app.generation.pdf_report import PDFReportGenerator
    print("✅ PDF Generator Module OK")
except Exception as e:
    print(f"❌ PDF Generator Import Error: {e}")

print("--- Verification Complete ---")
