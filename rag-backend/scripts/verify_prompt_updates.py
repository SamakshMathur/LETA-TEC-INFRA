import asyncio
import os
import sys

# Add the project root to sys.path so we can import app modules
sys.path.append(os.path.abspath("."))

from app.generation.advisory import generate_legal_advisory
from app.config import OPENAI_API_KEY

async def test_generation():
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set.")
        return

    query = "My client is a software company in India providing services to a US holding company. The payment was received after 90 days in convertible foreign exchange. Is this export of service? What is the time of supply and is GST applicable?"
    # Mock context
    context = """
    Section 2(6) of the IGST Act, 2017:
    (6) "export of services" means the supply of any service when,—
    (i) the supplier of service is located in India;
    (ii) the recipient of service is located outside India;
    (iii) the place of supply of service is outside India;
    (iv) the payment for such service has been received by the supplier of service in convertible foreign exchange; and
    (v) the supplier of service and the recipient of service are not merely establishments of a distinct person in accordance with Explanation 1 in section 8;

    Section 13(3) of the CGST Act, 2017 regarding Time of Supply for services... (as previously cited)
    
    Circular No. 78/2019: Clarification on export of services...
    """
    
    print("Generating advisory...")
    # generate_legal_advisory is synchronous in the file I saw, but let's check if it needs await.
    # Looking at advisory.py: `def generate_legal_advisory(...)`. It is synchronous.
    # However, it calls client.chat.completions.create which is synchronous.
    
    try:
        result = generate_legal_advisory(user_input=query, context=context)
        print("\n=== GENERATED ADVISORY ===\n")
        print(result["content"])
        print("\n==========================\n")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_generation())
