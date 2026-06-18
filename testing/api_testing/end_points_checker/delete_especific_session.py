import requests
import json

# API Base URL
BASE_URL = "http://localhost:8080"


# 9. Delete Specific Session
print("\n9. DELETE SPECIFIC SESSION (DELETE)")
session_to_delete = "22"  # Replace with actual session ID
response = requests.delete(f"{BASE_URL}/api/sessions/{session_to_delete}")
print(f"Response: {response.json()}")
print("-" * 50)
