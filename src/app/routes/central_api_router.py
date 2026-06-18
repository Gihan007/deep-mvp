from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple

from config import get_config
from neo4j import GraphDatabase

import logging
import math
import re
import json
from datetime import date, timedelta


# ---------------------------
# Metric name normalization / aliases
# ---------------------------

# Common frontend-friendly labels -> graph metricName
_METRIC_ALIASES: Dict[str, str] = {
    "net income": "NetIncome",
    "operating cash flow": "OperatingCashFlow",
    "free cash flow": "FreeCashFlow",
    # Some datasets store EBITDA under these names
    "ebitda": "EBITDAAdjusted",
    "ebit": "OperatingIncome",
}


def _normalize_metric_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").strip().lower())


def _display_metric_name(metric_name: str) -> str:
    """Best-effort human readable label (keeps common abbreviations)."""
    if not metric_name:
        return ""

    known = {
        "NetIncome": "Net Income",
        "OperatingCashFlow": "Operating Cash Flow",
        "FreeCashFlow": "Free Cash Flow",
        "EBITDAAdjusted": "EBITDA",
        "EBITAAdjusted": "EBIT",
    }
    if metric_name in known:
        return known[metric_name]

    # Fallback: insert spaces before capitals
    return re.sub(r"(?<!^)([A-Z])", r" \1", metric_name).strip()


def _resolve_metric_input(session, metric_input: str, ticker: Optional[str] = None) -> str:
    """Resolve user/frontend metric input to an actual `metricName` stored in Neo4j."""
    raw = (metric_input or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="metric is required")

    # 1) Exact match fast path
    if ticker:
        row = session.run(
            """
            MATCH (m:Metric {ticker: $ticker, metricName: $metricName})
            RETURN m.metricName AS name
            LIMIT 1
            """,
            ticker=ticker,
            metricName=raw,
        ).single()
        if row and row.get("name"):
            return str(row["name"])
    else:
        row = session.run(
            """
            MATCH (m:Metric {metricName: $metricName})
            RETURN m.metricName AS name
            LIMIT 1
            """,
            metricName=raw,
        ).single()
        if row and row.get("name"):
            return str(row["name"])

    # 2) Alias map
    alias_key = raw.lower()
    if alias_key in _METRIC_ALIASES:
        return _METRIC_ALIASES[alias_key]

    # 3) Normalized best-effort match against existing metric names
    target_norm = _normalize_metric_name(raw)
    if not target_norm:
        raise HTTPException(status_code=422, detail="metric is required")

    if ticker:
        res = session.run(
            """
            MATCH (m:Metric {ticker: $ticker})
            WHERE m.metricName IS NOT NULL
            RETURN DISTINCT m.metricName AS name
            """,
            ticker=ticker,
        )
    else:
        res = session.run(
            """
            MATCH (m:Metric)
            WHERE m.metricName IS NOT NULL
            RETURN DISTINCT m.metricName AS name
            """,
        )

    for r in res:
        name = r.get("name")
        if name and _normalize_metric_name(str(name)) == target_norm:
            return str(name)

    raise HTTPException(status_code=404, detail=f"Unknown metric: {metric_input}")




router = APIRouter()
logger = logging.getLogger(__name__)
config = get_config()


# ---------------------------
# Neo4j helpers
# ---------------------------

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


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if isinstance(f, float) and (math.isnan(f) or math.isinf(f)):
            return None
        return f
    except Exception:
        return None


_YEAR_KEY_RE = re.compile(r"^year_(\d{4})$")


def _extract_year_map(node_props: Dict[str, Any]) -> Dict[int, float]:
    """Extract {year:int -> value:float} from Neo4j node properties."""
    out: Dict[int, float] = {}
    for k, v in (node_props or {}).items():
        m = _YEAR_KEY_RE.match(str(k))
        if not m:
            continue
        year = int(m.group(1))
        fv = _safe_float(v)
        if fv is None:
            continue
        out[year] = fv
    return out


def _parse_tickers_param(tickers: str) -> List[str]:
    parts = [t.strip().upper() for t in (tickers or "").split(",") if t.strip()]
    # de-dupe preserving order
    seen = set()
    res = []
    for t in parts:
        if t not in seen:
            seen.add(t)
            res.append(t)
    return res


def _parse_period_years(period: Optional[str]) -> Optional[int]:
    """Return N in '5Y' or None for ALL/empty."""
    if not period:
        return None
    p = period.strip().upper()
    if p in ("ALL", "MAX"):
        return None
    m = re.match(r"^(\d+)Y$", p)
    if not m:
        raise HTTPException(status_code=422, detail="period must be like 1Y, 5Y, 10Y, or ALL")
    return int(m.group(1))


def _filter_years(year_map: Dict[int, float], n_years: Optional[int]) -> Dict[int, float]:
    if not year_map:
        return {}
    years_sorted = sorted(year_map.keys())
    if not n_years:
        return {y: year_map[y] for y in years_sorted}
    return {y: year_map[y] for y in years_sorted[-n_years:]}


def _cagr(start: float, end: float, periods: int) -> Optional[float]:
    if periods <= 0:
        return None
    if start is None or end is None:
        return None
    if start <= 0:
        return None
    try:
        return (end / start) ** (1.0 / periods) - 1.0
    except Exception:
        return None


def _sanitize_key(s: str) -> str:
    # Used for JSON keys like "Software_-_Infrastructure_total"
    s2 = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s2 or "Industry"


def _get_metric_node_properties(session, ticker: str, metric_name: str) -> Optional[Dict[str, Any]]:
    row = session.run(
        """
        MATCH (m:Metric {ticker: $ticker, metricName: $metricName})
        RETURN properties(m) AS props
        LIMIT 1
        """,
        ticker=ticker,
        metricName=metric_name,
    ).single()
    return row["props"] if row else None


def _get_metric_year_series(session, ticker: str, metric_name: str) -> Dict[int, float]:
    props = _get_metric_node_properties(session, ticker, metric_name)
    if not props:
        return {}
    return _extract_year_map(props)


def _get_any_metric_series(session, ticker: str, candidates: List[str]) -> Tuple[Optional[str], Dict[int, float]]:
    """Return (metricNameChosen, series)."""
    for name in candidates:
        series = _get_metric_year_series(session, ticker, name)
        if series:
            return name, series
    return None, {}


# ---------------------------
# Response models (lightweight)
# ---------------------------


class CompanyOut(BaseModel):
    ticker: str
    name: str


class MetricsOut(BaseModel):
    metrics: List[str]


class IndustryOut(BaseModel):
    name: str
    companies: List[str]


# ---------------------------
# Section 1: Business Performance Tab
# ---------------------------

# ========================================  okay
# 1. GET ALL COMPANIES
# ========================================
#curl -X GET "http://localhost:8080/api/central/companies" -H "Content-Type: application/json"
@router.get("/api/central/companies", response_model=List[CompanyOut])
def get_all_companies():
    """Populates the Company search dropdown selector."""
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (c:Company)
                WHERE c.ticker IS NOT NULL
                RETURN c.ticker AS ticker, c.companyName AS name
                ORDER BY name
                """
            )
            return [
                CompanyOut(ticker=str(r["ticker"]).upper(), name=str(r["name"] or "")).model_dump()
                for r in result
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list central companies")
        raise HTTPException(status_code=400, detail=f"Failed to list companies: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass




# ========================================  okay
# 2. GET AVAILABLE METRICS
# ========================================
#curl -X GET "http://localhost:8080/api/central/metrics?include_predicted=false&display_names=true" -H "Content-Type: application/json"

@router.get("/api/central/metrics", response_model=MetricsOut)
def get_available_metrics(
    include_predicted: bool = Query(False),
    display_names: bool = Query(False, description="If true, return human-friendly labels"),
):
    """Populates the Metric dropdown selector."""
    driver = _get_driver()
    try:
        with driver.session() as session:
            # Use DISTINCT metric names from Metric nodes.
            # (ValuationSummary is a Metric node too; exclude it from the dropdown.)
            metric_names = set()
            res1 = session.run(
                """
                MATCH (m:Metric)
                WHERE m.metricName IS NOT NULL AND m.metricName <> 'ValuationSummary'
                RETURN DISTINCT m.metricName AS name
                ORDER BY name
                """
            )
            metric_names.update([r["name"] for r in res1 if r and r.get("name")])

            if include_predicted:
                res2 = session.run(
                    """
                    MATCH (pm:PredictedMetric)
                    WHERE pm.metricName IS NOT NULL
                    RETURN DISTINCT pm.metricName AS name
                    """
                )
                metric_names.update([r["name"] for r in res2 if r and r.get("name")])

            metrics_sorted = sorted(metric_names)
            if display_names:
                metrics_sorted = sorted({_display_metric_name(m) for m in metrics_sorted if m})

            return MetricsOut(metrics=metrics_sorted).model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list central metrics")
        raise HTTPException(status_code=400, detail=f"Failed to list metrics: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


# ========================================   okay
# 3. GET INDUSTRIES
# ========================================
#curl -X GET "http://localhost:8080/api/central/industries" -H "Content-Type: application/json"

@router.get("/api/central/industries", response_model=Dict[str, List[IndustryOut]])
def get_available_industries():
    """Populates the Industry dropdown selector."""
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (i:Industry)
                OPTIONAL MATCH (c:Company)-[:BELONG_TO]->(i)
                WITH i, collect(DISTINCT c.ticker) AS tickers
                RETURN i.industryName AS name,
                       [t IN tickers WHERE t IS NOT NULL] AS companies
                ORDER BY name
                """
            )
            industries = [
                IndustryOut(
                    name=str(r["name"] or ""),
                    companies=[str(t).upper() for t in (r["companies"] or []) if t],
                ).model_dump()
                for r in result
            ]
            return {"industries": industries}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list central industries")
        raise HTTPException(status_code=400, detail=f"Failed to list industries: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



# ========================================   okay
# 4. GET AGGREGATED DATA (Company Performance)
# ========================================
#  curl -X GET "http://localhost:8080/api/central/aggregated-data?tickers=WMT,CENT&metric=Revenue&period=5Y&periodType=Annual" -H "Content-Type: application/json"

@router.get("/api/central/aggregated-data", response_model=List[Dict[str, Any]])
def get_aggregated_company_data(
    tickers: str = Query(..., description="Comma-separated list of tickers, e.g. AAPL,MSFT"),
    metric: str = Query(..., description="Metric label or exact metricName (e.g., Revenue, Net Income, Free Cash Flow)"),
    period: Optional[str] = Query(None, description="1Y, 5Y, 10Y, or ALL"),
    periodType: str = Query("Annual", description="Annual | Average | CAGR"),
):
    """Historical performance data for specific companies."""
    tickers_list = _parse_tickers_param(tickers)
    if not tickers_list:
        raise HTTPException(status_code=422, detail="tickers must contain at least one ticker")

    n_years = _parse_period_years(period)
    period_type = (periodType or "Annual").strip().lower()
    if period_type not in ("annual", "average", "cagr"):
        raise HTTPException(status_code=422, detail="periodType must be Annual, Average, or CAGR")

    driver = _get_driver()
    try:
        with driver.session() as session:
            out: List[Dict[str, Any]] = []
            for t in tickers_list:
                metric_name = _resolve_metric_input(session, metric, ticker=t)
                series = _get_metric_year_series(session, t, metric_name)
                if not series:
                    # If a ticker doesn't have that metric, just skip it (frontend can handle missing series)
                    continue

                series = _filter_years(series, n_years)
                years_sorted = sorted(series.keys())

                if period_type == "annual":
                    for y in years_sorted:
                        out.append({"ticker": t, "name": str(y), "value": series[y]})
                elif period_type == "average":
                    vals = [series[y] for y in years_sorted if series.get(y) is not None]
                    if vals:
                        out.append({"ticker": t, "name": "Average", "value": sum(vals) / len(vals)})
                else:  # cagr
                    if len(years_sorted) >= 2:
                        start_y, end_y = years_sorted[0], years_sorted[-1]
                        start_v, end_v = series[start_y], series[end_y]
                        c = _cagr(start_v, end_v, end_y - start_y)
                        if c is not None:
                            out.append({"ticker": t, "name": "CAGR", "value": c})

            if not out:
                raise HTTPException(status_code=404, detail="No data found for the requested tickers/metric")
            return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get aggregated-data")
        raise HTTPException(status_code=400, detail=f"Failed to get aggregated data: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


# ========================================     okay
# 5. GET INDUSTRY COMPARISON
# ========================================
#curl -X GET "http://localhost:8080/api/central/industry-comparison?industries=Discount%20Stores,Packaged%20Foods&metric=Revenue&period=5Y" -H "Content-Type: application/json"

@router.get("/api/central/industry-comparison", response_model=Dict[str, Any])
def get_industry_comparison_data(
    industries: str = Query(..., description="Comma-separated industry names"),
    metric: str = Query(..., description="Metric label or exact metricName"),
    period: Optional[str] = Query(None, description="Optional: 1Y, 5Y, 10Y, or ALL"),
):
    """Historical average performance for selected industries."""
    requested = [i.strip() for i in (industries or "").split(",") if i.strip()]
    if not requested:
        raise HTTPException(status_code=422, detail="industries must contain at least one industry name")

    n_years = _parse_period_years(period)

    driver = _get_driver()
    try:
        with driver.session() as session:
            # Resolve the metric input once
            metric_name = _resolve_metric_input(session, metric)

            # Resolve each industry name (case-insensitive exact match) -> tickers
            resolved: List[Tuple[str, List[str]]] = []
            for ind in requested:
                row = session.run(
                    """
                    MATCH (i:Industry)
                    WHERE toLower(i.industryName) = toLower($name)
                    OPTIONAL MATCH (c:Company)-[:BELONG_TO]->(i)
                    RETURN i.industryName AS industryName,
                           collect(DISTINCT c.ticker) AS tickers
                    LIMIT 1
                    """,
                    name=ind,
                ).single()
                if not row:
                    continue
                industry_name = str(row.get("industryName") or ind)
                tickers_list = [str(t).upper() for t in (row.get("tickers") or []) if t]
                resolved.append((industry_name, tickers_list))

            if not resolved:
                raise HTTPException(status_code=404, detail="No matching industries found")

            # Collect per-industry per-year values
            # year -> {industryKey: avg}
            year_bucket: Dict[int, Dict[str, float]] = {}

            for industry_name, tickers_list in resolved:
                if not tickers_list:
                    continue

                # Gather metric series for each ticker, then average by year
                per_ticker_series: List[Dict[int, float]] = []
                industry_years: set[int] = set()
                for t in tickers_list:
                    s = _get_metric_year_series(session, t, metric_name)
                    if s:
                        per_ticker_series.append(s)
                        industry_years.update(s.keys())

                if not per_ticker_series:
                    continue

                # Average for each year across tickers
                industry_key = f"{_sanitize_key(industry_name)}_total"
                for y in sorted(industry_years):
                    vals = [ts.get(y) for ts in per_ticker_series if ts.get(y) is not None]
                    if not vals:
                        continue
                    year_bucket.setdefault(y, {})[industry_key] = float(sum(vals) / len(vals))

            if not year_bucket:
                raise HTTPException(status_code=404, detail="No comparison data found for requested industries/metric")

            years_sorted = sorted(year_bucket.keys())
            if n_years:
                years_sorted = years_sorted[-n_years:]

            comparisons: List[Dict[str, Any]] = []
            for y in years_sorted:
                row = {"period": str(y)}
                row.update(year_bucket.get(y, {}))
                comparisons.append(row)

            return {
                "industries": [name for name, _ in resolved],
                "comparisons": comparisons,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get industry comparison")
        raise HTTPException(status_code=400, detail=f"Failed to get industry comparison: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


# ---------------------------
# Section 3: Historical Ranking
# ---------------------------


# curl -X GET "http://localhost:8080/api/central/rankings/types" -H "Content-Type: application/json"
@router.get("/api/central/rankings/types")
def get_ranking_types():
    """Populates the Ranking Type dropdown filter."""
    return {
        "rankingTypes": [
            {"id": "overall", "label": "Overall Rank"},
            {"id": "roic", "label": "ROIC Rank"},
            {"id": "earnings", "label": "Earnings Yield Rank"},
            {"id": "intrinsic", "label": "Intrinsic Value Rank"},
        ]
    }



# curl -X GET "http://localhost:8080/api/central/rankings/historical?tickers=WMT,COST&rankingType=overall&period=5Y" -H "Content-Type: application/json"

@router.get("/api/central/rankings/historical")
def get_historical_company_ranking(
    tickers: str = Query(..., description="Comma-separated list of tickers, e.g. WMT,COST"),
    rankingType: str = Query(..., description="overall | roic | earnings | intrinsic"),
    period: Optional[str] = Query(None, description="1Y, 5Y, 10Y, or ALL"),
):
    """Return historical ranking values based on SpecialMetricRankingCache nodes (one per cache_date)."""

    tickers_list = _parse_tickers_param(tickers)
    if not tickers_list:
        raise HTTPException(status_code=422, detail="tickers must contain at least one ticker")

    rtype = (rankingType or "").strip().lower()
    type_to_field = {
        "overall": "overall_rank",
        "roic": "roic_rank",
        "earnings": "earnings_yield_rank",
        "intrinsic": "intrinsic_to_mc_rank",
    }
    if rtype not in type_to_field:
        raise HTTPException(status_code=422, detail="rankingType must be one of overall, roic, earnings, intrinsic")

    n_years = _parse_period_years(period)
    min_date: Optional[str] = None
    if n_years:
        min_dt = date.today() - timedelta(days=365 * int(n_years))
        min_date = min_dt.isoformat()

    driver = _get_driver()
    try:
        with driver.session() as session:
            if min_date:
                res = session.run(
                    """
                    MATCH (c:SpecialMetricRankingCache)
                    WHERE c.cache_date IS NOT NULL AND c.cache_date >= $min_date
                    RETURN c.cache_date AS cache_date, c.Ranking AS ranking
                    ORDER BY c.cache_date ASC
                    """,
                    min_date=min_date,
                )
            else:
                res = session.run(
                    """
                    MATCH (c:SpecialMetricRankingCache)
                    WHERE c.cache_date IS NOT NULL
                    RETURN c.cache_date AS cache_date, c.Ranking AS ranking
                    ORDER BY c.cache_date ASC
                    """
                )

            history: List[Dict[str, Any]] = []
            field = type_to_field[rtype]

            for row in res:
                cache_date = row.get("cache_date")
                ranking_raw = row.get("ranking")
                if not cache_date or not ranking_raw:
                    continue

                try:
                    ranking_list = json.loads(ranking_raw) if isinstance(ranking_raw, str) else ranking_raw
                except Exception:
                    # Skip invalid JSON
                    continue

                if not isinstance(ranking_list, list):
                    continue

                # Build a per-date mapping for requested tickers
                per_date: Dict[str, Any] = {"date": str(cache_date)}
                index = {str(item.get("ticker", "")).upper(): item for item in ranking_list if isinstance(item, dict)}

                for t in tickers_list:
                    item = index.get(t)
                    per_date[t] = item.get(field) if item else None

                history.append(per_date)

            if not history:
                raise HTTPException(status_code=404, detail="No historical ranking data found (compute rankings first)")

            return {
                "history": history,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get historical rankings")
        raise HTTPException(status_code=400, detail=f"Failed to get historical rankings: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


# ---------------------------
# Section 2: Valuation Model
# ---------------------------

def _statement_match_clause(statement: str) -> str:
    s = statement.strip().lower()
    if s == "income":
        return "toLower(m.statementType) CONTAINS 'income'"
    if s == "balance":
        return "toLower(m.statementType) CONTAINS 'balance'"
    if s == "cashflow":
        return "toLower(m.statementType) CONTAINS 'cash'"
    raise HTTPException(status_code=500, detail="Invalid statement type mapping")


def _build_statement_table(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Rows: [{metricName: str, props: dict}] -> {year: {metricName: value}}"""
    out: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        metric_name = r.get("metricName")
        props = r.get("props") or {}
        year_map = _extract_year_map(props)
        for y, v in year_map.items():
            out.setdefault(int(y), {})[str(metric_name)] = v
    return out



# ========================================   okay
# 6. GET INCOME STATEMENT
# ========================================
#curl -X GET "http://localhost:8080/api/central/financials/income-statement/WMT" -H "Content-Type: application/json"

IncomeStatement_metricNames = [
    "RevenueGrowthRate",
    "Revenue",
    "CostOfRevenue",
    "GrossMargin",
    "SellingAndMarketingExpense",
    "GeneralAndAdministrativeExpense",
    "FulfillmentExpense",
    "TechnologyExpense",
    "SellingGeneralAndAdministration",
    "DepreciationAndAmortization",
    "ResearchAndDevelopment",
    "GoodwillImpairment",
    "OtherOperatingExpense",
    "OperatingExpenses",
    "OperatingIncome",
    "InterestExpenseDebt",
    "InterestExpenseFinance",
    "InterestExpense",
    "InterestIncome",
    "OtherNonoperatingIncome",
    "NonoperatingIncomeNet",
    "PretaxIncome",
    "TaxProvision",
    "NetIncomeControlling",
    "NetIncomeNoncontrolling",
    "NetIncome",
    "SharesOutstandingBasic",
    "SharesOutstandingDiluted",
    "OperatingLeaseCost",
    "VariableLeaseCost",
    "LeasesDiscountRate",
    "ForeignCurrencyAdjustment",
    "PaidInCapitalCommonStockDividendPayment"
]

@router.get("/api/central/financials/income-statement/{ticker}")
def get_income_statement_data(ticker: str):
    """Populates the historical columns of the Income Statement table."""
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:Metric {ticker: $ticker})
                WHERE m.metricName IN $metric_names
                RETURN m.metricName AS metricName, properties(m) AS props
                """,
                ticker=ticker_u,
                metric_names=IncomeStatement_metricNames,
            )
            rows = [dict(r) for r in result]

            # Build a year-keyed payload containing ONLY the requested income statement metrics.
            # Missing metrics for a year will be returned as null.
            base_table = _build_statement_table(rows)
            if not base_table:
                raise HTTPException(status_code=404, detail=f"No income statement data found for {ticker_u}")

            years_sorted = sorted(base_table.keys())
            shaped = {
                str(y): {mn: base_table[y].get(mn) for mn in IncomeStatement_metricNames}
                for y in years_sorted
            }
            return shaped
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch income statement")
        raise HTTPException(status_code=400, detail=f"Failed to fetch income statement: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass






# ========================================   okay
# 7. GET BALANCE SHEET
# ========================================
#curl -X GET "http://localhost:8080/api/central/financials/balance-sheet/WMT" -H "Content-Type: application/json"

BalanceSeet_metricName = [
    "Cash",
    "ShortTermInvestments",
    "CashAndCashEquivalents",
    "ReceivablesCurrent",
    "Inventory",
    "OtherAssetsCurrent",
    "AssetsCurrent",
    "PropertyPlantAndEquipment",
    "OperatingLeaseAssets",
    "FinanceLeaseAssets",
    "Goodwill",
    "DeferredIncomeTaxAssetsNoncurrent",
    "ReceivablesNoncurrent",
    "OtherAssetsNoncurrent",
    "AssetsNoncurrent",
    "Assets",
    "AccountsPayableCurrent",
    "EmployeeAccruedLiabilitiesCurrent",
    "AccruedLiabilitiesCurrent",
    "AccruedIncomeTaxesCurrent",
    "DeferredRevenueCurrent",
    "LongTermDebtCurrent",
    "OperatingLeaseLiabilitiesCurrent",
    "FinanceLeaseLiabilitiesCurrent",
    "OtherLiabilitiesCurrent",
    "LiabilitiesCurrent",
    "LongTermDebtNoncurrent",
    "OperatingLeaseLiabilitiesNoncurrent",
    "FinanceLeaseLiabilitiesNoncurrent",
    "DeferredIncomeTaxLiabilitiesNoncurrent",
    "OtherLiabilitiesNoncurrent",
    "LiabilitiesNoncurrent",
    "Liabilities",
    "CommonStock",
    "PaidInCapitalCommonStock",
    "AccumulatedOtherIncome",
    "RetainedEarningsAccumulated",
    "Equity",
    "LiabilitiesAndEquity",
    "Debt",
    "ForeignTaxCreditCarryForward",
    "CapitalExpenditures",
    "OperatingCash",
    "ExcessCash",
    "VariableLeaseAssets"
]

@router.get("/api/central/financials/balance-sheet/{ticker}")
def get_balance_sheet_data(ticker: str):
    """Populates the historical columns of the Balance Sheet table."""
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:Metric {ticker: $ticker})
                WHERE m.metricName IN $metric_names
                RETURN m.metricName AS metricName, properties(m) AS props
                """,
                ticker=ticker_u,
                metric_names=BalanceSeet_metricName,
            )
            rows = [dict(r) for r in result]

            base_table = _build_statement_table(rows)
            if not base_table:
                raise HTTPException(status_code=404, detail=f"No balance sheet data found for {ticker_u}")

            years_sorted = sorted(base_table.keys())
            shaped = {
                str(y): {mn: base_table[y].get(mn) for mn in BalanceSeet_metricName}
                for y in years_sorted
            }
            return shaped
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch balance sheet")
        raise HTTPException(status_code=400, detail=f"Failed to fetch balance sheet: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass





# ======================================== okay
# 8. GET CASH FLOW
# ========================================
#curl -X GET "http://localhost:8080/api/central/financials/cash-flow/WMT" -H "Content-Type: application/json"

CashFlow_metrics = [
    "OperatingCashFlow",
    "NetIncome",
    "DepreciationAndAmortization",
    "OtherNoncashChanges",
    "DeferredTax",
    "AssetImpairmentCharge",
    "ShareBasedCompensation",
    "ChangeInWorkingCapital",
    "ChangeInReceivables",
    "ChangeInInventory",
    "ChangeInPayable",
    "ChangeInOtherCurrentAssets",
    "ChangeInOtherCurrentLiabilities",
    "ChangeInOtherWorkingCapital",
    "InvestingCashFlow",
    "PurchaseOfPPE",
    "SaleOfPPE",
    "PurchaseOfBusiness",
    "SaleOfBusiness",
    "PurchaseOfInvestment",
    "SaleOfInvestment",
    "OtherInvestingChanges",
    "FinancingCashFlow",
    "ShortTermDebtIssuance",
    "ShortTermDebtPayment",
    "LongTermDebtIssuance",
    "LongTermDebtPayment",
    "PaidInCapitalCommonStockIssuance",
    "PaidInCapitalCommonStockRepurchasePayment",
    "PaidInCapitalCommonStockDividendPayment",
    "TaxWithholdingPayment",
    "FinancingLeasePayment",
    "MinorityDividendPayment",
    "MinorityShareholderPayment"
]

@router.get("/api/central/financials/cash-flow/{ticker}")
def get_cash_flow_data(ticker: str):
    """Populates the historical columns of the Cash Flow table."""
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:Metric {ticker: $ticker})
                WHERE m.metricName IN $metric_names
                RETURN m.metricName AS metricName, properties(m) AS props
                """,
                ticker=ticker_u,
                metric_names=CashFlow_metrics,
            )
            rows = [dict(r) for r in result]

            base_table = _build_statement_table(rows)
            if not base_table:
                raise HTTPException(status_code=404, detail=f"No cash flow data found for {ticker_u}")

            years_sorted = sorted(base_table.keys())
            shaped = {
                str(y): {mn: base_table[y].get(mn) for mn in CashFlow_metrics}
                for y in years_sorted
            }
            return shaped
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch cash flow")
        raise HTTPException(status_code=400, detail=f"Failed to fetch cash flow: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass





# ---------------------------
# Analysis endpoints (computed from Metric nodes)
# ---------------------------

def _years_union(*series: Dict[int, float]) -> List[int]:
    ys: set[int] = set()
    for s in series:
        ys.update(s.keys())
    return sorted(ys)


def _build_year_keyed_payload(years: List[int], fn) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for y in years:
        out[str(y)] = fn(y)

    # remove empty years (all None)
    cleaned: Dict[str, Dict[str, Any]] = {}
    for y, payload in out.items():
        if any(v is not None for v in payload.values()):
            cleaned[y] = payload
    return cleaned


# ========================================  okay but have douts
# 9. GET NOPAT ANALYSIS
# ========================================
#curl -X GET "http://localhost:8080/api/central/analysis/nopat/WMT" -H "Content-Type: application/json"

@router.get("/api/central/analysis/nopat/{ticker}")
def get_nopat(ticker: str):
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:

            # Preferred direct node:
            _, nopat_series = _get_any_metric_series(session, ticker_u, ["NetOperatingProfitAfterTaxes"])
            # EBIT candidates
            _, ebit_series = _get_any_metric_series(session, ticker_u, ["EBITAAdjusted", "EBITAUnadjusted", "OperatingIncome"])
            # Tax candidates
            _, tax_series = _get_any_metric_series(session, ticker_u, ["TaxesNonoperating", "TaxProvision"])

            years = _years_union(nopat_series, ebit_series, tax_series)
            if not years:
                raise HTTPException(status_code=404, detail=f"No NOPAT-related data found for {ticker_u}")

            def per_year(y: int) -> Dict[str, Any]:
                ebit = ebit_series.get(y)
                cash_tax_adj = tax_series.get(y) if y in tax_series else None
                nopat = nopat_series.get(y)

                # If no direct NOPAT, approximate NOPAT = EBIT - TaxProvision (if tax exists)
                if nopat is None and ebit is not None:
                    tax_val = tax_series.get(y)
                    if tax_val is not None:
                        nopat = ebit - tax_val

                return {
                    "EBIT": ebit,
                    "CashTaxAdjustment": cash_tax_adj,
                    "NOPAT": nopat,
                }

            return _build_year_keyed_payload(years, per_year)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute NOPAT")
        raise HTTPException(status_code=400, detail=f"Failed to compute NOPAT: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass





# ========================================             okay
# 10. GET INVESTED CAPITAL
# ========================================
#curl -X GET "http://localhost:8080/api/central/analysis/invested-capital/WMT" -H "Content-Type: application/json"

@router.get("/api/central/analysis/invested-capital/{ticker}")
def get_invested_capital(ticker: str):
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            _, owc = _get_any_metric_series(session, ticker_u, ["OperatingWorkingCapital"])
            _, ppe = _get_any_metric_series(session, ticker_u, ["PropertyPlantAndEquipment"])
            _, ic = _get_any_metric_series(
                session,
                ticker_u,
                ["InvestedCapitalIncludingGoodwill", "InvestedCapitalExcludingGoodwill", "TotalFundsInvested"],
            )

            years = _years_union(owc, ppe, ic)

            if not years:
                raise HTTPException(status_code=404, detail=f"No invested-capital data found for {ticker_u}")

            def per_year(y: int) -> Dict[str, Any]:
                return {
                    "OperatingWorkingCapital": owc.get(y),
                    "NetPP&E": ppe.get(y),
                    "InvestedCapital": ic.get(y),
                }

            return _build_year_keyed_payload(years, per_year)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute invested capital")
        raise HTTPException(status_code=400, detail=f"Failed to compute invested capital: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



# ========================================   okay
# 11. GET FREE CASH FLOW ANALYSIS
# ========================================
#curl -X GET "http://localhost:8080/api/central/analysis/free-cash-flow/WMT" -H "Content-Type: application/json"

@router.get("/api/central/analysis/free-cash-flow/{ticker}")
def get_free_cash_flow_analysis(ticker: str):
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            # NOPAT
            _, nopat = _get_any_metric_series(session, ticker_u, ["NetOperatingProfitAfterTaxes"])
            if not nopat:
                # fallback compute from EBIT/Tax
                _, ebit = _get_any_metric_series(session, ticker_u, ["EBITAAdjusted", "OperatingIncome"])
                _, tax = _get_any_metric_series(session, ticker_u, ["TaxProvision"])
                for y in _years_union(ebit, tax):
                    if y in ebit and y in tax and ebit.get(y) is not None and tax.get(y) is not None:
                        nopat[y] = ebit[y] - tax[y]

            # Invested capital (for delta)
            _, ic = _get_any_metric_series(
                session,
                ticker_u,
                ["InvestedCapitalIncludingGoodwill", "InvestedCapitalExcludingGoodwill", "TotalFundsInvested"],
            )

            # Direct free cash flow metric if present
            _, fcf = _get_any_metric_series(session, ticker_u, ["FreeCashFlow"])

            years = _years_union(nopat, ic, fcf)
            if not years:
                raise HTTPException(status_code=404, detail=f"No free-cash-flow data found for {ticker_u}")

            years_sorted = sorted(years)

            def per_year(y: int) -> Dict[str, Any]:
                # Change in invested capital = IC(y) - IC(y-1)
                change_ic = None
                if y in ic and (y - 1) in ic and ic.get(y) is not None and ic.get(y - 1) is not None:
                    change_ic = ic[y] - ic[y - 1]

                computed_fcf = None
                if nopat.get(y) is not None and change_ic is not None:
                    computed_fcf = nopat[y] - change_ic

                return {
                    "NOPAT": nopat.get(y),
                    "ChangeInInvestedCapital": change_ic,
                    "FreeCashFlow": fcf.get(y) if fcf.get(y) is not None else computed_fcf,
                }

            return _build_year_keyed_payload(years_sorted, per_year)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute free cash flow")
        raise HTTPException(status_code=400, detail=f"Failed to compute free cash flow: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass




# ========================================   # okay
# 12. GET ROIC BREAKDOWN
# ========================================
# curl -X GET "http://localhost:8080/api/central/analysis/roic/WMT" -H "Content-Type: application/json"

@router.get("/api/central/analysis/roic/{ticker}")
def get_roic_breakdown(ticker: str):
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            # Use direct metric if it exists
            _, roic = _get_any_metric_series(session, ticker_u, ["ReturnOnInvestedCapitalIncludingGoodwill"])

            # Revenue + invested capital + nopat
            _, revenue = _get_any_metric_series(session, ticker_u, ["Revenue"])
            _, ic = _get_any_metric_series(
                session,
                ticker_u,
                ["InvestedCapitalIncludingGoodwill", "InvestedCapitalExcludingGoodwill", "TotalFundsInvested"],
            )
            _, nopat = _get_any_metric_series(session, ticker_u, ["NetOperatingProfitAfterTaxes"])

            years = _years_union(roic, revenue, ic, nopat)
            if not years:
                raise HTTPException(status_code=404, detail=f"No ROIC data found for {ticker_u}")

            def per_year(y: int) -> Dict[str, Any]:
                rev = revenue.get(y)
                icv = ic.get(y)
                nop = nopat.get(y)

                nopat_margin = (nop / rev) if (nop is not None and rev and rev != 0) else None
                ic_turnover = (rev / icv) if (rev is not None and icv and icv != 0) else None
                roic_calc = (nop / icv) if (nop is not None and icv and icv != 0) else None

                return {
                    "NOPATMargin": nopat_margin,
                    "InvestedCapitalTurnover": ic_turnover,
                    "ROIC": roic.get(y) if roic.get(y) is not None else roic_calc,
                }

            return _build_year_keyed_payload(years, per_year)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute ROIC breakdown")
        raise HTTPException(status_code=400, detail=f"Failed to compute ROIC breakdown: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



# ========================================   okay
# 13. GET OPERATIONAL PERFORMANCE
# ========================================
#curl -X GET "http://localhost:8080/api/central/analysis/operational-performance/WMT" -H "Content-Type: application/json"

@router.get("/api/central/analysis/operational-performance/{ticker}")
def get_operational_performance(ticker: str):
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            _, revenue = _get_any_metric_series(session, ticker_u, ["Revenue"])
            _, revenue_growth = _get_any_metric_series(session, ticker_u, ["RevenueGrowthRate"])
            _, ebitda = _get_any_metric_series(session, ticker_u, ["EBITDAAdjusted", "EBITDA"])

            years = _years_union(revenue, revenue_growth, ebitda)
            if not years:
                raise HTTPException(status_code=404, detail=f"No operational performance data found for {ticker_u}")

            def per_year(y: int) -> Dict[str, Any]:
                # If RevenueGrowthRate missing, compute YoY from revenue
                rg = revenue_growth.get(y)
                if rg is None and y in revenue and (y - 1) in revenue and revenue.get(y - 1):
                    rg = (revenue[y] - revenue[y - 1]) / revenue[y - 1]

                rev = revenue.get(y)
                e = ebitda.get(y)
                ebitda_margin = (e / rev) if (e is not None and rev and rev != 0) else None

                return {
                    "RevenueGrowth": rg,
                    "EBITDAMargin": ebitda_margin,
                }

            return _build_year_keyed_payload(years, per_year)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute operational performance")
        raise HTTPException(status_code=400, detail=f"Failed to compute operational performance: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


# ========================================
# 14. GET FINANCING HEALTH
# ========================================
# curl -X GET "http://localhost:8080/api/central/analysis/financing-health/WMT" -H "Content-Type: application/json"

@router.get("/api/central/analysis/financing-health/{ticker}")
def get_financing_health(ticker: str):
    ticker_u = ticker.strip().upper()
    driver = _get_driver()
    try:
        with driver.session() as session:
            # Debt + cash
            _, debt = _get_any_metric_series(session, ticker_u, ["Debt", "DebtAndDebtEquivalents"])
            _, cash = _get_any_metric_series(session, ticker_u, ["CashAndCashEquivalents", "Cash"])

            # EBITDA and EBIT and interest
            _, ebitda = _get_any_metric_series(session, ticker_u, ["EBITDAAdjusted", "EBITDA"])
            _, ebit = _get_any_metric_series(session, ticker_u, ["EBITAAdjusted", "OperatingIncome"])
            _, interest = _get_any_metric_series(session, ticker_u, ["InterestExpense", "InterestExpenseDebt", "InterestExpenseFinance", "InterestExpense"])  # noqa

            years = _years_union(debt, cash, ebitda, ebit, interest)
            if not years:
                raise HTTPException(status_code=404, detail=f"No financing health data found for {ticker_u}")

            def per_year(y: int) -> Dict[str, Any]:
                d = debt.get(y)
                c = cash.get(y)
                net_debt = (d - c) if (d is not None and c is not None) else None

                e = ebitda.get(y)
                net_debt_to_ebitda = (net_debt / e) if (net_debt is not None and e and e != 0) else None

                eb = ebit.get(y)
                i = interest.get(y)
                interest_cov = (eb / i) if (eb is not None and i and i != 0) else None

                return {
                    "NetDebt": net_debt,
                    "NetDebtToEBITDA": net_debt_to_ebitda,
                    "InterestCoverage": interest_cov,
                }

            return _build_year_keyed_payload(years, per_year)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute financing health")
        raise HTTPException(status_code=400, detail=f"Failed to compute financing health: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass
