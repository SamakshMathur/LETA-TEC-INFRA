import requests
import time

URL = "http://localhost:8000/api/advisory/generate"

def test_regeneration():
    print("Testing Regeneration Loop...")
    
    # query that involves specific caps and logic
    payload = {
        "query": f"I filed my GSTR-3B for October 2023 with a delay of 20 days. My tax liability was NIL. What is the late fee? [TEST ID: {time.time()}]",
        "manual_case": True 
    }
    
    start = time.time()
    try:
        response = requests.post(URL, json=payload, timeout=120)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Time: {duration:.2f}s")
            print(f"PDF URL: {data.get('pdf_url')}")
            # The backend log will show if regeneration happened.
        else:
            print(f"Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_regeneration()
