import sys
import os

# Add the current directory to sys.path so we can import app.*
sys.path.append(os.path.abspath("."))

from app.dependencies import get_retriever
from app.generation.context_builder import build_context
from app.generation.synthesizer import synthesize_answer
from app.routing.router import route_query

def main():
    question = "services provided by indian branch office to foreign head office qualify as export?"
    print(f"Question: {question}")
    
    # 1. Routing & Retrieval
    print("Retrieving context...")
    route = route_query(question)
    retriever = get_retriever()
    chunks = retriever.search(
        query=question,
        top_k=20,
        allowed_sources=route["use_sources"]
    )
    
    # 2. Context Building
    context = build_context(chunks)
    
    # 3. Answer Generation
    print("Generating answer from LETA (Claude)...")
    answer = synthesize_answer(question, context)
    
    print("\n\n--- LETA ANSWER ---")
    print(answer)
    print("-------------------\n")
    
    with open("leta_answer.md", "w", encoding="utf-8") as f:
        f.write(answer)

if __name__ == "__main__":
    main()
