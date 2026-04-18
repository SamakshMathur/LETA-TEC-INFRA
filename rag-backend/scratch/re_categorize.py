import os
import sys
import time
from typing import List, Dict, Any

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_template_collection

def re_categorize():
    collection = get_template_collection()
    if collection is None:
        print("Error: Could not connect to MongoDB.")
        return

    print("Starting deep re-categorization of 1,221 documents...")
    
    # 1. Broadly fetch all docs
    docs = list(collection.find({}))
    
    total_updated = 0
    categories_found = {}

    for doc in docs:
        title = doc.get("title", "").upper()
        current_cat = doc.get("category", "General")
        new_cat = current_cat

        # Categorization Logic based on Keywords
        if "NOTFCTN" in title or "CENTRAL" in title or "NOTI" in title:
            new_cat = "Notification"
        elif "CIRCULAR" in title or "CIR" in title:
            new_cat = "Circular"
        elif "EWAY" in title or "DETAINED" in title or "DETENTION" in title:
            new_cat = "E-Way Bill"
        elif "16(4)" in title or "ITC" in title or "GSTR" in title or "RETURN" in title:
            new_cat = "Compliance & Returns"
        elif "PENALTY" in title or "INTEREST" in title or "DEMAND" in title or "DRC" in title:
            new_cat = "Demand & Penalty"
        elif "APPEAL" in title or "WRIT" in title:
            new_cat = "Appeal"
        elif "REFUND" in title:
            new_cat = "Refund"
        elif "REGISTRATION" in title or "CANCEL" in title:
            new_cat = "Registration"
        
        if new_cat != current_cat:
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"category": new_cat}}
            )
            total_updated += 1
            categories_found[new_cat] = categories_found.get(new_cat, 0) + 1

    print(f"\nMigration Complete!")
    print(f"Total Documents Updated: {total_updated}")
    print("\nNew Distribution:")
    for cat, count in categories_found.items():
        print(f"  - {cat}: {count}")

if __name__ == "__main__":
    re_categorize()
