import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import get_retriever

def verify():
    print("--- LETA LEGAL RETRIEVAL VERIFICATION ---")
    
    retriever = get_retriever()
    
    test_queries = [
        "What does Section 17(5) of CGST Act say about blocked credit?",
        "Rule 110 of GST Rules regarding appellate tribunal",
        "AAR ruling on thysenkrrup industrial solutions"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 30)
        
        results = retriever.search(query)
        
        if not results:
            print("  Result: [FAILED] No context retrieved.")
            continue
            
        for i, res in enumerate(results[:3]):
            # The metadata is now flattened into the result dict in Retriever.search
            print(f"  [{i+1}] ID: {res.get('chunk_id')}")
            print(f"      Type: {res.get('document_type')} | Law: {res.get('law')}")
            print(f"      Section: {res.get('section')} | Rule: {res.get('rule')}")
            print(f"      Text Snippet: {res['text'][:100]}...")
            print()

if __name__ == "__main__":
    verify()
