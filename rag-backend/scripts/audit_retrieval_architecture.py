import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import get_retriever
from app.retrieval.query_refiner import extract_query_topic
import json

def audit_retrieval():
    print("--- LETA TWO-STAGE RETRIEVAL AUDIT ---")
    retriever = get_retriever()
    
    query = "Is ITC allowed on motor vehicles used for passenger transport?"
    print(f"\nQuery: {query}")
    
    # 1. Topic & Subtopic Detection Audit
    topic_info = extract_query_topic(query)
    topic = topic_info.get("topic", "General") if isinstance(topic_info, dict) else topic_info
    subtopic = topic_info.get("subtopic", "N/A") if isinstance(topic_info, dict) else "N/A"
    print(f"Detected Topic: {topic}")
    print(f"Detected Subtopic: {subtopic}")
    
    # 2. Retrieval Audit
    results = retriever.search(query, top_k=5)
    
    print("\nTop 5 Results:")
    for i, res in enumerate(results):
        source = res.get("rel_path", res.get("source", "unknown"))
        is_statute_first = res.get("_is_statute_first", False)
        score = res.get("_final_legal_score", "N/A")
        components = res.get("_debug_components", {})
        
        marker = "[LAYER 1]" if is_statute_first else "[LAYER 2]"
        print(f"{i+1}. {marker} [{source}] (Score: {score:.4f} if score != 'N/A' else 'N/A')")
        print(f"   Structural Part: {res.get('structure', res.get('structural_part', 'N/A'))}")
        print(f"   Topic: {res.get('topic', 'N/A')}")
        if components:
            print(f"   Breakdown: Semantic={components['semantic']:.2f}, Legal={components['legal']:.2f}, Topic={components['topic']:.2f}")
    
    # Validation Logic
    best_source = results[0].get("rel_path", "").lower()
    # Validation Logic
    best_source = results[0].get("rel_path", "").lower()
    if "act" in best_source:
        print("\n[PASSED] VERIFICATION SUCCESS: Statutory Act ranked #1.")
    else:
        print("\n[WARNING] VERIFICATION ALERT: Act not at #1.")

if __name__ == "__main__":
    audit_retrieval()
