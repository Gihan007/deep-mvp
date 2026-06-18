"""Upload *MultiplesTable* CSVs into the structured metrics ingestion API.

Source folder (stage_5):
  /Users/dimuth/Documents/chat_bot/data_given_anand/stage_5/MultiplesData/

Expected filenames:
  <TICKER>_MultiplesTable.csv

API endpoint:
  /api/data_inject_graph_db/csv_structured_metrics_data

Form fields:
  - key=MultiplesTable
  - ticker=<TICKER>
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import requests


DEFAULT_BASE_DIR = Path("/Users/dimuth/Documents/chat_bot/data_given_anand/stage_6/MultiplesData")
#DEFAULT_API_URL = "http://localhost:8080/api/data_inject_graph_db/csv_structured_metrics_data"
DEFAULT_API_URL = "http://34.68.84.147:8080/api/data_inject_graph_db/csv_structured_metrics_data"


def discover_tickers(base_dir: Path) -> List[str]:
    tickers: List[str] = []
    if not base_dir.exists():
        return tickers
    for p in sorted(base_dir.glob("*_MultiplesTable.csv")):
        t = p.name.split("_", 1)[0]
        if t.isalpha():
            tickers.append(t)
    # unique while preserving order
    seen = set()
    out: List[str] = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def upload_multiples_table(
    api_url: str,
    base_dir: Path,
    ticker: str,
    timeout_s: int = 60,
    dry_run: bool = False,
) -> None:
    file_path = base_dir / f"{ticker}_MultiplesTable.csv"
    if not file_path.exists():
        print(f"[{ticker}] SKIP missing: {file_path.name}")
        return

    if dry_run:
        print(f"[DRY RUN] Would upload: ticker={ticker} key=MultiplesTable file={file_path.name}")
        return

    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f, "text/csv")}
        data = {"key": "MultiplesTable", "ticker": ticker}
        resp = requests.post(api_url, files=files, data=data, timeout=timeout_s)
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text

    print(f"[{ticker}] MultiplesTable -> {resp.status_code} :: {payload}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload stage_5 MultiplesTable CSVs into the ingestion API")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Folder containing *_MultiplesTable.csv")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API endpoint URL")
    parser.add_argument("--tickers", nargs="*", help="Optional list of tickers to upload (defaults to discovery)")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds")
    parser.add_argument("--dry-run", action="store_true", help="Don’t call API; just print what would be uploaded")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if not base_dir.exists():
        raise SystemExit(f"Base dir does not exist: {base_dir}")

    tickers = args.tickers or discover_tickers(base_dir)
    if not tickers:
        raise SystemExit(f"No *_MultiplesTable.csv files found under: {base_dir}")

    print(f"Base dir: {base_dir}")
    print(f"API URL : {args.api_url}")
    print(f"Tickers : {', '.join(tickers)}")

    for ticker in tickers:
        upload_multiples_table(args.api_url, base_dir, ticker, timeout_s=args.timeout, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

