from pathlib import Path

from app.routing.intent_classifier import classify_intent
from app.routing.router import route_query
from app.excel_logic.section_rule_lookup import find_rule_for_section

from app.retrieval.retriever import Retriever
from app.generation.context_builder import build_context
from app.generation.answer import generate_answer


INDEX = Path("vectordb/index.faiss")

retriever = Retriever(
    index_path=INDEX,
    chunks_path=Path("data/chunks/chunks.jsonl")
)

# 1️⃣ Ask question
question = input("Ask your GST question: ")

# 2️⃣ Intent + routing
intent = classify_intent(question)
route = route_query(question)

print("INTENT:", intent)
print("ROUTE:", route)

# 3️⃣ STRUCTURED EXCEL HANDLER (NO FALLBACK)
if route["mode"] == "structured":
    result = find_rule_for_section(question)

    print("\nFINAL ANSWER:\n")

    if result["found"]:
        print(
            f"Rule {result['rule']} applies to Section {result['section']} "
            f"({result['topic']}).\n"
            f"Source: {result['source']}"
        )
    else:
        print(result["message"])

    # 🔒 HARD STOP — NOTHING ELSE RUNS
    raise SystemExit


# 4️⃣ RAG FALLBACK (PDF / DOCX)
chunks = retriever.search(
    question,
    top_k=5,
    allowed_sources=route["use_sources"]
)

context = build_context(chunks)

from app.generation.final_answer import build_final_answer

answer = build_final_answer(question, context, chunks)

from app.generation.confidence import estimate_confidence

confidence = estimate_confidence(context)

print("\nConfidence Score:", round(confidence, 2))


print("\nFINAL ANSWER:\n")
print(answer)
 