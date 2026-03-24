import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.retrieval.query_refiner import extract_query_topic
import json

query = "Is ITC allowed on motor vehicles used for passenger transport?"
topic_info = extract_query_topic(query)
print(f"Query: {query}")
print(f"Topic Info: {json.dumps(topic_info, indent=2)}")
print(f"Type: {type(topic_info)}")
