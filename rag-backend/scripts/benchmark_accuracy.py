import json
import requests
import time
import re

URL = "http://localhost:8000/api/advisory/generate"
DATASET_PATH = "data/gold_100.json"
REPORT_PATH = "evaluation_report.md"

def evaluate():
    print("=" * 60)
    print("   LETA ACCURACY BENCHMARK v2.0")
    print("   Target: 100% Concept Coverage")
    print("=" * 60)
    
    print("\nLoading Gold Dataset...")
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)
    
    total_cases = len(dataset)
    passed_cases = 0
    total_score = 0
    results = []
    category_scores = {}
    
    print(f"Cases to Test: {total_cases}")
    print("-" * 60)
    
    for case in dataset:
        case_id = case["id"]
        query = case["query"]
        category = case.get("category", "General")
        expected_concepts = case["gold_answer_concepts"]
        expected_logic = case.get("expected_logic", "")
        
        print(f"\n[{case_id}] ({category}) {query[:60]}...")
        
        payload = {
            "query": query,
        }
        
        try:
            start = time.time()
            response = requests.post(URL, json=payload, timeout=120)
            duration = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                generated_answer = data.get("advisory", data.get("content", ""))
                
                # Accuracy Check: Concept Coverage
                missing_concepts = []
                found_count = 0
                concept_details = []
                
                for concept in expected_concepts:
                    # Flexible matching: normalize whitespace and case
                    normalized_answer = re.sub(r'\s+', ' ', generated_answer.lower())
                    normalized_concept = re.sub(r'\s+', ' ', concept.lower())
                    
                    if normalized_concept in normalized_answer:
                        found_count += 1
                        concept_details.append(f"  ✅ '{concept}'")
                    else:
                        missing_concepts.append(concept)
                        concept_details.append(f"  ❌ '{concept}'")
                
                score = (found_count / len(expected_concepts)) * 100
                total_score += score
                
                # Strict pass: 80% concept match (up from 60%)
                is_pass = score >= 80
                
                if is_pass:
                    passed_cases += 1
                    status = "PASS"
                else:
                    status = "FAIL"
                
                # Track category scores
                if category not in category_scores:
                    category_scores[category] = {"total": 0, "score_sum": 0}
                category_scores[category]["total"] += 1
                category_scores[category]["score_sum"] += score
                
                results.append({
                    "id": case_id,
                    "category": category,
                    "status": status,
                    "score": score,
                    "missing": missing_concepts,
                    "duration": duration,
                    "concept_details": concept_details,
                    "answer_preview": generated_answer[:200]
                })
                
                print(f"  -> {status} ({score:.0f}%) in {duration:.1f}s")
                if missing_concepts:
                    print(f"  -> Missing: {', '.join(missing_concepts)}")
                    
            else:
                print(f"  -> ERROR: API Status {response.status_code}")
                results.append({"id": case_id, "category": category, "status": "ERROR", "score": 0, "duration": 0})
                
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")
            results.append({"id": case_id, "category": category, "status": "ERROR", "score": 0, "duration": 0})
    
    # Calculate Results
    accuracy = (passed_cases / total_cases) * 100
    avg_score = total_score / total_cases if total_cases > 0 else 0
    
    print("\n" + "=" * 60)
    print(f"  BENCHMARK COMPLETE")
    print(f"  Pass Rate: {accuracy:.1f}% ({passed_cases}/{total_cases})")
    print(f"  Avg Concept Coverage: {avg_score:.1f}%")
    print(f"  Pass Threshold: 80%")
    print("=" * 60)
    
    # Category Breakdown
    print("\n  Category Breakdown:")
    for cat, data in sorted(category_scores.items()):
        cat_avg = data["score_sum"] / data["total"]
        print(f"    {cat}: {cat_avg:.0f}% avg ({data['total']} cases)")
    
    # Generate Report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# LETA Accuracy Benchmark Report v2.0\n\n")
        f.write(f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Overall Pass Rate**: {accuracy:.1f}% ({passed_cases}/{total_cases})\n")
        f.write(f"**Average Concept Coverage**: {avg_score:.1f}%\n")
        f.write(f"**Pass Threshold**: ≥80% Concept Match\n\n")
        
        f.write("## Category Breakdown\n\n")
        f.write("| Category | Avg Score | Cases |\n")
        f.write("|----------|-----------|-------|\n")
        for cat, data in sorted(category_scores.items()):
            cat_avg = data["score_sum"] / data["total"]
            f.write(f"| {cat} | {cat_avg:.0f}% | {data['total']} |\n")
        
        f.write("\n## Detailed Results\n\n")
        f.write("| Case ID | Category | Status | Score | Missing Concepts | Time |\n")
        f.write("|---------|----------|--------|-------|------------------|------|\n")
        for r in results:
            missing_str = ", ".join(r.get('missing', [])) if r.get('missing') else "None"
            f.write(f"| {r['id']} | {r.get('category', '-')} | {r['status']} | {r['score']:.0f}% | {missing_str} | {r.get('duration', 0):.1f}s |\n")
        
        # Failure Analysis
        failures = [r for r in results if r["status"] == "FAIL"]
        if failures:
            f.write("\n## Failure Analysis\n\n")
            for r in failures:
                f.write(f"### {r['id']} ({r.get('category', '-')}) - {r['score']:.0f}%\n")
                f.write(f"**Missing Concepts**: {', '.join(r.get('missing', []))}\n")
                f.write(f"**Answer Preview**: {r.get('answer_preview', 'N/A')}\n\n")

    print(f"\n  Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    evaluate()
