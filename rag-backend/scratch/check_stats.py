import os
import sys
from typing import List, Dict, Any

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_template_collection

def check_stats():
    collection = get_template_collection()
    if collection is None:
        print("Error: Could not connect to MongoDB.")
        return

    print("--- Database Stats ---")
    total = collection.count_documents({})
    print(f"Total Documents: {total}")

    categories = collection.distinct("category")
    print(f"Unique Categories: {categories}")

    print("\n--- Items per Category ---")
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    groups = list(collection.aggregate(pipeline))
    for group in groups:
        print(f"{group['_id']}: {group['count']}")

    print("\n--- Sample Path Distribution ---")
    # Check if they are from different data dirs
    sample_docs = list(collection.find({}, {"file_path": 1}).limit(100))
    responses_count = 0
    notifications_count = 0
    circulars_count = 0
    for doc in sample_docs:
        path = doc.get("file_path", "")
        if "Responses" in path: responses_count += 1
        elif "Notification" in path: notifications_count += 1
        elif "Circulars" in path: circulars_count += 1
    
    print(f"Sample breakdown (first 100):")
    print(f"  Responses: {responses_count}")
    print(f"  Notifications: {notifications_count}")
    print(f"  Circulars: {circulars_count}")

if __name__ == "__main__":
    check_stats()
