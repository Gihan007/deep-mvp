import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import requests

HEADERS = {
    "User-Agent": "YourName your@email.com"
}

TICKER = "AAPL"
YEAR = "2021"

# --------------------------------------------------
# 1) Ticker → CIK
# --------------------------------------------------
ticker_url = "https://www.sec.gov/files/company_tickers.json"
ticker_data = requests.get(ticker_url, headers=HEADERS).json()

cik = None
for item in ticker_data.values():
    if item["ticker"].upper() == TICKER.upper():
        cik = str(item["cik_str"]).zfill(10)
        break

if not cik:
    raise ValueError("Ticker not found")

print(f"CIK for {TICKER}: {cik}")

# --------------------------------------------------
# 2) Get company filings
# --------------------------------------------------
submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
data = requests.get(submissions_url, headers=HEADERS).json()

forms = data["filings"]["recent"]["form"]
dates = data["filings"]["recent"]["filingDate"]
docs = data["filings"]["recent"]["primaryDocument"]
accessions = data["filings"]["recent"]["accessionNumber"]

# --------------------------------------------------
# 3) Find 10-K for the requested year
# --------------------------------------------------
found = False

for i in range(len(forms)):
    if forms[i] == "10-K" and dates[i].startswith(YEAR):
        acc = accessions[i].replace("-", "")
        doc = docs[i]
        html_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
        print(f"10-K {YEAR} URL:")
        print(html_url)
        found = True
        break

if not found:
    print(f"No 10-K found for {TICKER} in {YEAR}")




headers = {"User-Agent": "YourName your@email.com"}
html = requests.get(html_url, headers=headers).text

# with open(f"{TICKER}_{YEAR}_10K.html", "w", encoding="utf-8") as f:
#     f.write(html)


soup = BeautifulSoup(html, "html.parser")
for tag in soup(["script", "style"]):
    tag.decompose()
markdown = md(str(soup), heading_style="ATX")

import tempfile
import os

# Use temp directory for file output
temp_dir = tempfile.gettempdir()
output_path = os.path.join(temp_dir, f"{TICKER}_{YEAR}_10K.md")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(markdown)

print(f"10K markdown saved to: {output_path}")

