from __future__ import annotations

import logging
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from neo4j import GraphDatabase

from config import get_config

logger = logging.getLogger(__name__)
router = APIRouter()
config = get_config()


# --------------------------------------------------------------------------------------
# Neo4j helpers
# --------------------------------------------------------------------------------------

def _get_driver():
    if not config.NEO4J_URI:
        raise HTTPException(status_code=500, detail="NEO4J_URI is not configured")
    try:
        return GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
        )
    except Exception as e:
        logger.exception("Failed to create Neo4j driver")
        raise HTTPException(status_code=500, detail=f"Neo4j connection error: {e}")


_YEAR_COL_RE = re.compile(r"^(\d{4})$")


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _extract_year_props(node_props: Dict[str, Any]) -> Dict[int, Any]:
    """Extract {year:int -> rawValue} from properties like year_2024."""
    out: Dict[int, Any] = {}
    for k, v in (node_props or {}).items():
        if not isinstance(k, str):
            continue
        if not k.startswith("year_"):
            continue
        y = k.replace("year_", "")
        if not (len(y) == 4 and y.isdigit()):
            continue
        out[int(y)] = v
    return out


def _get_node_props(session, label: str, ticker: str, metric_name: str) -> Optional[Dict[str, Any]]:
    row = session.run(
        f"""
        MATCH (m:`{label}` {{ticker: $ticker, metricName: $metricName}})
        RETURN properties(m) AS props
        LIMIT 1
        """,
        ticker=ticker,
        metricName=metric_name,
    ).single()
    return row["props"] if row else None


def _get_single_node_props(session, label: str, ticker: str) -> Optional[Dict[str, Any]]:
    row = session.run(
        f"""
        MATCH (m:`{label}` {{ticker: $ticker}})
        RETURN properties(m) AS props
        LIMIT 1
        """,
        ticker=ticker,
    ).single()
    return row["props"] if row else None


_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "utills" / "metric_csv_templates"


def _read_template_csv(key: str) -> Tuple[List[str], List[str]]:
    """Read template CSV and return (headers, row_labels).

    Template files live at: src/app/utills/metric_csv_templates/{key}.csv
    - headers: full header row (including blank first column header)
    - row_labels: first column values for each subsequent row
    """
    template_path = _TEMPLATES_DIR / f"{key}.csv"
    if not template_path.exists():
        raise RuntimeError(f"Template file not found: {template_path}")
    df = pd.read_csv(template_path, dtype=str).fillna("")
    headers = [str(c) for c in df.columns]

    # first column name might be blank in the template (pandas will call it 'Unnamed: 0')
    first_col = df.columns[0]
    row_labels = [str(v).strip() for v in df[first_col].tolist() if str(v).strip() != ""]
    return headers, row_labels


def _read_template_metric_list_only(key: str) -> List[str]:
    """Read template CSV that contains ONLY metric names.

    Format expected:
        metric
        Revenue
        CostOfRevenue
        ...
    """
    template_path = _TEMPLATES_DIR / f"{key}.csv"
    if not template_path.exists():
        raise RuntimeError(f"Template file not found: {template_path}")

    # Use csv.reader (not pandas) to correctly handle 1-column files.
    import csv as _csv

    with template_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = _csv.reader(f)
        header = next(reader, None)
        if header is None:
            return []
        # first cell is the column name (metric)
        rows: List[str] = []
        for r in reader:
            if not r:
                continue
            v = str(r[0]).strip()
            if v:
                rows.append(v)
        return rows


def _load_spec_from_templates() -> Dict[str, Dict[str, Any]]:
    # Templates policy (requested): for year-based datasets we store ONLY metric names.
    row_only_keys = [
        "3StatementModel",
        "FreeCashFlows",
        "ReportedFinancials",
        "InvestedCapital",
        "Performance",
        "HistoricalCagrAvg",
        "ExtractedItems",
    ]
    full_template_keys = [
        "ValuationForecastDriverValues",
        "ValuationSummary",
    ]

    out: Dict[str, Dict[str, Any]] = {}

    for k in row_only_keys:
        out[k] = {"rows": _read_template_metric_list_only(k)}

    for k in full_template_keys:
        headers, rows = _read_template_csv(k)
        if headers and headers[0].startswith("Unnamed"):
            headers[0] = ""
        out[k] = {"headers": headers, "rows": rows}

    return out


try:
    # Templates are the ONLY supported source of ordering/spec.
    # Never fall back to `data_csvs.txt` at runtime.
    _SPEC = _load_spec_from_templates()
except Exception as e:
    raise RuntimeError(
        "Failed to load dynamic table templates from 'src/app/utills/metric_csv_templates'. "
        "Ensure all required template CSVs exist and are readable. "
        f"Underlying error: {e}"
    )


# --------------------------------------------------------------------------------------
# CSV builders
# --------------------------------------------------------------------------------------

def _build_row_based_csv(
    *,
    ticker: str,
    metric_names_in_order: List[str],
    dataset_key: str,
    include_driver_value: bool,
    include_statement_type: bool,
    extra_prop_cols: Optional[List[str]] = None,
    session,
) -> pd.DataFrame:
    """Build a row-based DataFrame.

    Templates now only define the row order (metric list). Column headers are
    derived dynamically from stored Neo4j properties.
    """

    current_year = datetime.now().year

    extra_prop_cols = extra_prop_cols or []

    # Pre-fetch props so we can derive year columns.
    rows_cache: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    years_set: set[int] = set()

    for mn in metric_names_in_order:
        hist_props = _get_node_props(session, "Metric", ticker, mn) or {}
        pred_props = _get_node_props(session, "MetricPredicted", ticker, mn) or {}
        hist_years = _extract_year_props(hist_props)
        pred_years = _extract_year_props(pred_props)

        if dataset_key == "FreeCashFlows":
            # FreeCashFlows now stores BOTH historical + predicted year values.
            years_set.update(hist_years.keys())
            years_set.update(pred_years.keys())
        elif dataset_key == "ReportedFinancials":
            years_set.update([y for y in hist_years.keys() if y < current_year])
        elif dataset_key == "ExtractedItems":
            years_set.update(hist_years.keys())
        elif dataset_key == "HistoricalCagrAvg":
            # no years
            pass
        else:
            years_set.update(hist_years.keys())
            years_set.update(pred_years.keys())

        rows_cache.append((mn, hist_props, pred_props))

    if dataset_key == "ReportedFinancials":
        year_cols = sorted(years_set, reverse=True)
    else:
        year_cols = sorted(years_set)

    # Build dynamic headers
    headers: List[str] = ["metric"]
    if include_statement_type:
        headers.append("statementType")
    if dataset_key != "HistoricalCagrAvg":
        headers.extend([str(y) for y in year_cols])
    if include_driver_value:
        headers.append("DriverValue")
    headers.extend(extra_prop_cols)

    rows: List[Dict[str, Any]] = []
    for mn, hist_props, pred_props in rows_cache:
        hist_years = _extract_year_props(hist_props)
        pred_years = _extract_year_props(pred_props)

        row: Dict[str, Any] = {"metric": mn}
        if include_statement_type:
            row["statementType"] = hist_props.get("statementType")

        for y in year_cols:
            if dataset_key == "FreeCashFlows":
                # Prefer predicted values for future years, but allow historical values
                # to be shown when present (for past years).
                if y < current_year:
                    row[str(y)] = hist_years.get(y)
                else:
                    row[str(y)] = pred_years.get(y, hist_years.get(y))
            elif dataset_key == "ReportedFinancials":
                row[str(y)] = hist_years.get(y) if y < current_year else None
            elif dataset_key == "ExtractedItems":
                row[str(y)] = hist_years.get(y)
            elif dataset_key == "HistoricalCagrAvg":
                # no years
                pass
            else:
                if y < current_year:
                    row[str(y)] = hist_years.get(y)
                else:
                    row[str(y)] = pred_years.get(y, hist_years.get(y))

        if include_driver_value:
            row["DriverValue"] = hist_props.get("DriverValue")

        for col in extra_prop_cols:
            row[col] = hist_props.get(col)

        rows.append(row)

    df = pd.DataFrame(rows)

    # Ensure exact ordering and ensure missing columns exist.
    for c in headers:
        if c not in df.columns:
            df[c] = np.nan
    return df[headers]


def _build_driver_values_csv(*, ticker: str, session) -> pd.DataFrame:
    spec = _SPEC["ValuationForecastDriverValues"]
    headers = spec["headers"]
    props = _get_single_node_props(session, "Metric_ValuationForecastDriverValues", ticker)
    if not props:
        raise HTTPException(status_code=404, detail=f"ValuationForecastDriverValues not found for {ticker}")

    row: Dict[str, Any] = {}
    for h in headers:
        if h == "":
            continue
        row[h] = props.get(h)

    # Ensure ExtractionTime always present if available
    if "ExtractionTime" in headers and "ExtractionTime" not in row:
        row["ExtractionTime"] = props.get("ExtractionTime")

    df = pd.DataFrame([row])
    # force ordering
    for c in headers:
        if c and c not in df.columns:
            df[c] = np.nan
    df = df[[c for c in headers if c]]
    return df


def _build_valuation_summary_csv(*, ticker: str, session) -> pd.DataFrame:
    spec = _SPEC["ValuationSummary"]
    headers = spec["headers"]  # ["", "FreeCashFlow", "DiscountFactor", "PresentValue"]
    row_labels = spec["rows"]
    props = _get_single_node_props(session, "Metric_ValuationSummary", ticker)
    if not props:
        raise HTTPException(status_code=404, detail=f"ValuationSummary not found for {ticker}")

    def sanitize(s: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_")

    rows: List[Dict[str, Any]] = []
    for rn in row_labels:
        r: Dict[str, Any] = {headers[0]: rn}
        for col in headers[1:]:
            key = f"{sanitize(rn)}_{sanitize(col)}"
            r[col] = props.get(key)
        rows.append(r)

    df = pd.DataFrame(rows)
    for c in headers:
        if c not in df.columns:
            df[c] = np.nan
    return df[headers]


def _df_to_json_payload(df: pd.DataFrame) -> Dict[str, Any]:
    """Convert a DataFrame to a JSON-serializable payload.

    - Converts NaN/NaT to None.
    - Converts numpy scalars to native Python types.
    """
    def _sanitize_json_value(v: Any) -> Any:
        """Make a value JSON-safe for stdlib json.

        Starlette uses `json.dumps(..., allow_nan=False)`, so any NaN/inf must be removed.
        """
        if v is None:
            return None
        # pandas NA/NaT
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        # numpy scalars -> python scalars
        if isinstance(v, np.generic):
            v = v.item()
        # Complex numbers cannot be JSON encoded
        if isinstance(v, complex):
            return None
        # Floats: remove NaN/inf
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    cols = [str(c) for c in df.columns]
    # IMPORTANT: don't use DataFrame.to_dict() here; it can re-introduce NaN depending
    # on internal dtype handling. We build rows manually and sanitize cell-by-cell.
    rows: List[Dict[str, Any]] = []
    for row_vals in df.to_numpy(dtype=object):
        row: Dict[str, Any] = {}
        for c, v in zip(cols, row_vals):
            row[c] = _sanitize_json_value(v)
        rows.append(row)

    return {"columns": cols, "rows": rows}


def _validate_ticker(ticker: str) -> str:
    if not ticker or ticker.strip() == "":
        raise HTTPException(status_code=422, detail="ticker is required")
    t = ticker.strip().upper()
    if not t.isalpha():
        raise HTTPException(status_code=422, detail="ticker must contain only letters")
    return t


# --------------------------------------------------------------------------------------
# 7 endpoints
# --------------------------------------------------------------------------------------

@router.post("/api/dynamic_table/3StatementModel")
def regenerate_3statement_model(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["3StatementModel"]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="3StatementModel",
                include_driver_value=True,
                include_statement_type=False,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "3StatementModel", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/FreeCashFlows")
def regenerate_free_cash_flows(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["FreeCashFlows"]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="FreeCashFlows",
                include_driver_value=False,
                include_statement_type=False,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "FreeCashFlows", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/ReportedFinancials")
def regenerate_reported_financials(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["ReportedFinancials"]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="ReportedFinancials",
                include_driver_value=False,
                include_statement_type=True,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "ReportedFinancials", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/InvestedCapital")
def regenerate_invested_capital(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["InvestedCapital"]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="InvestedCapital",
                include_driver_value=False,
                include_statement_type=False,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "InvestedCapital", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/Performance")
def regenerate_performance(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["Performance"]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="Performance",
                include_driver_value=False,
                include_statement_type=False,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "Performance", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/ValuationForecastDriverValues")
def regenerate_valuation_forecast_driver_values(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            df = _build_driver_values_csv(ticker=ticker_u, session=session)
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "ValuationForecastDriverValues", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/ValuationSummary")
def regenerate_valuation_summary(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            df = _build_valuation_summary_csv(ticker=ticker_u, session=session)
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "ValuationSummary", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/HistoricalCagrAvg")
def regenerate_historical_cagr_avg(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["HistoricalCagrAvg"]

            # Fixed set of columns stored for this dataset (no years)
            extra_cols = [
                "Last1Y_AVG",
                "Last2Y_AVG",
                "Last3Y_AVG",
                "Last4Y_AVG",
                "Last5Y_AVG",
                "Last10Y_AVG",
                "Last15Y_AVG",
                "Last1Y_CAGR",
                "Last2Y_CAGR",
                "Last3Y_CAGR",
                "Last4Y_CAGR",
                "Last5Y_CAGR",
                "Last10Y_CAGR",
                "Last15Y_CAGR",
            ]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="HistoricalCagrAvg",
                include_driver_value=False,
                include_statement_type=False,
                extra_prop_cols=extra_cols,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "HistoricalCagrAvg", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/dynamic_table/ExtractedItems")
def regenerate_extracted_items(ticker: str = Form(...)):
    ticker_u = _validate_ticker(ticker)
    driver = _get_driver()
    try:
        with driver.session() as session:
            spec = _SPEC["ExtractedItems"]
            df = _build_row_based_csv(
                ticker=ticker_u,
                metric_names_in_order=spec["rows"],
                dataset_key="ExtractedItems",
                include_driver_value=False,
                include_statement_type=False,
                session=session,
            )
            payload = _df_to_json_payload(df)
            return JSONResponse(status_code=200, content={"status": "success", "key": "ExtractedItems", "ticker": ticker_u, **payload})
    finally:
        try:
            driver.close()
        except Exception:
            pass
