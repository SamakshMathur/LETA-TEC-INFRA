from pathlib import Path
from app.retrieval.retriever import Retriever

INDEX = Path("vectordb/index.faiss")

retriever = Retriever(INDEX)

query = "Is GST applicable on cheque bounce penalty?"

results = retriever.search(query, top_k=5)

for r in results:
    print("-" * 40)
    print(f"Source: {r['source']}")
    print(f"Page: {r.get('page')}")