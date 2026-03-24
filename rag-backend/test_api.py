import requests
import json

url = "http://localhost:8000/ask"
payload = {"question": "Define mixed supply"}
headers = {"Content-Type": "application/json"}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Response Data:")
        print(json.dumps(data, indent=2))
    else:
        print("Error Response:")
        print(response.text)
except Exception as e:
    print(f"Request failed: {e}")
