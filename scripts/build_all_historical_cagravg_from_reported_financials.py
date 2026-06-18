"""Create a single CSV with all unique metrics from `*_ReportedFinancials.csv`.

User goal:
  - scan all ticker folders under a root directory
  - read each `*_ReportedFinancials.csv`
  - collect ALL unique metric names (and their row values)
  - if a metric already exists in the output, skip it

Output:
  - <root>/ALL_ReportedFinancials.csv

Notes:
  - We keep the *first* occurrence of each metric (metric-name uniqueness).
  - We union all year columns across tickers and align values by year.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


DEFAULT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "data_given_anand"
    / "stage_5"
    / "VInvestTestData"
)


@dataclass
class MetricRow:
    metric: str
    statement_type: str
    # year -> value
    values: Dict[str, str]


def find_reported_financials_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for ticker_dir in sorted(root.iterdir()):
        if not ticker_dir.is_dir() or ticker_dir.name.startswith("."):
            continue
        files.extend(sorted(ticker_dir.glob("*_ReportedFinancials.csv")))
    return files


def read_reported_financials(path: Path) -> tuple[list[str], list[MetricRow]]:
    """Return (years, rows) for a single ReportedFinancials csv."""

    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return [], []

        # Expected header like: ['', 'statementType', '2025', '2024', ...]
        years = [h.strip() for h in header[2:] if h.strip()]
        rows: list[MetricRow] = []

        for r in reader:
            if not r or len(r) < 2:
                continue
            metric = r[0].strip()
            statement_type = r[1].strip()
            if not metric:
                continue

            values: Dict[str, str] = {}
            for i, year in enumerate(years, start=2):
                if i < len(r):
                    val = r[i].strip()
                    if val != "":
                        values[year] = val

            rows.append(MetricRow(metric=metric, statement_type=statement_type, values=values))

        return years, rows


def main() -> int:
    root = DEFAULT_ROOT
    if not root.exists():
        raise SystemExit(f"Root folder not found: {root}")

    files = find_reported_financials_files(root)
    if not files:
        raise SystemExit(f"No *_ReportedFinancials.csv files found under: {root}")

    # 1) First pass: union year columns
    all_years_set: set[str] = set()
    for fpath in files:
        years, _ = read_reported_financials(fpath)
        all_years_set.update(years)

    # Sort years numerically DESC if possible, else lexicographically
    def year_sort_key(y: str):
        try:
            return (0, -int(y))
        except ValueError:
            return (1, y)

    all_years = sorted(all_years_set, key=year_sort_key)

    # 2) Second pass: keep first occurrence of each metric
    seen_metrics: set[str] = set()
    merged_rows: list[MetricRow] = []
    for fpath in files:
        _, rows = read_reported_financials(fpath)
        for row in rows:
            if row.metric in seen_metrics:
                continue
            seen_metrics.add(row.metric)
            merged_rows.append(row)

    out_path = root / "ALL_ReportedFinancials.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "statementType", *all_years])
        for row in merged_rows:
            writer.writerow(
                [row.metric, row.statement_type, *[row.values.get(y, "") for y in all_years]]
            )

    print(f"Wrote {len(merged_rows)} unique metrics to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
