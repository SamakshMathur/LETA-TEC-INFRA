import os
import sys
from pathlib import Path
import json

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import VECTOR_DB_PATH, CHUNKS_PATH
from app.retrieval.retriever import Retriever
from app.retrieval.query_refiner import classify_topic_rules

GOLDEN_QUERIES = [
    {
        "query": "What is the GST treatment of secondary or post-sale discounts?",
        "expected_topic": "Valuation",
        "expected_subtopic": "Discounts",
        "expected_provisions": ["CGST_SEC_15"]
    },
    {
        "query": "What are the conditions under Section 15(3) of the CGST Act for excluding discounts from taxable value?",
        "expected_topic": "Valuation",
        "expected_subtopic": "Discounts",
        "expected_provisions": ["CGST_SEC_15"]
    },
    {
        "query": "Can a post-supply discount reduce taxable value under GST through a credit note?",
        "expected_topic": "Valuation",
        "expected_subtopic": "Credit Note",
        "expected_provisions": ["CGST_SEC_15", "CGST_SEC_34"]
    },
    {
        "query": "Can input tax credit be claimed on motor vehicles used for business?",
        "expected_topic": "ITC",
        "expected_subtopic": "Blocked ITC",
        "expected_provisions": ["CGST_SEC_17"]
    },
    {
        "query": "What is the GST treatment of exports without payment of tax?",
        "expected_topic": "Export",
        "expected_subtopic": "Without payment of tax",
        "expected_provisions": ["IGST_SEC_16"]
    }
]

def run_scorecard():
    # Load retriever
    print("Initializing Retriever...")
    retriever = Retriever(Path(VECTOR_DB_PATH), Path(CHUNKS_PATH))
    if not retriever.index:
        print("ERROR: FAISS index not loaded.")
        sys.exit(1)

    print("\nRunning Golden Queries Evaluation...\n")
    print(f"{'Query':<80} | {'Topic':<10} | {'Subtopic':<20} | {'Recall@5':<8} | {'Recall@10':<9} | {'Recall@20':<9} | {'MRR':<5}")
    print("-" * 155)

    all_r5 = []
    all_r10 = []
    all_r20 = []
    all_mrr = []

    for item in GOLDEN_QUERIES:
        q = item["query"]
        expected_topic = item["expected_topic"]
        expected_subtopic = item["expected_subtopic"]
        expected_provs = set(item["expected_provisions"])

        # Predict topic using rule-based classification
        topic_info = classify_topic_rules(q)
        pred_topic = topic_info.get("topic") or "General"
        pred_subtopic = topic_info.get("subtopic") or "None"

        # Search retriever
        # Mock advanced_queries dict with rule-based topic
        advanced_queries = {
            "queries": [q],
            "hyde_document": "",
            "topic": pred_topic,
            "subtopic": topic_info.get("subtopic")
        }

        # skip_rerank is false so we test full pipeline retrieval correctness!
        results = retriever.search(
            query=q,
            top_k=20,
            advanced_queries=advanced_queries,
            skip_rerank=False
        )

        # Calculate metrics
        match_ranks = []

        def is_chunk_match(res, expected_set):
            rel_path = res.get("rel_path") or res.get("metadata", {}).get("rel_path") or ""
            provs = res.get("provisions") or res.get("metadata", {}).get("provisions") or []

            # Special case for IGST_SEC_16 since it is stored as CGST_SEC_16 inside IGST.docx
            if "IGST_SEC_16" in expected_set:
                if ("CGST_SEC_16" in provs or "IGST_SEC_16" in provs) and "igst" in rel_path.lower():
                    return True

            return bool(set(provs) & expected_set)

        for idx, res in enumerate(results):
            rank = idx + 1
            if is_chunk_match(res, expected_provs):
                match_ranks.append(rank)

        # Recall@K
        # Unique expected provisions found in top K
        def calc_recall(k):
            matched_count = 0
            for exp in expected_provs:
                exp_set = {exp}
                found = False
                for res in results[:k]:
                    if is_chunk_match(res, exp_set):
                        found = True
                        break
                if found:
                    matched_count += 1
            return matched_count / len(expected_provs) if expected_provs else 0.0

        r5 = calc_recall(5)
        r10 = calc_recall(10)
        r20 = calc_recall(20)

        # MRR (Mean Reciprocal Rank)
        # 1 / rank of the first matching chunk
        mrr = 1.0 / match_ranks[0] if match_ranks else 0.0

        all_r5.append(r5)
        all_r10.append(r10)
        all_r20.append(r20)
        all_mrr.append(mrr)

        short_q = q if len(q) <= 78 else q[:75] + "..."
        topic_match_str = f"{pred_topic}"
        subtopic_match_str = f"{pred_subtopic}"
        print(f"{short_q:<80} | {topic_match_str:<10} | {subtopic_match_str:<20} | {r5:<8.2f} | {r10:<9.2f} | {r20:<9.2f} | {mrr:<5.2f}")

        # Diagnostic output
        print("\n  Top 5 retrieved chunks:")
        for idx, res in enumerate(results[:5]):
            rel_path = res.get("rel_path") or res.get("metadata", {}).get("rel_path") or "Unknown"
            provs = res.get("provisions") or res.get("metadata", {}).get("provisions") or []
            score = res.get("_rerank_score") or res.get("_debug_score") or 0.0
            text_preview = (res.get("text", "")[:100] + "...").replace("\n", " ")
            print(f"    Rank {idx+1}: {rel_path} | Provs: {provs} | Score: {score:.4f} | Preview: {text_preview}")
        print("\n" + "="*155 + "\n")

    print("-" * 155)
    mean_r5 = sum(all_r5) / len(all_r5)
    mean_r10 = sum(all_r10) / len(all_r10)
    mean_r20 = sum(all_r20) / len(all_r20)
    mean_mrr = sum(all_mrr) / len(all_mrr)
    print(f"{'MEAN':<80} | {'':<10} | {'':<20} | {mean_r5:<8.2f} | {mean_r10:<9.2f} | {mean_r20:<9.2f} | {mean_mrr:<5.2f}")


if __name__ == "__main__":
    run_scorecard()
