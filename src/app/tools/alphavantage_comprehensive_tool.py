"""src.app.tools.alphavantage_comprehensive_tool

Self-contained "comprehensive" wrapper around AlphaVantage endpoints + internal
Neo4j-based investment metrics.

NOTE (per user request): this file intentionally **does not** import the other
tool modules (investment_metrics_calculator_tool, alphavantage_* tools). The
logic is implemented inline here, even if it makes this module larger.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import json
import logging
import math
from datetime import datetime

import requests
from neo4j import GraphDatabase
from langchain.tools import tool

from config import get_config
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

config = get_config()
ALPHA_VANTAGE_API_KEY = config.ALPHA_VANTAGE_API_KEY
ALPHA_VANTAGE_BASE_URL = config.ALPHA_VANTAGE_BASE_URL
NEO4J_URI = config.NEO4J_URI
NEO4J_USERNAME = config.NEO4J_USERNAME
NEO4J_PASSWORD = config.NEO4J_PASSWORD


def _normalize_tickers(tickers: Union[str, List[str], None]) -> List[str]:
    """Normalize tickers input into list[str] (upper-case, de-duped, order-preserving)."""
    if tickers is None:
        return []

    parsed: List[str] = []
    if isinstance(tickers, list):
        parsed = [str(t).strip() for t in tickers]
    else:
        s = str(tickers).strip()
        if not s:
            parsed = []
        elif s.startswith("[") and s.endswith("]"):
            # allow JSON list in string form
            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    parsed = [str(t).strip() for t in arr]
                else:
                    parsed = [s]
            except Exception:
                parsed = [s]
        elif "," in s:
            parsed = [p.strip() for p in s.split(",")]
        else:
            parsed = [s]

    # normalize, remove empties
    normalized = [t.upper() for t in parsed if t]

    # de-dupe preserve order
    seen = set()
    out = [t for t in normalized if not (t in seen or seen.add(t))]
    return out


def _safe_tool_call(fn, **kwargs) -> Dict[str, Any]:
    """Call a tool and catch exceptions.

    We store both the kwargs and the output so the caller always gets a stable structure.
    """
    try:
        # langchain @tool decorated callables are often BaseTool instances.
        # In that case, use .invoke(input_dict) instead of calling directly.
        if hasattr(fn, "invoke"):
            output = fn.invoke(kwargs)
        else:
            output = fn(**kwargs)
        return {"input": kwargs, "output": output, "error": None}
    except Exception as e:
        return {"input": kwargs, "output": None, "error": str(e)}


# =====================================================================================
# Inline AlphaVantage retrieval functions
# =====================================================================================

def _av_company_overview(symbol: str) -> str:
    """AlphaVantage OVERVIEW."""
    params = {"function": "OVERVIEW", "symbol": (symbol or "").upper().strip(), "apikey": ALPHA_VANTAGE_API_KEY}
    resp = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
    data = resp.json()
    if not data:
        return f"No data found for symbol: {symbol}"
    return str(data)


def _av_daily_stock(symbol: str, days: int = 30, datatype: str = "json") -> str:
    """AlphaVantage TIME_SERIES_DAILY (raw, unadjusted)."""
    valid_datatypes = ("json", "csv")
    if datatype not in valid_datatypes:
        return f"Invalid datatype. Must be one of: {', '.join(valid_datatypes)}"
    if days <= 0:
        return "Error: 'days' parameter must be greater than 0"

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": (symbol or "").upper().strip(),
        "datatype": datatype,
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    resp = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)

    if datatype == "csv":
        if resp.status_code != 200:
            return f"Error fetching CSV data: HTTP {resp.status_code}"
        csv_lines = resp.text.split("\n")
        filtered_csv = "\n".join(csv_lines[: days + 1])  # +1 header
        return filtered_csv

    data = resp.json()
    if not data:
        return f"No data found for symbol: {symbol}"
    for k in ("Error Message", "Note", "Information"):
        if k in data:
            return f"API {k}: {data.get(k)}"

    modified = dict(data)
    ts = modified.get("Time Series (Daily)")
    if isinstance(ts, dict):
        modified["Time Series (Daily)"] = dict(list(ts.items())[:days])
    return str(modified)


def _av_earnings_call_transcript(symbol: str, quarter: Optional[str] = None) -> str:
    """AlphaVantage EARNINGS_CALL_TRANSCRIPT.

    Returns top 3 executive statements sorted by sentiment, similar to previous tool.
    """
    params = {
        "function": "EARNINGS_CALL_TRANSCRIPT",
        "symbol": (symbol or "").upper().strip(),
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    if quarter:
        params["quarter"] = quarter

    resp = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
    data = resp.json()
    transcript = data.get("transcript") if isinstance(data, dict) else None
    if not isinstance(transcript, list):
        return str(data)

    executive_keywords = ("ceo", "cfo", "chief", "president")
    executive_transcripts = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").lower()
        if any(k in title for k in executive_keywords):
            executive_transcripts.append(item)

    def _sent(v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return float("-inf")

    top3 = sorted(executive_transcripts, key=lambda x: _sent(x.get("sentiment")), reverse=True)[:3]
    return str(top3)


def _av_market_news_and_sentiment(
    tickers: Optional[str] = None,
    topics: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    sort_order: str = "LATEST",
    limit: int = 50,
) -> str:
    """AlphaVantage NEWS_SENTIMENT.

    Returns a truncated feed (first 10 items) like previous tool.
    """
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": tickers,
        "topics": topics,
        "time_from": time_from,
        "time_to": time_to,
        "sort": sort_order,
        "limit": limit,
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    resp = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
    data = resp.json()
    if not data:
        return f"No data found for tickers: {tickers}"

    if isinstance(data, dict) and isinstance(data.get("feed"), list):
        modified = dict(data)
        modified["feed"] = data["feed"][:10]
        return str(modified)

    return str(data)


# =====================================================================================
# Inline Neo4j-based investment metrics (copied from investment_metrics_calculator_tool)
# =====================================================================================

def _neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def _is_valid_number(val, positive: bool = False) -> bool:
    try:
        if val is None:
            return False
        f = float(val)
        if isinstance(f, float) and math.isnan(f):
            return False
        if positive and f <= 0:
            return False
        return True
    except (TypeError, ValueError):
        return False


def _calculate_market_cap(price, shares_outstanding):
    if not _is_valid_number(price, positive=True):
        return None
    if not _is_valid_number(shares_outstanding, positive=True):
        return None
    try:
        return float(price) * float(shares_outstanding)
    except Exception:
        return None


def _get_roic_5y_avg(session, ticker: str) -> Optional[float]:
    metric_name = "ReturnOnInvestedCapitalInclGoodwill"
    current_year = datetime.now().year
    years = [current_year - i for i in range(1, 6)]
    year_props = [f"year_{y}" for y in years]
    return_fields = ", ".join([f"m.{p} AS {p}" for p in year_props])
    query = f"""
        MATCH (m:Metric {{ticker: $ticker, metricName: $metric_name}})
        RETURN {return_fields}
    """
    row = session.run(query, ticker=ticker, metric_name=metric_name).single()
    if not row:
        return None
    vals = []
    for p in year_props:
        v = row.get(p)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            vals.append(float(v))
    return float(sum(vals) / len(vals)) if vals else None


def _get_net_income_5y_avg(session, ticker: str) -> Optional[float]:
    metric_name = "NetIncome"
    current_year = datetime.now().year
    years = [current_year - i for i in range(1, 6)]
    year_props = [f"year_{y}" for y in years]
    return_fields = ", ".join([f"m.{p} AS {p}" for p in year_props])
    query = f"""
        MATCH (m:Metric {{ticker: $ticker, metricName: $metric_name}})
        RETURN {return_fields}
    """
    row = session.run(query, ticker=ticker, metric_name=metric_name).single()
    if not row:
        return None
    vals = []
    for p in year_props:
        v = row.get(p)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            vals.append(float(v))
    return float(sum(vals) / len(vals)) if vals else None


def _get_intrinsic_value(session, ticker: str) -> Optional[float]:
    metric_name = "ValuationSummary"
    query = """
        MATCH (m:Metric_ValuationSummary {ticker: $ticker, metricName: $metric_name})
        RETURN m.EnterpriseValue_PresentValue AS intrinsic_value
    """
    row = session.run(query, ticker=ticker, metric_name=metric_name).single()
    if not row:
        return None
    v = row.get("intrinsic_value")
    if v is not None and not (isinstance(v, float) and math.isnan(v)):
        return float(v)
    return None


def _get_specil_metric_cache(session, ticker: str) -> Optional[Dict[str, Any]]:
    query = """
    MATCH (c:SpecilMetricCache {ticker: $ticker})
    RETURN c.price AS price,
           c.shares_outstanding AS shares_outstanding,
           c.market_cap AS market_cap,
           c.timestamp AS timestamp,
           c.cache_date AS cache_date
    """
    row = session.run(query, ticker=ticker).single()
    if not row:
        return None
    return {
        "price": row.get("price"),
        "shares_outstanding": row.get("shares_outstanding"),
        "market_cap": row.get("market_cap"),
        "timestamp": row.get("timestamp"),
        "cache_date": row.get("cache_date"),
    }


def _investment_metrics_calculator(symbols: Any) -> str:
    """Inline version of `investment_metrics_calculator_tool`.

    Returns a stringified dict identical in spirit to the existing tool.
    """
    # Normalize input into list of upper-case tickers
    tickers: List[str] = []
    try:
        if isinstance(symbols, list):
            tickers = [str(s).upper().strip() for s in symbols if str(s).strip()]
        elif isinstance(symbols, str):
            s = symbols.strip()
            if s.startswith("[") and s.endswith("]"):
                parsed = json.loads(s)
                tickers = [str(x).upper().strip() for x in parsed if str(x).strip()]
            elif "," in s:
                tickers = [part.upper().strip() for part in s.split(",") if part.strip()]
            elif s:
                tickers = [s.upper()]
        else:
            s = str(symbols).strip()
            if s:
                tickers = [s.upper()]
    except Exception as e:
        return str({"error": f"Invalid input format for symbols: {symbols}", "exception": str(e)})

    # Deduplicate while preserving order
    seen = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]
    if not tickers:
        return str({"error": "No valid tickers provided"})

    driver = _neo4j_driver()
    try:
        results = []
        with driver.session() as session:
            for ticker in tickers:
                try:
                    roic_5y_avg = _get_roic_5y_avg(session, ticker)
                    net_income_5y_avg = _get_net_income_5y_avg(session, ticker)
                    cache = _get_specil_metric_cache(session, ticker) or {}
                    shares_outstanding = cache.get("shares_outstanding")
                    current_price = cache.get("price")
                    market_cap = _calculate_market_cap(current_price, shares_outstanding)
                    intrinsic_value = _get_intrinsic_value(session, ticker)

                    margin_of_safety = None
                    if _is_valid_number(intrinsic_value, positive=True) and _is_valid_number(current_price, positive=True):
                        margin_of_safety = 1.0 - (float(current_price) / float(intrinsic_value))

                    per = {
                        "ticker": ticker,
                        "metrics": {
                            "1_roic": roic_5y_avg,
                            "2_net_income_5y_avg": net_income_5y_avg,
                            "3_shares_outstanding": shares_outstanding,
                            "4_market_cap": market_cap,
                            "5_current_price": current_price,
                            "6_intrinsic_value": intrinsic_value,
                            "7_eps_5y_avg": None,
                            "8_earnings_yield": None,
                            "9_intrinsic_to_mc": None,
                            "10_margin_of_safety": margin_of_safety,
                        },
                        "validation_errors": {},
                    }

                    errors = {}
                    if not _is_valid_number(roic_5y_avg, positive=False):
                        errors["roic"] = "missing or NaN"
                    if not _is_valid_number(net_income_5y_avg, positive=False):
                        errors["net_income_5y_avg"] = "missing or NaN"
                    if not _is_valid_number(shares_outstanding, positive=True):
                        errors["shares_outstanding"] = "missing, NaN, or <= 0"
                    if not _is_valid_number(market_cap, positive=True):
                        errors["market_cap"] = "missing, NaN, or <= 0"
                    if not _is_valid_number(current_price, positive=True):
                        errors["current_price"] = "missing, NaN, or <= 0"
                    if not _is_valid_number(intrinsic_value, positive=True):
                        errors["intrinsic_value"] = "missing, NaN, or <= 0"

                    if not errors:
                        eps_5y_avg = float(net_income_5y_avg) / float(shares_outstanding)
                        per["metrics"]["7_eps_5y_avg"] = eps_5y_avg
                        per["metrics"]["8_earnings_yield"] = eps_5y_avg / float(current_price)
                        per["metrics"]["9_intrinsic_to_mc"] = float(intrinsic_value) / float(market_cap)
                    else:
                        per["validation_errors"] = errors

                    results.append(per)
                except Exception as e_ticker:
                    results.append({"ticker": ticker, "metrics": {}, "validation_errors": {"exception": str(e_ticker)}})

        output = {"tickers": tickers, "results": results}
        return str(output)
    finally:
        try:
            driver.close()
        except Exception:
            pass


@tool
def alphavantage_comprehensive_tool(
    tickers: Union[str, List[str]],
    numberof_days_to_retrive_daily_stock: int = 30,
    quarter_for_earnings_call_transcript: Optional[str] = None,
    topics_for_market_news_and_sentiment: Optional[str] = None,
    time_from_for_market_news_and_sentiment: Optional[str] = None,
    time_to_for_market_news_and_sentiment: Optional[str] = None,
    sort_order_for_market_news_and_sentiment: str = "LATEST",
    limit_for_market_news_and_sentiment: int = 50,
    datatype_for_daily_stock: str = "json",
) -> str:
    """Run a bundled set of AlphaVantage + internal tools for one or more tickers.

    Args:
        tickers: List[str] or comma-separated string or JSON-list string.
        numberof_days_to_retrive_daily_stock: Days of daily candles to fetch per ticker.
        quarter_for_earnings_call_transcript: Quarter in the form YYYYQN (e.g., 2024Q1).
        topics_for_market_news_and_sentiment: AlphaVantage NEWS_SENTIMENT topics CSV.
        time_from_for_market_news_and_sentiment: YYYYMMDDTHHMM.
        time_to_for_market_news_and_sentiment: YYYYMMDDTHHMM.
        sort_order_for_market_news_and_sentiment: LATEST | EARLIEST | RELEVANCE.
        limit_for_market_news_and_sentiment: Max number of news items from AV.
        datatype_for_daily_stock: json | csv.

    Returns:
        String representation of a dict with separate sections per sub-tool.
        Example keys:
          - investment_metrics
          - company_overview_by_ticker
          - earnings_call_transcript_by_ticker
          - daily_stock_by_ticker
          - market_news_and_sentiment
    """

    logger.info(">>>>>>>>>>> Executing alphavantage_comprehensive_tool with tickers=%s", tickers
    )

    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        return str({"error": "No valid tickers provided", "input": {"tickers": tickers}})

    # 1) Investment metrics (inline Neo4j implementation)
    investment_metrics = _safe_tool_call(_investment_metrics_calculator, symbols=normalized_tickers)

    # 2) Per-ticker AlphaVantage calls
    company_overview_by_ticker: Dict[str, Any] = {}
    earnings_call_transcript_by_ticker: Dict[str, Any] = {}
    daily_stock_by_ticker: Dict[str, Any] = {}

    for t in normalized_tickers:
        company_overview_by_ticker[t] = _safe_tool_call(_av_company_overview, symbol=t)

        earnings_call_transcript_by_ticker[t] = _safe_tool_call(
            _av_earnings_call_transcript,
            symbol=t,
            quarter=quarter_for_earnings_call_transcript,
        )

        daily_stock_by_ticker[t] = _safe_tool_call(
            _av_daily_stock,
            symbol=t,
            days=numberof_days_to_retrive_daily_stock,
            datatype=datatype_for_daily_stock,
        )

    # 3) Market news can accept comma-separated tickers; we request once
    market_news_and_sentiment = _safe_tool_call(
        _av_market_news_and_sentiment,
        tickers=",".join(normalized_tickers),
        topics=topics_for_market_news_and_sentiment,
        time_from=time_from_for_market_news_and_sentiment,
        time_to=time_to_for_market_news_and_sentiment,
        sort_order=sort_order_for_market_news_and_sentiment,
        limit=limit_for_market_news_and_sentiment,
    )

    result = {
        "input": {
            "tickers": normalized_tickers,
            "numberof_days_to_retrive_daily_stock": numberof_days_to_retrive_daily_stock,
            "quarter_for_earnings_call_transcript": quarter_for_earnings_call_transcript,
            "topics_for_market_news_and_sentiment": topics_for_market_news_and_sentiment,
            "time_from_for_market_news_and_sentiment": time_from_for_market_news_and_sentiment,
            "time_to_for_market_news_and_sentiment": time_to_for_market_news_and_sentiment,
            "sort_order_for_market_news_and_sentiment": sort_order_for_market_news_and_sentiment,
            "limit_for_market_news_and_sentiment": limit_for_market_news_and_sentiment,
            "datatype_for_daily_stock": datatype_for_daily_stock,
        },
        "investment_metrics": investment_metrics,
        "company_overview_by_ticker": company_overview_by_ticker,
        "earnings_call_transcript_by_ticker": earnings_call_transcript_by_ticker,
        "daily_stock_by_ticker": daily_stock_by_ticker,
        "market_news_and_sentiment": market_news_and_sentiment,
    }

    # Log combined tool output
    try:
        add_tool_output(
            {
                "tool_name": "alphavantage_comprehensive_tool",
                "input_arguments": result["input"],
                "tool_output": str(result),
            }
        )
    except Exception:
        pass

    return str(result)
