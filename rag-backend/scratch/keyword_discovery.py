import os
import sys
from collections import Counter

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_template_collection

def discover_keywords():
    collection = get_template_collection()
    if collection is None:
        print("Error: Could not connect to MongoDB.")
        return

    # Fetch "General" documents
    docs = list(collection.find({"category": "General"}, {"title": 1}))
    print(f"Analyzing {len(docs)} General documents...")

    words = []
    for doc in docs:
        title = doc.get("title", "").upper()
        # Filter out common junk words
        for word in title.split():
            if len(word) > 3 and word not in ["FORMAT", "DRAFT", "REPLY", "RESPONSE", "NOTICE", "TEMPLATE", "LEGAL", "CASE", "GST", "S. NO.", "S NO"]:
                words.append(word)

    common = Counter(words).most_common(50)
    print("\nMost Common Keywords in General Titles:")
    for word, count in common:
        print(f"{word}: {count}")

if __name__ == "__main__":
    discover_keywords()
