from app.routing.intent_classifier import classify_intent

def test_classifier():
    test_cases = [
        # Definition
        ("What is GST?", "definition"),
        ("Define Composite Supply", "definition"),
        ("Explain concept of Input Tax Credit", "definition"),
        
        # Section Advisory
        ("Late fee under section 47", "section_advisory"),
        ("Is ITC blocked under section 17(5)?", "section_advisory"),
        ("Time limit for refund", "section_advisory"),
        ("Penalty for failure to issue invoice", "section_advisory"),

        # Rate
        ("GST rate on solar panels", "rate_classification"),
        ("What is the HSN for rice?", "rate_classification"),
        ("Tax on mobile phones", "rate_classification"),
        ("Applicable GST on services", "rate_classification"),

        # Comparison
        ("Difference between composite and mixed supply", "comparison"),
        ("GST vs VAT", "comparison"),
        ("Regular or composition scheme", "comparison"),
        
        # Ambiguous / Edge cases
        ("help me", "section_advisory"), # default fallback
    ]

    passed = 0
    failed = 0

    print("--- Running Intent Classifier Tests ---")
    for query, expected in test_cases:
        result = classify_intent(query)
        intent = result["intent"]
        if intent == expected:
            print(f"[PASS] '{query}' -> {intent}")
            passed += 1
        else:
            print(f"[FAIL] '{query}' -> Expected {expected}, got {intent}")
            failed += 1

    print(f"\nResults: {passed} PASSED, {failed} FAILED")

if __name__ == "__main__":
    test_classifier()
