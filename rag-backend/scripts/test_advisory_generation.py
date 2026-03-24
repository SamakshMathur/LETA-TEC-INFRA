import requests
import json
import time

url = "http://localhost:8000/api/advisory/generate"
payload = {
    "subject": "Late Fee under GST",
    "query": "What is the late fee for delayed filing of GSTR-3B under Section 47? Please mention the maximum cap.",
    "jurisdiction": "India"
}

print(f"Sending request to {url}...")
start = time.time()
try:
    response = requests.post(url, json=payload, timeout=120)
    end = time.time()
    
    with open("advisory_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Status Code: {response.status_code}\n")
        f.write(f"Time Taken: {end - start:.2f}s\n")
        
        if response.status_code == 200:
            # The API returns a streaming response or file download usually?
            # Wait, advisory.py returns FileResponse (PDF).
            # But I want to see the TEXT content which might be in headers or I need to intercept the generation logic?
            # Ah, the endpoint returns a PDF file validation using pdf_gen.
            # But wait, looking at advisory.py code in Step 958:
            # It generates PDF and returns it.
            # It DOES NOT return the text JSON.
            # This makes verification hard without reading PDF.
            # However, I can check logs?
            # Or I can modify advisory.py to return JSON for debugging? 
            # Or I can check if the validator ran by looking at server logs (I added prints? No).
            
            # Let's check what the endpoint returns.
            f.write(f"Content-Type: {response.headers.get('Content-Type')}\n")
            f.write(f"Content Length: {len(response.content)} bytes\n")
        else:
            f.write(f"Error: {response.text}\n")
            
except Exception as e:
    print(f"Failed: {e}")
