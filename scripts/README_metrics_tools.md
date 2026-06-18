# Metrics CSV utilities

## 1) Count CSV rows per ticker/type (pivot output)

Creates a pivot table (rows = `csv_type`, columns = tickers like AAPL/ADBE) with
counts of data rows per file.

Run:

```bash
python3 scripts/metric_count_rows.py
```

Output:

- `.../data_given_anand/stage_5/VInvestTestData/metric_cout.csv`

## 2) Merge ALL unique metrics from `*_ReportedFinancials.csv`

Scans every ticker folder under `VInvestTestData/`, reads each
`*_ReportedFinancials.csv`, and builds a single file with **unique metric names**.

Run (preferred script name):

```bash
python3 scripts/merge_reported_financials_unique_metrics.py
```

Alternative (same code):

```bash
python3 scripts/build_all_historical_cagravg_from_reported_financials.py
```

Output:

- `.../data_given_anand/stage_5/VInvestTestData/ALL_ReportedFinancials.csv`

