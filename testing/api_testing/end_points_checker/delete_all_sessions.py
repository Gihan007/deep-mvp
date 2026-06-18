import requests
import json

# API Base URL
BASE_URL = "http://localhost:8080"


# 10. Delete All Sessions
print("\n10. DELETE ALL SESSIONS (DELETE)")
response = requests.delete(f"{BASE_URL}/api/sessions")
print(f"Response: {response.json()}")
print("-" * 50)
