import os
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent))

from app.dependencies import get_retriever
from app.generation.context_builder import build_context
from app.generation.synthesizer import synthesize_answer
from app.generation.rules_engine import rules_engine

def verify_fix():
    print("Initializing Retriever...")
    retriever = get_retriever()
    
    query = "GST applicability on reward points"
    print(f"\nQuerying: {query}")
    
    # 1. Retrieve
    chunks = retriever.search(query=query, top_k=5)
    context = build_context(chunks)
    
    # 2. Generate
    print("\nGenerating Answer (this may take a moment with o1)...")
    answer = synthesize_answer(query, context)
    
    with open("output_answer.txt", "w", encoding="utf-8") as f:
        f.write(answer)
    
    print("\n--- FINAL ANSWER SAVED TO output_answer.txt ---")

    # Verification checks
    print("\nRunning Verification Checks:")
    
    # Check for sections
    sections_found = [f"{i}." in answer for i in range(1, 11)]
    print(f"10 Sections Found: {all(sections_found)} ({sections_found.count(True)}/10)")
    
    # Check for hallucinations
    hallucination_keywords = ["Rajasthan", "Gujarat", "warehouse"]
    hallucinations = [kw for kw in hallucination_keywords if kw.lower() in answer.lower()]
    if hallucinations:
        print(f"⚠️ HALLUCINATION DETECTED: Found keywords {hallucinations}")
    else:
        print("✅ No known hallucination keywords found.")
        
    # Check for correct context
    context_keywords = ["reward", "points", "FAQ"]
    found_context = [kw for kw in context_keywords if kw.lower() in answer.lower()]
    print(f"Context grounded in reward points: {len(found_context)}/{len(context_keywords)} keywords found ({found_context})")

if __name__ == "__main__":
    verify_fix()
