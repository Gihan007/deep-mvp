"""Count CSV row counts under a VInvestTestData-style folder.

Expected input structure:

    <root>/
        AAPL/
            AAPL_ExtractedItems.csv
            AAPL_FreeCashFlows.csv
            ...
        MSFT/
            MSFT_ExtractedItems.csv
            ...

This script walks each ticker folder, counts *data rows* (excluding header) in
each CSV file, and writes a consolidated CSV report.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
from typing import Iterable, Optional


@dataclass(frozen=True)
class CsvRowCount:
    ticker: str
    csv_type: str
    file_name: str
    file_path: str
    rows: int


def infer_csv_type(ticker: str, csv_path: Path) -> str:
    """Infer a 'type' from filenames like `AAPL_ExtractedItems.csv`.

    If the filename begins with '<ticker>_' that prefix is removed.
    """

    base = csv_path.stem  # filename without extension
    prefix = f"{ticker}_"
    if base.startswith(prefix):
        return base[len(prefix) :]
    return base


def count_data_rows(csv_path: Path) -> int:
    """Count data rows (excluding the header row) in a CSV file."""

    # Using csv.reader instead of line counting to handle quoted newlines.
    try:
        f = csv_path.open("r", encoding="utf-8-sig", newline="", errors="replace")
    except FileNotFoundError:
        return 0

    with f:
        reader = csv.reader(f)
        try:
            next(reader)  # header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def iter_ticker_dirs(root_dir: Path) -> Iterable[Path]:
    for p in sorted(root_dir.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            yield p


def collect_counts(root_dir: Path) -> list[CsvRowCount]:
    results: list[CsvRowCount] = []
    for ticker_dir in iter_ticker_dirs(root_dir):
        ticker = ticker_dir.name
        for csv_path in sorted(ticker_dir.glob("*.csv")):
            csv_type = infer_csv_type(ticker, csv_path)
            rows = count_data_rows(csv_path)
            results.append(
                CsvRowCount(
                    ticker=ticker,
                    csv_type=csv_type,
                    file_name=csv_path.name,
                    file_path=str(csv_path),
                    rows=rows,
                )
            )
    return results


def write_report(counts: list[CsvRowCount], output_csv: Path) -> None:
    """Write a pivoted CSV:

    csv_type, AAPL, ADBE, ...
    3StatementModel, 174, 180, ...
    ExtractedItems, 22, 21, ...
    """

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    tickers = sorted({c.ticker for c in counts})
    types = sorted({c.csv_type for c in counts})

    table: dict[str, dict[str, int]] = defaultdict(dict)
    for c in counts:
        # if duplicates exist, last one wins (shouldn't happen for this dataset)
        table[c.csv_type][c.ticker] = c.rows

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["csv_type", *tickers])
        for t in types:
            writer.writerow([t, *[table[t].get(ticker, "") for ticker in tickers]])


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Count data rows (excluding header) in each CSV under ticker folders "
            "and write a consolidated report."
        )
    )
    parser.add_argument(
        "--root",
        default=str(
            (Path(__file__).resolve().parents[2]
             / "data_given_anand"
             / "stage_5"
             / "VInvestTestData")
        ),
        help=(
            "Path to root folder that contains ticker subfolders. "
            "Default: <repo>/data_given_anand/stage_5/VInvestTestData"
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Default: <root>/metric_cout.csv",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    root_dir = Path(args.root).expanduser().resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        raise SystemExit(f"Root folder not found or not a directory: {root_dir}")

    output_csv = (
        Path(args.out).expanduser().resolve()
        if args.out
        else root_dir / "metric_cout.csv"
    )

    counts = collect_counts(root_dir)
    write_report(counts, output_csv)
    print(f"Wrote {len(counts)} row counts to: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
