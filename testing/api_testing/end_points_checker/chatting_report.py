"""
Simple individual examples for each API endpoint.
"""
import requests
import json
import time
import base64
import mimetypes
import os



API_URL = "http://localhost:8080/api/deep_qa_bot_report"
#API_URL = "http://34.68.84.147:8080/api/qa_bot"

question = "What was Walmart’s  Revenue Growth Rate over the last 5 years"

# === Optional: Prepare Base64-encoded files ===
def encode_file_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")



# Example: You can add your own image/audio/file paths here
image_paths = ["/Users/dimuth/Documents/chat_bot/Get-Deep/data/images/market.jpg"] 
file_paths = ["/Users/dimuth/Documents/chat_bot/Get-Deep/data/pdfs/test.pdf"]
audio_paths = ["voice_note.wav"]

#base64_images = [f"data:image/png;base64,{encode_file_to_base64(p)}" for p in image_paths]
#base64_files = [f"data:application/pdf;base64,{encode_file_to_base64(p)}" for p in file_paths]
#base64_audios = [f"data:audio/wav;base64,{encode_file_to_base64(p)}" for p in audio_paths]


session_id = f"test-{int(time.time())}"

report_type = "company_performance_and_investment_thesis"
ticker = "WMT"

payload = {
    "report_type": report_type,
    "session_id": session_id,
    "ticker": ticker,

}

# === Send Request ===
response = requests.post(API_URL, json=payload)

# === Print Response ===
print("Status Code:", response.status_code)

try:
    data = response.json()
    print(json.dumps(data, indent=4))
except Exception:
    print(response.text)





"""

what Markets and customers in 2021 in Walmart
what are Executive officer information in walmart 
what are the Debt details in Walmart

 
"""
