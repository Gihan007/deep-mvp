import requests
import json

# API Base URL
BASE_URL = "http://localhost:8080"



# 2. List All Sessions
print("\n2. LIST ALL SESSIONS (GET)")
response = requests.get(f"{BASE_URL}/api/sessions")
print(f"Response: {response.json()}")
print("-" * 50)

