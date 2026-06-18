"""
investment_metrics_tool
"""

from langchain.tools import tool
from typing import Dict, Any, List
import logging
import math
from datetime import datetime
from neo4j import GraphDatabase
import json

from config import get_config
from app.utills.tool_output_collector import add_tool_output

logger = logging.getLogger(__name__)
config = get_config()

NEO4J_URI = config.NEO4J_URI
NEO4J_USERNAME = config.NEO4J_USERNAME
NEO4J_PASSWORD = config.NEO4J_PASSWORD

tool_outputs = {}


def _get_driver():
    """Create Neo4j driver connection"""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def _is_valid_number(val, positive=False):
    """Check if value is a valid number"""
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


def get_roic_5y_avg(driver, ticker):
    """Get 5-year average ROIC from ReturnOnInvestedCapitalIncludingGoodwill"""
    # Align with `get_special_metric_data_router.py`
    metric_name = "ReturnOnInvestedCapitalInclGoodwill"
    current_year = datetime.now().year
    years = [current_year - i for i in range(1, 6)]
    year_props = [f"year_{y}" for y in years]
    return_fields = ", ".join([f"m.{p} AS {p}" for p in year_props])
    
    query = f"""
        MATCH (m:Metric {{ticker: $ticker, metricName: $metric_name}})
        RETURN {return_fields}
    """
    
    with driver.session() as session:
        row = session.run(query, ticker=ticker, metric_name=metric_name).single()
    
    if not row:
        return None
    
    values = []
    for p in year_props:
        val = row.get(p)
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            values.append(float(val))
    
    return sum(values) / len(values) if values else None


def get_net_income_5y_avg(driver, ticker):
    """Get 5-year average Net Income"""
    metric_name = "NetIncome"
    current_year = datetime.now().year
    years = [current_year - i for i in range(1, 6)]
    year_props = [f"year_{y}" for y in years]
    return_fields = ", ".join([f"m.{p} AS {p}" for p in year_props])
    
    query = f"""
        MATCH (m:Metric {{ticker: $ticker, metricName: $metric_name}})
        RETURN {return_fields}
    """
    
    with driver.session() as session:
        row = session.run(query, ticker=ticker, metric_name=metric_name).single()
    
    if not row:
        return None
    
    values = []
    for p in year_props:
        val = row.get(p)
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            values.append(float(val))
    
    return sum(values) / len(values) if values else None


def get_intrinsic_value(driver, ticker):
    """Get intrinsic value from the ValuationSummary node.

    This aligns with `get_special_metric_data_router.py`:
      MATCH (m:Metric_ValuationSummary {ticker, metricName:"ValuationSummary"})
      RETURN m.EnterpriseValue_PresentValue
    """
    metric_name = "ValuationSummary"
    query = """
        MATCH (m:Metric_ValuationSummary {ticker: $ticker, metricName: $metric_name})
        RETURN m.EnterpriseValue_PresentValue AS intrinsic_value
    """

    with driver.session() as session:
        row = session.run(query, ticker=ticker, metric_name=metric_name).single()

    if not row:
        return None

    v = row.get("intrinsic_value")
    if v is not None and not (isinstance(v, float) and math.isnan(v)):
        return float(v)
    return None


# ==============================
# SpecilMetricCache utilities (Neo4j-only; no external API calls)
# ==============================

def get_SpecilMetricCache_node_data(driver, ticker):
    """Read cached market data from Neo4j :SpecilMetricCache.

    Expected properties (as produced by special-metrics router):
      - price
      - shares_outstanding
      - market_cap (optional; we re-compute anyway)

    Note: we intentionally DO NOT enforce "today-only" cache in this tool.
    """
    query = """
    MATCH (c:SpecilMetricCache {ticker: $ticker})
    RETURN c.price AS price,
           c.shares_outstanding AS shares_outstanding,
           c.market_cap AS market_cap,
           c.timestamp AS timestamp,
           c.cache_date AS cache_date
    """

    with driver.session() as session:
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


def _calculate_market_cap(price, shares_outstanding):
    """Compute Market Cap = Stock Price × Shares Outstanding."""
    if not _is_valid_number(price, positive=True):
        return None
    if not _is_valid_number(shares_outstanding, positive=True):
        return None
    try:
        return float(price) * float(shares_outstanding)
    except Exception:
        return None


@tool
def investment_metrics_calculator_tool(symbols: Any) -> str:
    """
    Calculate 9 key investment metrics for one or more stock tickers.
    
    Args:
        symbols: Accepts any of the following formats:
                 - List[str] of tickers, e.g. ["AAPL", "MSFT", "AMZN"]
                 - Comma-separated string, e.g. "AAPL,MSFT,AMZN"
                 - Single ticker string, e.g. "AAPL"
    
    Returns:
        A dictionary with keys:
        - tickers: list of processed tickers
        - results: list of per-ticker results. Each item contains:
            1. roic_5y_avg
            2. net_income_5y_avg
            3. shares_outstanding
            4. market_cap
            5. current_price
            6. intrinsic_value
            7. eps_5y_avg (derived)
            8. earnings_yield (derived)
            9. intrinsic_to_mc (derived)
           plus validation_errors for that ticker if any required data missing/invalid.
    """
    logger.info(f">>>>>>>>>>> Executing investment_metrics_calculator_tool for symbols={symbols}")

    # Normalize input into list of upper-case tickers
    tickers: List[str] = []
    try:
        if isinstance(symbols, list):
            tickers = [str(s).upper().strip() for s in symbols if str(s).strip()]
        elif isinstance(symbols, str):
            s = symbols.strip()
            if s.startswith('[') and s.endswith(']'):
                parsed = json.loads(s)
                tickers = [str(x).upper().strip() for x in parsed if str(x).strip()]
            elif ',' in s:
                tickers = [part.upper().strip() for part in s.split(',') if part.strip()]
            elif s:
                tickers = [s.upper()]
        else:
            # Fallback: try string conversion
            s = str(symbols).strip()
            if s:
                tickers = [s.upper()]
    except Exception as e:
        logger.error(f"Failed to parse symbols input: {e}")
        return str({"error": f"Invalid input format for symbols: {symbols}"})

    # Deduplicate while preserving order
    seen = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]

    if not tickers:
        return str({"error": "No valid tickers provided"})

    driver = None
    try:
        driver = _get_driver()

        all_results = []

        for ticker in tickers:
            try:
                logger.info(f"Fetching metrics for {ticker}...")

                roic_5y_avg = get_roic_5y_avg(driver, ticker)
                net_income_5y_avg = get_net_income_5y_avg(driver, ticker)

                cache = get_SpecilMetricCache_node_data(driver, ticker) or {}
                shares_outstanding = cache.get('shares_outstanding')
                current_price = cache.get('price')
                market_cap = _calculate_market_cap(current_price, shares_outstanding)
                intrinsic_value = get_intrinsic_value(driver, ticker)

                margin_of_safety = None
                if _is_valid_number(intrinsic_value, positive=True) and _is_valid_number(current_price, positive=True):
                    # same formula used in special-metrics router
                    margin_of_safety = 1.0 - (float(current_price) / float(intrinsic_value))

                per_result = {
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
                    "validation_errors": {}
                }

                # Validate and calculate derived metrics
                errors = {}
                if not _is_valid_number(roic_5y_avg, positive=False):
                    errors['roic'] = 'missing or NaN'
                if not _is_valid_number(net_income_5y_avg, positive=False):
                    errors['net_income_5y_avg'] = 'missing or NaN'
                if not _is_valid_number(shares_outstanding, positive=True):
                    errors['shares_outstanding'] = 'missing, NaN, or <= 0'
                if not _is_valid_number(market_cap, positive=True):
                    errors['market_cap'] = 'missing, NaN, or <= 0'
                if not _is_valid_number(current_price, positive=True):
                    errors['current_price'] = 'missing, NaN, or <= 0'
                if not _is_valid_number(intrinsic_value, positive=True):
                    errors['intrinsic_value'] = 'missing, NaN, or <= 0'

                # margin_of_safety is derived (does not block other derived metrics)
                if margin_of_safety is None:
                    # Only mark as error if its inputs are present but invalid
                    # (keeps backward compatibility for callers who only care about the first 9 metrics)
                    if _is_valid_number(intrinsic_value, positive=True) and not _is_valid_number(current_price, positive=True):
                        errors['margin_of_safety'] = 'missing/invalid current_price'

                if not errors:
                    eps_5y_avg = float(net_income_5y_avg) / float(shares_outstanding)
                    per_result["metrics"]["7_eps_5y_avg"] = eps_5y_avg

                    earnings_yield = eps_5y_avg / float(current_price)
                    per_result["metrics"]["8_earnings_yield"] = earnings_yield

                    intrinsic_to_mc = float(intrinsic_value) / float(market_cap)
                    per_result["metrics"]["9_intrinsic_to_mc"] = intrinsic_to_mc

                    logger.info(f"Successfully calculated all 9 metrics for {ticker}")
                else:
                    per_result["validation_errors"] = errors
                    logger.warning(f"Could not calculate derived metrics for {ticker} due to validation errors: {errors}")

                all_results.append(per_result)

            except Exception as e_ticker:
                logger.error(f"Error calculating metrics for {ticker}: {e_ticker}")
                all_results.append({
                    "ticker": ticker,
                    "metrics": {},
                    "validation_errors": {"exception": str(e_ticker)}
                })

        output = {"tickers": tickers, "results": all_results}

        # Log tool output once
        tool_output = {
            'tool_name': "investment_metrics_calculator_tool",
            'input_arguments': {'symbols': symbols},
            'tool_output': str(output)
        }
        try:
            add_tool_output(tool_output)
        except Exception:
            pass

        return str(output)

    except Exception as e:
        error_msg = f"Error calculating investment metrics: {str(e)}"
        logger.error(error_msg)
        return error_msg

    finally:
        if driver:
            try:
                driver.close()
            except Exception:
                pass
