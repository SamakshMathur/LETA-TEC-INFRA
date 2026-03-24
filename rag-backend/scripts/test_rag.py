import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.generation.synthesizer import synthesize_answer
from app.retrieval.retriever import Retriever
from app.config import VECTOR_DB_PATH, CHUNKS_PATH

def run_test():
    print("--- Starting RAG Integrity Test ---")
    
    # 1. Check if Vector DB exists
    if not Path(VECTOR_DB_PATH).exists():
        print(f"[WARNING] Vector DB not found at {VECTOR_DB_PATH}. Retrieval will be empty.")
    
    # 2. Init Retriever
    print("Initializing Retriever...")
    retriever = Retriever(Path(VECTOR_DB_PATH), Path(CHUNKS_PATH))
    
    # 3. Test Retrieval
    query = "What is the penalty for not filing GSTR-1?"
    if len(sys.argv) > 1:
        query = sys.argv[1]
    
    print(f"\nTest Query: {query}")
    
    results = retriever.search(query, top_k=3)
    if results:
        print(f"[OK] Retrieval Success! Found {len(results)} chunks.")
        print(f"Top Source: {results[0].get('source')} (Page {results[0].get('page')})")
        context_text = results[0]['text'][:200] + "..."
        print(f"Context Sample: {context_text}")
    else:
        print("[WARN] Retrieval returned 0 results (Expected if DB is empty). Using Mock Context for Generation check.")
        results = [{"text": "Section 122 penalty is Rs. 10,000.", "source": "Test", "page": 1}]
        
    # 4. Test Generation (LLM)
    # We construct context strings
    context = "\n".join([r['text'] for r in results])
    
    print("\nSynthesizing Answer (calling LLM)...")
    try:
        answer = synthesize_answer(query, context)
        print("\n[OK] Generation Success!")
        print("-" * 40)
        print("GENERATED RESPONSE (Preview):")
        print("-" * 40)
        print(answer)
        print("-" * 40)
    except Exception as e:
        print(f"❌ Generation Failed: {e}")

if __name__ == "__main__":
    run_test()
