
import requests
import os
import time
import csv

BASE_DIR = "/home/valueaccel/dimuth/stage_2/data_10K_TextExtracts"
API_URL = "http://localhost:8080/api/data_inject_graph_db/csv_unstructured"
#API_URL = "http://34.68.84.147:8080/api/data_inject_graph_db/csv_unstructured"
LOG_FILE = "upload_status.csv"

# ---- Load already processed files from log ----
processed_files = set()

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as log:
        reader = csv.reader(log)
        next(reader, None)  # skip header
        for row in reader:
            if row:
                processed_files.add(row[0])

# ---- Create log file with header if not exists ----
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as log:
        writer = csv.writer(log)
        writer.writerow(["filename", "status"])

# ---- Collect all TXT files ----
txt_files = []

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".txt"):
            txt_files.append(os.path.join(root, file))

print(f"Found {len(txt_files)} TXT files.")

# TXT file format expectation:
# - filename must be like: TICKER_YEAR.txt (e.g., COST_2018.txt)
# - each line is treated as one "row" (like the old CSV single-column rows)

# ---- Process each file ----
for txt_path in txt_files:
    filename = os.path.basename(txt_path)

    # Skip if already processed
    if filename in processed_files:
        print(f"Skipping (already in log): {filename}")
        continue

    print(f"\nUploading: {filename}")

    with open(txt_path, "rb") as f:
        # NOTE: API expects form field name `file` (not `files`) and content-type text/plain.
        files = {"file": (filename, f, "text/plain")}

        try:
            response = requests.post(API_URL, files=files)
            status = "success" if response.status_code == 200 else f"failed({response.status_code})"

            print("Status Code:", response.status_code)
            print("Response:", response.text[:300])

        except Exception as e:
            status = f"failed({str(e)})"
            print("Error uploading", filename, "->", e)

    # ---- Write result to log ----
    with open(LOG_FILE, "a", newline="") as log:
        writer = csv.writer(log)
        writer.writerow([filename, status])

    time.sleep(2)














# import requests
# import os

# # API endpoint
# url = "http://localhost:8080/api/data_inject_graph_db/csv_unstructured"


# csv_files = [
#     "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/TGT/TGT_2025_10K_granular_extract.csv",
#     "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/BJ/BJ_2019_10K_granular_extract.csv",
#     "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/DLTR/DLTR_2013_10K_granular_extract.csv",
#     "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/WMT/WMT_2020_10K_granular_extract.csv",
#     "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/COST/COST_2018_10K_granular_extract.csv"
# ]

# files = []
# for path in csv_files:
#     filename = os.path.basename(path)
#     files.append(('files', (filename, open(path, 'rb'), 'text/csv')))

# try:
#     response = requests.post(url, files=files)
#     print("Status Code:", response.status_code)
#     print("Response:", response.text)

# finally:
#     # Close opened file objects
#     for _, filetuple in files:
#         filetuple[1].close()






"""


| Batch | CSV Filename                       | Total Tokens | Prompt Tokens | Completion Tokens | Total Cost (USD) | Successful Requests |
|-------|------------------------------------|--------------|---------------|-------------------|------------------|---------------------|
| 1     | TGT_2025_10K_granular_extract.csv  |   415,762    |   353,951     |     61,811        |    0.072861      |        47           |
| 2     | BJ_2019_10K_granular_extract.csv   |   712,918    |   615,674     |     97,244        |    0.120784      |        79           |
| 3     | DLTR_2013_10K_granular_extract.csv |   631,239    |   567,689     |     63,550        |    0.092976      |        78           |
| 4     | WMT_2020_10K_granular_extract.csv  |  1,069,222   |   950,375     |     118,847.      |    0.163714      |        128          |
| 5     | COST_2018_10K_granular_extract.csv |  502,792     |   428,168     |     74,624        |    0.086574      |        57           |


"""

# NOTE: Table above is from older CSV-based runs; with TXT ingestion the token usage
# should be comparable if the line content is equivalent.
