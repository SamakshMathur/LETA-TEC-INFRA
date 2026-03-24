
import sys
import os
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.generation.synthesizer import synthesize_answer

def test_accuracy():
    # TEST CASE 1: E-Way Bill (Threshold check)
    # TEST CASE 2: Blocked Credit (Section 17(5)) - Complex
    test_cases = [
        {
            "name": "E-Way Bill Threshold",
            "question": "A registered person in Maharashtra supplies goods to a recipient in Gujarat. The value is Rs. 60,000. Is E-Way bill mandatory?",
            "context": "Rule 138: E-way bill mandatory for consignment value > Rs. 50,000. inter-state implies IGST applies but E-Way rules are same."
        },
        {
            "name": "Motor Vehicle Blocked Credit",
            "question": "An IT company buys a 7-seater car for corporate commuting of executives. Value is 15 Lakhs + GST. Can they claim ITC on the car?",
            "context": "Section 17(5): ITC shall not be available in respect of motor vehicles for transportation of persons having approved seating capacity of not more than 13 persons (including the driver), except for making further supply, transportation of passengers, or training."
        }
    ]
    
    for case in test_cases:
        print(f"\n--- Testing Case: {case['name']} ---")
        print(f"Question: {case['question']}")
        
        try:
            answer = synthesize_answer(case['question'], case['context'])
            if not answer:
                print("!! FAILED: Received empty response.")
            else:
                print("\n--- LETA RESPONSE ---")
                print(answer[:500] + "...")
                print("--- END RESPONSE ---")
                
                # Check for critical keywords (Adversarial Check)
                if "Section 17(5)" in answer or "mandatory" in answer.lower():
                    print("SUCCESS: Response contains critical legal references.")
                else:
                    print("WARNING: Critical legal references might be missing.")
        except Exception as e:
            print(f"Error during testing: {e}")

if __name__ == "__main__":
    test_accuracy()
