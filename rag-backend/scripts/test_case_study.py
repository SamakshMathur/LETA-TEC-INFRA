
import requests
import json
import time

url = "http://localhost:8000/ask"
payload = {
    "question": "Case Study: A registered person in Maharashtra supplies goods to a recipient in Gujarat. The goods are moved by road. The value of the consignment is Rs. 60,000. Is E-Way bill mandatory? What if the recipient is unregistered?",
    "intent": "general"
}

print(f"Sending request to {url}...")
start = time.time()
try:
    response = requests.post(url, json=payload, timeout=60)
    end = time.time()
    print(f"Status Code: {response.status_code}")
    print(f"Time Taken: {end - start:.2f}s")
    if response.status_code == 200:
        data = response.json()
        print("Response Keys:", data.keys())
        print("Answer Length:", len(data.get("answer", "")))
        print("Preview:", data.get("answer", "")[:200])
        print("Sources:", data.get("sources"))
    else:
        print("Error Response:", response.text)
except Exception as e:
    with open("test_output.txt", "w") as f:
        f.write(f"Request failed: {e}")

# Success logic modification
if 'response' in locals():
    with open("test_output.txt", "w") as f:
        f.write(f"Status Code: {response.status_code}\n")
        f.write(f"Time Taken: {end - start:.2f}s\n")
        if response.status_code == 200:
            data = response.json()
            f.write(f"Response Keys: {list(data.keys())}\n")
            f.write(f"Answer Length: {len(data.get('answer', ''))}\n")
            f.write(f"Preview: {data.get('answer', '')[:500]}\n")
            f.write(f"Sources: {data.get('sources')}\n")
        else:
            f.write(f"Error Response: {response.text}\n")
