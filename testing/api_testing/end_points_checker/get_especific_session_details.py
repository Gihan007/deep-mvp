import requests
import json

# API Base URL
BASE_URL = "http://localhost:8080"


# 3. Get Specific Session History
print("\n3. GET SESSION HISTORY (GET)")
session_id = "2"  # Replace with actual session ID
response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
#print(f"Response: {response.json()}")
print(f"Status code: {response.status_code}")
print(f"Raw response text:\n{response.text}")
print("-" * 50)

