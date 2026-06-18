import csv
from pathlib import Path

import pandas as pd


# =========================
# EDIT THESE PATHS IF NEEDED
# =========================
REF_DIR = Path(
    "/Users/dimuth/Documents/chat_bot/data_given_anand/stage_6/SampleDataFeb13/AAPL"
)
TEMPLATE_DIR = Path(
    "/Users/dimuth/Documents/chat_bot/Get-Deep/src/app/utills/metric_csv_templates"
)

# Create .bak before overwriting templates
MAKE_BACKUP = False

# Only regenerate these template files
ALLOWED_DATASETS = {
    "3StatementModel",
    "ExtractedItems",
    "FreeCashFlows",
    "HistoricalCagrAvg",
    "InvestedCapital",
    "Performance",
    "ValuationForecastDriverValues",
    "ValuationSummary",
}

# Never touch these
DO_NOT_TOUCH = {"ReportedFinancials", "MultiplesTable"}


def read_reference_df(path: Path) -> pd.DataFrame:
    # Keep strings as-is; don’t parse numbers/dates
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def extract_first_col_values(df: pd.DataFrame) -> list[str]:
    if df.shape[1] == 0:
        return []

    values: list[str] = []
    seen: set[str] = set()

    for raw in df.iloc[:, 0].tolist():
        s = str(raw).strip() if raw is not None else ""
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        values.append(s)

    return values


def detect_template_kind(template_path: Path) -> str:
    """Return one of:
    - metric_list
    - valuation_forecast_driver_values
    - valuation_summary
    - unknown
    """
    with template_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return "unknown"

    header = rows[0]

    # metric list templates look like:
    # metric
    # Revenue
    if len(header) == 1 and header[0].strip().lower() == "metric":
        return "metric_list"

    # ValuationSummary template looks like:
    # ,FreeCashFlow,DiscountFactor,PresentValue
    if len(header) >= 2 and header[0].strip() == "" and header[1].strip() == "FreeCashFlow":
        return "valuation_summary"

    # ValuationForecastDriverValues template looks like:
    # ExtractionTime,RevenueGrowthInLast4y,...
    if len(header) >= 2 and header[0].strip() == "ExtractionTime":
        return "valuation_forecast_driver_values"

    return "unknown"


def write_metric_list_template(out_path: Path, metrics: list[str]):
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric"])
        for m in metrics:
            w.writerow([m])


def write_valuation_forecast_driver_values_template(out_path: Path, ref_columns: list[str]):
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(ref_columns)
        # Keep one empty row like your existing template
        w.writerow([""] * len(ref_columns))


def write_valuation_summary_template(out_path: Path, ref_columns: list[str], row_labels: list[str]):
    # Ensure first column is blank (template style)
    if not ref_columns:
        ref_columns = ["", "FreeCashFlow", "DiscountFactor", "PresentValue"]
    else:
        ref_columns = list(ref_columns)
        ref_columns[0] = ""

    ncols = len(ref_columns)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(ref_columns)
        for label in row_labels:
            w.writerow([label] + [""] * (ncols - 1))


def find_reference_file(ref_dir: Path, dataset: str) -> Path | None:
    # expects files like AAPL_3StatementModel.csv
    matches = sorted(ref_dir.glob(f"*_{dataset}.csv"))
    return matches[0] if matches else None


def main():
    if not REF_DIR.exists():
        raise SystemExit(f"Reference dir not found: {REF_DIR}")
    if not TEMPLATE_DIR.exists():
        raise SystemExit(f"Template dir not found: {TEMPLATE_DIR}")

    for dataset in sorted(ALLOWED_DATASETS):
        if dataset in DO_NOT_TOUCH:
            continue

        template_path = TEMPLATE_DIR / f"{dataset}.csv"
        if not template_path.exists():
            print(f"[SKIP] Template not found: {template_path}")
            continue

        ref_path = find_reference_file(REF_DIR, dataset)
        if ref_path is None:
            # Example: AAPL_ExtractedItems.csv doesn’t exist → skip
            print(f"[SKIP] Reference for {dataset} not found in {REF_DIR}")
            continue

        kind = detect_template_kind(template_path)
        df = read_reference_df(ref_path)

        if MAKE_BACKUP:
            bak = template_path.with_suffix(template_path.suffix + ".bak")
            if not bak.exists():
                bak.write_bytes(template_path.read_bytes())

        if kind == "metric_list":
            metrics = extract_first_col_values(df)
            write_metric_list_template(template_path, metrics)
            print(f"[OK] Regenerated metric list template: {template_path} ({len(metrics)} rows)")

        elif kind == "valuation_forecast_driver_values":
            cols = list(df.columns)
            write_valuation_forecast_driver_values_template(template_path, cols)
            print(f"[OK] Regenerated ValuationForecastDriverValues template: {template_path} ({len(cols)} columns)")

        elif kind == "valuation_summary":
            cols = list(df.columns)
            rows = extract_first_col_values(df)
            write_valuation_summary_template(template_path, cols, rows)
            print(f"[OK] Regenerated ValuationSummary template: {template_path} ({len(rows)} rows)")

        else:
            print(f"[SKIP] Unknown template structure for {dataset}: {template_path}")


if __name__ == "__main__":
    main()
