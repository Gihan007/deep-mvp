import requests

# Replace with the actual endpoint
url = "http://localhost:8080/api/user_data_deletion"

# Replace with the appropriate session ID
payload = {
    "session_id": "your_unique_session_id"
}

# Send the POST request with JSON data
response = requests.post(url, json=payload)

# Print the response
print("Status Code:", response.status_code)
print("Response JSON:", response.json())