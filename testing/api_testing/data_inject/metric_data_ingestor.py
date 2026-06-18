"""Upload new *structured metric CSVs* (stage_3 format) into the API.

Expected folder layout:
  /Users/dimuth/Documents/chat_bot/data_given_anand/stage_3/<TICKER>/<TICKER>_<Dataset>.csv

Datasets / API keys supported by the updated backend:
  - 3StatementModel
  - FreeCashFlows
  - ReportedFinancials
  - InvestedCapital
  - Performance
  - ValuationForecastDriverValues
  - ValuationSummary
"""

from __future__ import annotations
import csv
import os
from pathlib import Path
from typing import Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ------------------- Configuration -------------------

BASE_DIR = Path("/Users/dimuth/Documents/chat_bot/data_given_anand/missing_tickers")
API_URL = "http://localhost:8080/api/data_inject_graph_db/csv_structured_metrics_data"


#API_URL = "http://34.68.84.147:8080/api/data_inject_graph_db/csv_structured_metrics_data"



# Optional: set to a list of ticker strings to only upload specific tickers,
# e.g. ["AAPL", "MSFT"]. Set to None to upload all tickers found in BASE_DIR.
TICKERS = None

READ_TIMEOUT_S = 300       # HTTP read timeout in seconds
CONNECT_TIMEOUT_S = 10     # HTTP connect timeout in seconds
RETRIES = 2                # Retry count for transient network/5xx errors
BACKOFF_FACTOR = 0.5       # Sleep between retries (exponential backoff factor)
CONTINUE_ON_ERROR = False  # If True, continue uploading other datasets/tickers on failure
DRY_RUN = False            # If True, don't call API; just print what would be uploaded

COMPLETED_FILE = Path("ticker_completed.csv")

DATASET_TO_KEY: Dict[str, str] = {
    "3StatementModel":            "3StatementModel",
    "FreeCashFlows":              "FreeCashFlows",
    "ReportedFinancials":         "ReportedFinancials",
    "InvestedCapital":            "InvestedCapital",
    "Performance":                "Performance",
    "HistoricalCagrAvg":          "HistoricalCagrAvg",
    "ExtractedItems":             "ExtractedItems",
    "ValuationForecastDriverValues": "ValuationForecastDriverValues",
    "ValuationSummary":           "ValuationSummary",
    "MultiplesTable":             "MultiplesTable",
}


# ------------------- Functions -------------------

def build_retrying_session(retries: int, backoff_factor: float) -> requests.Session:
    """Create a requests session with basic retries.

    Notes:
      - We explicitly allow retries on POST because this is an ingestion endpoint.
      - If your API is not idempotent, keep retries low (or disable).
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def discover_tickers(base_dir: Path) -> List[str]:
    tickers: List[str] = []
    for p in sorted(base_dir.iterdir()):
        if p.is_dir() and p.name.isalpha():
            tickers.append(p.name)
    return tickers


def upload_csv(
    session: requests.Session,
    ticker: str,
    key: str,
    file_path: Path,
) -> bool:
    if DRY_RUN:
        print(f"[DRY RUN] Would upload: ticker={ticker} key={key} file={file_path.name}")
        return True

    print(
        f"[{ticker}] UPLOAD start: key={key} file={file_path.name} "
        f"(connect_timeout={CONNECT_TIMEOUT_S}s read_timeout={READ_TIMEOUT_S}s)",
        flush=True,
    )

    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f, "text/csv")}
        data = {"key": key, "ticker": ticker}

        try:
            resp = session.post(
                API_URL,
                files=files,
                data=data,
                timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
            )
        except requests.exceptions.RequestException as e:
            print(f"[{ticker}] {key} -> REQUEST FAILED :: {e}")
            return False

        try:
            payload = resp.json()
        except Exception:
            payload = resp.text

    print(f"[{ticker}] UPLOAD done : key={key} -> {resp.status_code} :: {payload}", flush=True)
    return 200 <= resp.status_code < 300


def mark_ticker_completed(ticker: str) -> None:
    """Append ticker to ticker_completed.csv, avoid duplicates."""
    existing = set()
    if COMPLETED_FILE.exists():
        with COMPLETED_FILE.open("r", newline="") as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)  # skip header
            existing.update(row[0] for row in reader)

    if ticker in existing:
        return  # already recorded

    write_header = not COMPLETED_FILE.exists()
    with COMPLETED_FILE.open("a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(["ticker"])
        writer.writerow([ticker])


# ------------------- Main -------------------

def main() -> None:
    if not BASE_DIR.exists():
        raise SystemExit(f"Base dir does not exist: {BASE_DIR}")

    tickers = TICKERS or discover_tickers(BASE_DIR)
    if not tickers:
        raise SystemExit(f"No ticker folders found under: {BASE_DIR}")

    print(f"Base dir : {BASE_DIR}")
    print(f"API URL  : {API_URL}")
    print(f"Tickers  : {', '.join(tickers)}")
    print(f"Dry run  : {DRY_RUN}")

    session = build_retrying_session(RETRIES, BACKOFF_FACTOR)

    for ticker in tickers:
        ticker_dir = BASE_DIR / ticker
        if not ticker_dir.exists():
            print(f"[WARN] Missing ticker folder: {ticker_dir}")
            continue

        print(f"\n=== Processing ticker: {ticker} ===")

        any_failed = False

        for dataset, key in DATASET_TO_KEY.items():
            # Only upload the expected CSVs, avoid any duplicate-report helper files.
            file_path = ticker_dir / f"{ticker}_{dataset}.csv"
            if not file_path.exists():
                print(f"[{ticker}] SKIP missing: {file_path.name}")
                continue

            ok = upload_csv(
                session=session,
                ticker=ticker,
                key=key,
                file_path=file_path,
            )
            if not ok:
                any_failed = True
                if not CONTINUE_ON_ERROR:
                    raise SystemExit(f"Upload failed for ticker={ticker} key={key}")

        # Mark ticker as completed only if all attempted uploads succeeded
        if not any_failed:
            mark_ticker_completed(ticker)
        else:
            print(f"[{ticker}] NOT marked completed (one or more dataset uploads failed)")


if __name__ == "__main__":
    main()