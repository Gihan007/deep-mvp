from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List, Literal
from config import get_config
from neo4j import GraphDatabase
import logging
import os
import requests
from datetime import datetime, timedelta
import math
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

# ReturnOnInvestedCapitalInclGoodwill
# NetOperatingProfitAfterTaxes


router = APIRouter()
logger = logging.getLogger(__name__)
config = get_config()

NEO4J_URI = config.NEO4J_URI
NEO4J_USERNAME = config.NEO4J_USERNAME
NEO4J_PASSWORD = config.NEO4J_PASSWORD
ALPHA_VANTAGE_API_KEY = config.ALPHA_VANTAGE_API_KEY
USE_ONLY_CACHE_NODES = str(getattr(config, "USE_ONLY_CACHE_NODES", "false")).strip().lower() in ("1","true","yes","on")

# =====================================================================================
# Top-level flags / defaults
# =====================================================================================
# NOTE: These are defaults for `refresh_special_metric_cache_all`.
# You can change them here (or wire them to env/config later).
SPECIAL_METRIC_CACHE_PRIMARY_SOURCE = str(getattr(config, "SPECIAL_METRIC_CACHE_PRIMARY_SOURCE", "alphavantage")).strip().lower()
SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS = int(getattr(config, "SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS", 10))
SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS = int(getattr(config, "SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS",5))
SPECIAL_METRIC_OLD_CACHE_YAHOO_MAX_WORKERS = int(getattr(config, "SPECIAL_METRIC_OLD_CACHE_YAHOO_MAX_WORKERS", 10))


def _temp_charts_dir() -> Path:
    """Return absolute path to a temporary charts directory.
    
    Uses system temp directory to avoid cluttering the workspace.
    """
    import tempfile
    temp_dir = Path(tempfile.gettempdir()) / "get_deep_charts"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _log_and_raise_500(msg: str, exc: Exception) -> None:
    """Log full traceback and raise a clean HTTP 500.

    This avoids silent failures where clients only see a generic 500 while server logs
    show nothing useful.
    """
    logger.exception(msg)
    raise HTTPException(status_code=500, detail=f"{msg}: {exc}")


def _progress_log(
    message: str,
    *,
    ticker: Optional[str] = None,
    stage: Optional[str] = None,
    level: int = logging.INFO,
) -> None:
    """Emit progress logs that are visible in common FastAPI deployments.

    Why both logger + print?
      - `logger` integrates with uvicorn/gunicorn logging.
      - `print(..., flush=True)` is a fallback in environments where logging is misconfigured.
    """
    t = (ticker or "").upper().strip()
    prefix = ""
    if t:
        prefix += f"[{t}] "
    if stage:
        prefix += f"({stage}) "
    full = f"{prefix}{message}".strip()

    try:
        logger.log(level, full)
    except Exception:
        # Never break endpoint due to logging
        pass
    try:
        print(full, flush=True)
    except Exception:
        pass


class TickerRequest(BaseModel):
    ticker: str

class TickersRequest(BaseModel):
    tickers: List[str] = Field(default_factory=list, description="Explicit list of tickers (ignored if user_query is provided)")
    user_query: Optional[str] = Field(
        default=None,
        description="Natural language query to select tickers from the Knowledge Graph. If provided, this will be used instead of `tickers`.",
    )


class MultiplesTableMetricRequest(BaseModel):
    ticker: str = Field(..., description="Company ticker, e.g. COST")
    metric_name: str = Field(..., description="MultiplesTable property name, e.g. MarketCap_Fundamental")


def _get_driver():
    if not config.NEO4J_URI:
        raise HTTPException(status_code=500, detail="NEO4J_URI is not configured")
    try:
        return GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD))
    except Exception as e:
        logger.exception("Failed to create Neo4j driver")
        raise HTTPException(status_code=500, detail=f"Neo4j connection error: {e}")




def create_cache_node_constraint(driver):
    """Create unique constraint for cache nodes (run once during setup)"""
    with driver.session() as session:
        try:
            session.run("""
                CREATE CONSTRAINT stock_cache_ticker IF NOT EXISTS
                FOR (c:SpecilMetricCache) REQUIRE c.ticker IS UNIQUE
            """)
            print("Cache constraint created successfully")
        except Exception as e:
            print(f"Constraint may already exist: {e}")


def store_stock_cache(driver, ticker, price=None, shares_outstanding=None, market_cap=None):
    """Store or update stock cache data in Neo4j"""
    timestamp = datetime.now().isoformat()
    cache_date = datetime.now().date().isoformat()  # Store just the date
    
    query = """
    MERGE (c:SpecilMetricCache {ticker: $ticker})
    SET c.timestamp = $timestamp,
        c.cache_date = $cache_date
    """
    params = {
        'ticker': ticker,
        'timestamp': timestamp,
        'cache_date': cache_date
    }
    
    if price is not None:
        query += ", c.price = $price"
        params['price'] = price
    
    if shares_outstanding is not None:
        query += ", c.shares_outstanding = $shares_outstanding"
        params['shares_outstanding'] = shares_outstanding
    
    if market_cap is not None:
        query += ", c.market_cap = $market_cap"
        params['market_cap'] = market_cap
    
    with driver.session() as session:
        session.run(query, params)
    
    print(f"Cached data for {ticker} at {timestamp}")



def get_SpecilMetricCache_node_data(driver, ticker):
    """
    Retrieve cached stock data if it exists and is from today
    Returns dict with data or None if cache miss/outdated
    If outdated, automatically deletes the cache node
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
        result = session.run(query, ticker=ticker).single()
    
    if not result:
        print(f"Cache MISS for {ticker} - no data found")
        return None
    
    # Check if cache is from today
    # today = datetime.now().date().isoformat()
    # # cache_date = result['cache_date']
    # if cache_date != today:
    #     print(f"Cache OUTDATED for {ticker} - cached on: {cache_date}, today: {today}")
    #     # Delete the outdated cache node
    #     delete_query = """
    #     MATCH (c:SpecilMetricCache {ticker: $ticker})
    #     DELETE c
    #     """ 
    #     with driver.session() as session:
    #         session.run(delete_query, ticker=ticker)
    #     print(f"Deleted outdated cache for {ticker}")
    #     return None
    
    #print(f"Cache HIT for {ticker} - cached today at {result['timestamp']}")
    return {
        'price': result['price'],
        'shares_outstanding': result['shares_outstanding'],
        'market_cap': result['market_cap'],
        'timestamp': result['timestamp']
    }





def list_all_tickers(driver):
    """Collect distinct tickers from existing Company nodes."""
    query = """
    MATCH (m:Company)
    WHERE m.ticker IS NOT NULL
    RETURN DISTINCT m.ticker AS ticker
    ORDER BY ticker
    """
    with driver.session() as session:
        return [r["ticker"] for r in session.run(query)]
    


def fetch_special_metric_cached(driver, ticker):
    """
    Fetch shares outstanding (and computed market cap if possible) - uses cache first.

    IMPORTANT:
      - We do NOT read Alpha Vantage's `MarketCapitalization` field.
      - Market Cap is computed as: Market Cap = Stock Price × Shares Outstanding

    In USE_ONLY_CACHE_NODES mode, do not call external API; return cached values or None.
    """
    # Try cache first
    cached = get_SpecilMetricCache_node_data(driver, ticker)
    if cached and cached.get('shares_outstanding'):
        shares_outstanding = cached.get('shares_outstanding')
        price = cached.get('price')
        market_cap = _calculate_market_cap(price, shares_outstanding)

        # If we can compute it and cache is missing/outdated, write computed value back.
        if market_cap is not None:
            try:
                store_stock_cache(driver, ticker, market_cap=market_cap)
            except Exception:
                # best-effort caching only
                pass

        return {
            'shares_outstanding': shares_outstanding,
            'market_cap': market_cap,
        }

    # In cache-only mode, do not call external APIs
    if USE_ONLY_CACHE_NODES:
        return {'shares_outstanding': None, 'market_cap': None}

    # Cache miss - fetch from API
    print(f"Fetching company overview from API for {ticker}...")
    url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}'
    
    try:
        response = requests.get(url)
        data = response.json()
        
        shares_outstanding = float(data.get('SharesOutstanding', 0)) if data.get('SharesOutstanding') else None
        # DO NOT read MarketCapitalization from Alpha Vantage. Market cap must be computed.
        market_cap = None
        
        # Store in cache
        store_stock_cache(driver, ticker, 
                         shares_outstanding=shares_outstanding, 
                         market_cap=market_cap)
        
        return {
            'shares_outstanding': shares_outstanding,
            'market_cap': market_cap
        }
    except Exception as e:
        print(f"Error fetching company overview for {ticker}: {e}")
        return {'shares_outstanding': None, 'market_cap': None}


def fetch_current_stock_price_cached(driver, ticker):
    """
    Fetch current stock price - uses cache first
    """
    # Try cache first
    cached = get_SpecilMetricCache_node_data(driver, ticker)
    if cached and cached['price']:
        return cached['price']

    # In cache-only mode, do not call external APIs
    if USE_ONLY_CACHE_NODES:
        return None
    
    # Cache miss - fetch from API
    print(f"Fetching stock price from API for {ticker}...")
    #url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}'
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}'
    
    try:
        response = requests.get(url)
        data = response.json()
        
        price = None
        # if 'Global Quote' in data and '05. price' in data['Global Quote']:
        #     price = float(data['Global Quote']['05. price'])
        
        if 'Time Series (Daily)' in data and '4. close' in data['Time Series (Daily)']:
            ts = data["Time Series (Daily)"]
            price = float(ts[max(ts.keys())]["4. close"])

        # Store in cache
        if price:
            # Store price in cache
            store_stock_cache(driver, ticker, price=price)

            # Best-effort: if shares_outstanding is already cached, compute market cap and cache it.
            try:
                cached_now = get_SpecilMetricCache_node_data(driver, ticker)
                shares_outstanding = cached_now.get('shares_outstanding') if cached_now else None
                market_cap = _calculate_market_cap(price, shares_outstanding)
                if market_cap is not None:
                    store_stock_cache(driver, ticker, market_cap=market_cap)
            except Exception:
                pass
        
        return price
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None


def get_last_5yr_avg_ROIC(driver, ticker):
    metric_name = "ReturnOnInvestedCapitalInclGoodwill"
    current_year = datetime.now().year
    years = [current_year - i for i in range(1, 6)]
    year_props = [f"year_{y}" for y in years]
    return_fields = ", ".join([f"m.{p} AS {p}" for p in year_props])
    query = f"""
        MATCH (m:Metric {{ ticker: $ticker, metricName: $metric_name }})
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

    if not values:
        return None
    return sum(values) / len(values)


def get_last_5yr_avg_NetIncome(driver, ticker):
    metric_name = "NetIncome"
    current_year = datetime.now().year
    years = [current_year - i for i in range(1, 6)]
    year_props = [f"year_{y}" for y in years]
    return_fields = ", ".join([f"m.{p} AS {p}" for p in year_props])
    query = f"""
        MATCH (m:Metric {{ ticker: $ticker, metricName: $metric_name }})
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
    if not values:
        return None
    return sum(values) / len(values)



def get_Intrinsic_value(driver, ticker):
    """
    Get intrinsic value (Equity Value) from ValuationSummary metric in Neo4j
    """
    metric_name = "ValuationSummary"
    query = """
        MATCH (m:Metric_ValuationSummary {ticker: $ticker, metricName: $metric_name})
        RETURN coalesce(
            m.EquityIntrinsicValue_PresentValue,
            m.EquityIntrinsicValue_0,
            m.EquityIntrinsicValue,
            m.EquityValue_PresentValue,
            m.EquityValue_0,
            m.EquityValue
        ) AS equity_value
    """
    with driver.session() as session:
        row = session.run(query, ticker=ticker, metric_name=metric_name).single()
    if not row:
        return None
    equity_value = row.get('equity_value')
    # Check if value exists and is valid (not None or NaN)
    if equity_value is not None and not (isinstance(equity_value, float) and math.isnan(equity_value)):
        return float(equity_value)
    return None



def _is_valid_number(val, positive=False):
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
    """Compute Market Cap = Stock Price × Shares Outstanding.

    Returns:
        float market cap if both inputs are valid and > 0, else None.
    """
    if not _is_valid_number(price, positive=True):
        return None
    if not _is_valid_number(shares_outstanding, positive=True):
        return None
    try:
        return float(price) * float(shares_outstanding)
    except Exception:
        return None




def _fetch_yahoo_price_and_shares(ticker: str):
    """Fallback to Yahoo Finance (yfinance) to fetch latest close and shares outstanding.

    Returns:
        dict: {"price": float|None, "shares_outstanding": float|None}
    """
    if yf is None:
        logger.warning("yfinance not available; cannot fallback to Yahoo Finance")
        return {"price": None, "shares_outstanding": None}

    try:
        t = yf.Ticker(ticker)

        shares_outstanding = None
        try:
            info = getattr(t, "info", None) or {}
            so = info.get("sharesOutstanding")
            if _is_valid_number(so, positive=True):
                shares_outstanding = float(so)
        except Exception:
            shares_outstanding = None

        price = None
        try:
            hist = t.history(period="1d")
            if hist is not None and not hist.empty and "Close" in hist.columns:
                close_val = hist["Close"].iloc[-1]
                if _is_valid_number(close_val, positive=True):
                    price = float(close_val)
        except Exception:
            price = None

        return {"price": price, "shares_outstanding": shares_outstanding}
    except Exception as e:
        logger.error(f"Yahoo Finance fallback failed for {ticker}: {e}")
        return {"price": None, "shares_outstanding": None}


# =====================================================================================
# StockPrices_SharesOutstanding_MetricOldCache (NEW)
#   - Seeds ~1Y daily closes and ~2Y shares outstanding history per ticker.
#   - Maintained daily (append + trim) by refresh_special_metric_cache_all.
#   - This cache is then used by the ranking-table logic (no direct yfinance calls there).
# =====================================================================================


def create_stockprices_shares_old_cache_constraint(driver) -> None:
    """Ensure unique constraint for StockPrices_SharesOutstanding_MetricOldCache.ticker"""
    with driver.session() as session:
        session.run(
            """
            CREATE CONSTRAINT stockprices_shares_old_cache_ticker IF NOT EXISTS
            FOR (c:StockPrices_SharesOutstanding_MetricOldCache) REQUIRE c.ticker IS UNIQUE
            """
        )


def upsert_stockprices_shares_old_cache(
    driver,
    ticker: str,
    prices: Optional[List[Dict[str, Any]]] = None,
    shares: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Upsert old market data cache for a ticker.

    Storage format:
      - prices_json: JSON string list[{"date": "YYYY-MM-DD", "close": float}]
      - shares_json: JSON string list[{"date": "YYYY-MM-DD", "shares_outstanding": float}]
    """
    ticker = (ticker or "").upper().strip()
    timestamp = datetime.now().isoformat()
    # Keep this simple + explicit per user request: store the refresh date using `time` module.
    cache_date = time.strftime("%Y-%m-%d", time.localtime())

    query = """
    MERGE (c:StockPrices_SharesOutstanding_MetricOldCache {ticker: $ticker})
    SET c.ticker = $ticker,
        c.timestamp = $timestamp,
        c.cache_date = $cache_date
    """
    params: Dict[str, Any] = {
        "ticker": ticker,
        "timestamp": timestamp,
        "cache_date": cache_date,
    }
    if prices is not None:
        query += ", c.prices_json = $prices_json"
        params["prices_json"] = json.dumps(prices)
    if shares is not None:
        query += ", c.shares_json = $shares_json"
        params["shares_json"] = json.dumps(shares)

    with driver.session() as session:
        session.run(query, params)


def _merge_timeseries_points(
    existing: Optional[List[Dict[str, Any]]],
    incoming: Optional[List[Dict[str, Any]]],
    date_key: str,
    value_key: str,
    keep_since_days_ago: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Merge (append + dedupe) time-series points by date.

    - Keeps the latest value per date.
    - Sorts ascending by date.
    - If keep_since_days_ago is provided, drops items older than (today - that many days).
    """
    existing = existing or []
    incoming = incoming or []

    by_date: Dict[str, float] = {}
    for it in existing + incoming:
        if not isinstance(it, dict):
            continue
        d = it.get(date_key)
        v = it.get(value_key)
        if not d:
            continue
        fv = _safe_float(v)
        if fv is None:
            continue
        by_date[str(d)] = float(fv)

    merged = [{date_key: d, value_key: by_date[d]} for d in sorted(by_date.keys())]

    if keep_since_days_ago is not None and keep_since_days_ago > 0:
        try:
            cutoff = pd.Timestamp.today().tz_localize(None) - pd.Timedelta(days=int(keep_since_days_ago))
            trimmed: List[Dict[str, Any]] = []
            for it in merged:
                dt = pd.to_datetime(it.get(date_key), errors="coerce")
                if dt is pd.NaT:
                    continue
                if getattr(dt, "tzinfo", None) is not None:
                    dt = dt.tz_localize(None)
                if dt >= cutoff:
                    trimmed.append(it)
            merged = trimmed
        except Exception:
            # best-effort only
            pass

    return merged


def append_old_market_cache_daily(
    driver,
    ticker: str,
    close_price: Optional[float],
    shares_outstanding: Optional[float],
    keep_price_days: int = 365,
    keep_shares_days: int = 730,
) -> None:
    """Append today's close/shares into the old cache, trimming by date.

    This lets you seed once with yfinance, then maintain daily using AlphaVantage.
    """
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return

    today = datetime.now().date().isoformat()

    new_prices: List[Dict[str, Any]] = []
    if _is_valid_number(close_price, positive=True):
        new_prices = [{"date": today, "close": float(close_price)}]

    new_shares: List[Dict[str, Any]] = []
    if _is_valid_number(shares_outstanding, positive=True):
        new_shares = [{"date": today, "shares_outstanding": float(shares_outstanding)}]

    if not new_prices and not new_shares:
        return

    existing = get_stockprices_shares_old_cache(driver, ticker)

    merged_prices = None
    if new_prices:
        merged_prices = _merge_timeseries_points(
            existing.get("prices"),
            new_prices,
            date_key="date",
            value_key="close",
            keep_since_days_ago=keep_price_days,
        )

    merged_shares = None
    if new_shares:
        merged_shares = _merge_timeseries_points(
            existing.get("shares"),
            new_shares,
            date_key="date",
            value_key="shares_outstanding",
            keep_since_days_ago=keep_shares_days,
        )

    upsert_stockprices_shares_old_cache(driver, ticker, prices=merged_prices, shares=merged_shares)


def get_stockprices_shares_old_cache(driver, ticker: str) -> Dict[str, Any]:
    """Return parsed old cache data for a ticker.

    Returns:
      {"prices": list|None, "shares": list|None, "cache_date": str|None, "timestamp": str|None}
    """
    ticker = (ticker or "").upper().strip()
    query = """
    MATCH (c:StockPrices_SharesOutstanding_MetricOldCache {ticker: $ticker})
    RETURN c.prices_json AS prices_json,
           c.shares_json AS shares_json,
           c.cache_date AS cache_date,
           c.timestamp AS timestamp
    """
    with driver.session() as session:
        row = session.run(query, ticker=ticker).single()
    if not row:
        return {"prices": None, "shares": None, "cache_date": None, "timestamp": None}

    prices_raw = row.get("prices_json")
    shares_raw = row.get("shares_json")

    def _parse_list(v):
        if not v:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return None

    return {
        "prices": _parse_list(prices_raw),
        "shares": _parse_list(shares_raw),
        "cache_date": row.get("cache_date"),
        "timestamp": row.get("timestamp"),
    }


def _shares_outstanding_ago_from_old_cache_payload(
    shares: Optional[List[Dict[str, Any]]],
    years_ago: int = 1,
) -> Optional[float]:
    """Compute shares outstanding closest at or before (today - years_ago) from an already-fetched cache payload."""
    shares = shares or []
    if not shares:
        return None
    try:
        target = pd.Timestamp.today().tz_localize(None) - pd.DateOffset(years=years_ago)
        rows = []
        for it in shares:
            if not isinstance(it, dict):
                continue
            d = it.get("date")
            so = it.get("shares_outstanding")
            if not d:
                continue
            dt = pd.to_datetime(d).tz_localize(None)
            fso = _safe_float(so)
            if fso is None:
                continue
            rows.append((dt, fso))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])
        candidates = [v for (dt, v) in rows if dt <= target]
        if not candidates:
            return None
        return float(candidates[-1])
    except Exception:
        return None


def _price_history_from_old_cache_payload(
    prices: Optional[List[Dict[str, Any]]],
    years: int = 1,
) -> Optional[List[float]]:
    """Compute daily closes (oldest->latest) for last N years from an already-fetched cache payload."""
    prices = prices or []
    if not prices:
        return None
    try:
        cutoff = pd.Timestamp.today().tz_localize(None) - pd.DateOffset(years=years)
        rows = []
        for it in prices:
            if not isinstance(it, dict):
                continue
            d = it.get("date")
            c = it.get("close")
            if not d:
                continue
            dt = pd.to_datetime(d).tz_localize(None)
            if dt < cutoff:
                continue
            fc = _safe_float(c)
            if fc is None:
                continue
            rows.append((dt, fc))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])
        return [float(v) for _, v in rows]
    except Exception:
        return None


def _get_shares_outstanding_ago_from_old_cache(driver, ticker_symbol: str, years_ago: int = 1) -> Optional[float]:
    """Get shares_outstanding closest at or before (today - years_ago) from old cache."""
    cached = get_stockprices_shares_old_cache(driver, ticker_symbol)
    shares = cached.get("shares") or []
    if not shares:
        return None

    try:
        target = pd.Timestamp.today().tz_localize(None) - pd.DateOffset(years=years_ago)
        # Expect entries like {date: 'YYYY-MM-DD', shares_outstanding: float}
        rows = []
        for it in shares:
            if not isinstance(it, dict):
                continue
            d = it.get("date")
            so = it.get("shares_outstanding")
            if not d:
                continue
            dt = pd.to_datetime(d).tz_localize(None)
            fso = _safe_float(so)
            if fso is None:
                continue
            rows.append((dt, fso))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])
        # pick last <= target
        candidates = [v for (dt, v) in rows if dt <= target]
        if not candidates:
            return None
        return float(candidates[-1])
    except Exception:
        return None


def _get_price_history_from_old_cache(driver, ticker_symbol: str, years: int = 1) -> Optional[List[float]]:
    """Get daily closes (oldest->latest) for last N years from old cache."""
    cached = get_stockprices_shares_old_cache(driver, ticker_symbol)
    prices = cached.get("prices") or []
    if not prices:
        return None

    try:
        cutoff = pd.Timestamp.today().tz_localize(None) - pd.DateOffset(years=years)
        rows = []
        for it in prices:
            if not isinstance(it, dict):
                continue
            d = it.get("date")
            c = it.get("close")
            if not d:
                continue
            dt = pd.to_datetime(d).tz_localize(None)
            if dt < cutoff:
                continue
            fc = _safe_float(c)
            if fc is None:
                continue
            rows.append((dt, fc))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])
        return [float(v) for _, v in rows]
    except Exception:
        return None



def intrinsic_to_mc_calculator(intrinsic_value, market_cap):
    """
    Safely compute Intrinsic Value to Market Cap ratio.
    Returns:
        float ratio if both numbers are valid and market_cap > 0, else None.
    """
    try:
        if not _is_valid_number(intrinsic_value, positive=True):
            return None
        if not _is_valid_number(market_cap, positive=True):
            return None
        return float(intrinsic_value) / float(market_cap)
    except Exception:
        return None



def calculate_metrics_for_tickers(driver, tickers):
    """
    Calculate metrics for all tickers and return ranked results plus rejected tickers with reasons.
    Uses caching to minimize API calls.
    Validation:
      - roic_5y_avg: must be a finite number (can be negative)
      - net_income_5y_avg: must be a finite number (can be negative)
      - shares_outstanding: finite and > 0
      - market_cap: finite and > 0
      - current_price: finite and > 0
      - intrinsic_value: finite and > 0
    Only tickers passing validation are included in ranking.
    """
    accepted = []
    rejected = []
    
    # Clear outdated cache before starting (optional)
    #clear_outdated_cache(driver)
    
    # Step 1: Gather data for all tickers
    for ticker in tickers:
        try:
            #print(f"\n{'='*60}")
            print(f"Processing {ticker}...")
            #print('='*60)
            
            roic_5y_avg = get_last_5yr_avg_ROIC(driver, ticker)             # Get ROIC 5Y Avg from Neo4j
            net_income_5y_avg = get_last_5yr_avg_NetIncome(driver, ticker)  # Get Net Income 5Y Avg from Neo4j
            intrinsic_value = get_Intrinsic_value(driver, ticker)           # Get intrinsic value from Neo4j
            
            company_data = fetch_special_metric_cached(driver, ticker)     # Get company overview (with cache)
            shares_outstanding = company_data['shares_outstanding']
            current_price = fetch_current_stock_price_cached(driver, ticker) # Get current stock price (with cache)

            # Market cap MUST be computed (never taken directly from Alpha Vantage)
            market_cap = _calculate_market_cap(current_price, shares_outstanding)
            

            # Validate required inputs
            errors = {}
            if not _is_valid_number(roic_5y_avg, positive=False):
                errors['roic_5y_avg'] = 'missing or NaN'
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
            
            if errors:
                rejected.append({'ticker': ticker, 'reasons': errors})
                continue
            
            # Calculate derived metrics (safe because validated)
            eps_5y_avg = float(net_income_5y_avg) / float(shares_outstanding)
            earnings_yield = eps_5y_avg / float(current_price)
            intrinsic_to_mc = intrinsic_to_mc_calculator(intrinsic_value, market_cap)
            
            accepted.append({
                'ticker': ticker,
                'roic_5y_avg': float(roic_5y_avg),
                'earnings_yield': float(earnings_yield),
                'intrinsic_to_mc': float(intrinsic_to_mc)
            })
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            rejected.append({'ticker': ticker, 'reasons': {'exception': str(e)}})
    

    #print("accepted: ", accepted)
    #print("rejected: ", rejected)

    # Step 2: Rank each metric for accepted tickers
    def make_ranks(items, key):
        ordered = sorted(enumerate(items), key=lambda x: x[1][key], reverse=True)
        ranks = {}
        for rank, (idx, _) in enumerate(ordered, 1):
            ranks[idx] = rank
        return ranks
    
    roic_ranks = make_ranks(accepted, 'roic_5y_avg') if accepted else {}
    ey_ranks = make_ranks(accepted, 'earnings_yield') if accepted else {}
    imc_ranks = make_ranks(accepted, 'intrinsic_to_mc') if accepted else {}
    
    # Step 3: Calculate overall rank
    final_results = []
    for i, result in enumerate(accepted):
        roic_rank = roic_ranks.get(i)
        ey_rank = ey_ranks.get(i)
        imc_rank = imc_ranks.get(i)
        
        overall_score = roic_rank + ey_rank + imc_rank
        final_results.append({
            'ticker': result['ticker'],
            'roic_5y_avg': result['roic_5y_avg'],
            'roic_rank': roic_rank,
            'earnings_yield': result['earnings_yield'],
            'earnings_yield_rank': ey_rank,
            'intrinsic_to_mc': result['intrinsic_to_mc'],
            'intrinsic_to_mc_rank': imc_rank,
            'overall_score': overall_score
        })
    
    final_results.sort(key=lambda x: x['overall_score'])
    
    for overall_rank, item in enumerate(final_results, 1):
        item['overall_rank'] = overall_rank
    
    print("final_results: ", final_results)
    return final_results, rejected


# =====================================================================================
# V-Invest (Investment Factor) Ranking Table (NEW)
# =====================================================================================

def _safe_float(v: Any) -> Optional[float]:
    """Convert to float; return None for None/NaN/non-numeric."""
    try:
        if v is None:
            return None
        f = float(v)
        if isinstance(f, float) and math.isnan(f):
            return None
        return f
    except Exception:
        return None


def _json_sanitize(obj: Any) -> Any:
    """Recursively convert values to JSON-safe primitives.

    - NaN / +/-Inf -> None (FastAPI/Starlette JSON rejects them)
    - numpy scalars -> python scalars
    - pandas Timestamp -> ISO string
    """
    try:
        # pandas Timestamp
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    except Exception:
        pass

    # numpy scalar
    try:
        if isinstance(obj, np.generic):
            obj = obj.item()
    except Exception:
        pass

    # dict
    if isinstance(obj, dict):
        return {str(k): _json_sanitize(v) for k, v in obj.items()}

    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [_json_sanitize(v) for v in obj]

    # floats (incl. pandas NA converted)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    return obj


def _fetch_metric_nodes_props(driver, ticker: str, metric_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch properties for multiple :Metric nodes in one Neo4j query."""
    if not metric_names:
        return {}
    q = """
    MATCH (m:Metric {ticker: $ticker})
    WHERE m.metricName IN $names
    RETURN m.metricName AS metricName, properties(m) AS props
    """
    out: Dict[str, Dict[str, Any]] = {}
    with driver.session() as session:
        for r in session.run(q, ticker=ticker, names=metric_names):
            name = r.get("metricName")
            props = r.get("props") or {}
            if name:
                out[str(name)] = dict(props)
    return out


def _bulk_fetch_specil_metric_cache(session, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch SpecilMetricCache for all tickers in one query."""
    if not tickers:
        return {}
    q = """
    UNWIND $tickers AS t
    MATCH (c:SpecilMetricCache {ticker: t})
    RETURN c.ticker AS ticker,
           c.price AS price,
           c.shares_outstanding AS shares_outstanding,
           c.market_cap AS market_cap,
           c.timestamp AS timestamp,
           c.cache_date AS cache_date
    """
    out: Dict[str, Dict[str, Any]] = {}
    for r in session.run(q, tickers=[(t or "").upper().strip() for t in tickers]):
        t = (r.get("ticker") or "").upper().strip()
        if not t:
            continue
        out[t] = {
            "price": r.get("price"),
            "shares_outstanding": r.get("shares_outstanding"),
            "market_cap": r.get("market_cap"),
            "timestamp": r.get("timestamp"),
            "cache_date": r.get("cache_date"),
        }
    return out


def _bulk_fetch_old_market_cache(session, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch StockPrices_SharesOutstanding_MetricOldCache for all tickers in one query."""
    if not tickers:
        return {}
    q = """
    UNWIND $tickers AS t
    MATCH (c:StockPrices_SharesOutstanding_MetricOldCache {ticker: t})
    RETURN c.ticker AS ticker,
           c.prices_json AS prices_json,
           c.shares_json AS shares_json,
           c.cache_date AS cache_date,
           c.timestamp AS timestamp
    """
    out: Dict[str, Dict[str, Any]] = {}
    for r in session.run(q, tickers=[(t or "").upper().strip() for t in tickers]):
        t = (r.get("ticker") or "").upper().strip()
        if not t:
            continue
        # Parse lazily here (still once per ticker) to avoid reparsing
        prices_raw = r.get("prices_json")
        shares_raw = r.get("shares_json")
        try:
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) and prices_raw else prices_raw
        except Exception:
            prices = None
        try:
            shares = json.loads(shares_raw) if isinstance(shares_raw, str) and shares_raw else shares_raw
        except Exception:
            shares = None
        out[t] = {
            "prices": prices if isinstance(prices, list) else None,
            "shares": shares if isinstance(shares, list) else None,
            "cache_date": r.get("cache_date"),
            "timestamp": r.get("timestamp"),
        }
    return out


def _bulk_fetch_metric_nodes_props(session, tickers: List[str], metric_names: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Fetch properties for multiple :Metric nodes across many tickers in one query."""
    if not tickers or not metric_names:
        return {}
    q = """
    MATCH (m:Metric)
    WHERE m.ticker IN $tickers AND m.metricName IN $names
    RETURN m.ticker AS ticker, m.metricName AS metricName, properties(m) AS props
    """
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for r in session.run(
        q,
        tickers=[(t or "").upper().strip() for t in tickers],
        names=metric_names,
    ):
        t = (r.get("ticker") or "").upper().strip()
        mn = r.get("metricName")
        if not t or not mn:
            continue
        out.setdefault(t, {})[str(mn)] = dict(r.get("props") or {})
    return out


def _bulk_fetch_valuation_summary_props(session, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch ValuationSummary props for many tickers in one query."""
    if not tickers:
        return {}
    q = """
    MATCH (m:Metric_ValuationSummary {metricName: 'ValuationSummary'})
    WHERE m.ticker IN $tickers
    RETURN m.ticker AS ticker, properties(m) AS props
    """
    out: Dict[str, Dict[str, Any]] = {}
    for r in session.run(q, tickers=[(t or "").upper().strip() for t in tickers]):
        t = (r.get("ticker") or "").upper().strip()
        if not t:
            continue
        out[t] = dict(r.get("props") or {})
    return out


def _build_vinvest_metrics_row_from_payload(
    ticker: str,
    spec_cache: Dict[str, Any],
    old_cache: Dict[str, Any],
    mprops: Dict[str, Dict[str, Any]],
    vs_props: Dict[str, Any],
) -> Dict[str, Any]:
    """Pure function version of `_build_vinvest_metrics_row` (no Neo4j calls)."""
    ticker = (ticker or "").upper().strip()

    shares_outstanding = _safe_float(spec_cache.get("shares_outstanding"))
    current_price = _safe_float(spec_cache.get("price"))
    market_cap = _safe_float(spec_cache.get("market_cap"))
    if market_cap is None:
        market_cap = _calculate_market_cap(current_price, shares_outstanding)

    shares_outstanding_1y_ago = _shares_outstanding_ago_from_old_cache_payload(old_cache.get("shares"), years_ago=1)
    closes = _price_history_from_old_cache_payload(old_cache.get("prices"), years=1)

    last_year, prev_year = _infer_latest_and_prev_year(mprops)

    # --- QUALITY ---
    roic_props = mprops.get("ReturnOnInvestedCapitalInclGoodwill") or {}
    roic = _safe_float(roic_props.get("Last15Y_AVG"))

    rev_props = mprops.get("Revenue") or {}
    revenue_growth_3y = _safe_float(rev_props.get("Last3Y_CAGR"))

    share_dilution = None
    if _is_valid_number(shares_outstanding, positive=True) and _is_valid_number(shares_outstanding_1y_ago, positive=True):
        share_dilution = (float(shares_outstanding) - float(shares_outstanding_1y_ago)) / float(shares_outstanding)

    # --- VALUE ---
    debt_pv = _pick_vs_value(vs_props, "Debt")
    op_lease_pv = _pick_vs_value(vs_props, "OperatingLeaseLiabilities")
    fin_lease_pv = _pick_vs_value(vs_props, "FinanceLeaseLiabilities")
    var_lease_pv = _pick_vs_value(vs_props, "VariableLeaseLiabilities")
    excess_cash_pv = _pick_vs_value(vs_props, "ExcessCash")
    intrinsic_value = _safe_float(vs_props.get("EquityIntrinsicValue_PresentValue"))

    market_enterprise_value = None
    if _is_valid_number(market_cap, positive=True):
        me = float(market_cap)
        for v in [debt_pv, op_lease_pv, fin_lease_pv, var_lease_pv]:
            if _is_valid_number(v, positive=False):
                me += float(v)
        if _is_valid_number(excess_cash_pv, positive=False):
            me -= float(excess_cash_pv)
        market_enterprise_value = me

    def _year_val(name: str, year: int) -> Optional[float]:
        return _pick_metric_year(mprops.get(name) or {}, year)

    ebit = _year_val("EBIT", last_year)

    velite_yield = None
    if _is_valid_number(ebit, positive=False) and _is_valid_number(market_enterprise_value, positive=True):
        velite_yield = float(ebit) / float(market_enterprise_value)

    intrinsic_to_market_cap = intrinsic_to_mc_calculator(intrinsic_value, market_cap)

    # --- SAFETY ---
    assets_last = _year_val("Assets", last_year)
    assets_prev = _year_val("Assets", prev_year)
    liabilities_last = _year_val("Liabilities", last_year)
    revenue_last = _year_val("Revenue", last_year)
    revenue_prev = _year_val("Revenue", prev_year)
    retained_last = _year_val("RetainedEarningsAccumulated", last_year)

    net_wc_last = _year_val("NetOperatingWorkingCapital", last_year)
    assets_cur_last = _year_val("AssetsCurrent", last_year)
    liab_cur_last = _year_val("LiabilitiesCurrent", last_year)
    if net_wc_last is None and assets_cur_last is not None and liab_cur_last is not None:
        net_wc_last = float(assets_cur_last) - float(liab_cur_last)

    altman_z = _compute_altman_z(
        net_operating_working_capital=net_wc_last,
        retained_earnings=retained_last,
        ebit=ebit,
        assets=assets_last,
        liabilities=liabilities_last,
        revenue=revenue_last,
        market_cap=market_cap,
    )

    op_cf_last = _year_val("OperatingCashFlow", last_year)
    net_income_last = _year_val("NetIncome", last_year)
    net_income_prev = _year_val("NetIncome", prev_year)
    long_debt_last = _year_val("LongTermDebt", last_year)
    long_debt_prev = _year_val("LongTermDebt", prev_year)
    assets_cur_prev = _year_val("AssetsCurrent", prev_year)
    liab_cur_prev = _year_val("LiabilitiesCurrent", prev_year)
    gross_profit_last = _year_val("GrossProfit", last_year)
    gross_profit_prev = _year_val("GrossProfit", prev_year)

    piotroski_f = _compute_piotroski_f(
        net_income_last=net_income_last,
        net_income_prev=net_income_prev,
        assets_last=assets_last,
        assets_prev=assets_prev,
        op_cf_last=op_cf_last,
        long_term_debt_last=long_debt_last,
        long_term_debt_prev=long_debt_prev,
        assets_current_last=assets_cur_last,
        assets_current_prev=assets_cur_prev,
        liabilities_current_last=liab_cur_last,
        liabilities_current_prev=liab_cur_prev,
        shares_outstanding_last=shares_outstanding,
        shares_outstanding_prev=shares_outstanding_1y_ago,
        gross_profit_last=gross_profit_last,
        gross_profit_prev=gross_profit_prev,
        revenue_last=revenue_last,
        revenue_prev=revenue_prev,
    )

    debt_last = _year_val("Debt", last_year)
    debt_to_ebitda = None
    if _is_valid_number(debt_last, positive=False) and _is_valid_number(op_cf_last, positive=False) and float(op_cf_last) != 0:
        debt_to_ebitda = float(debt_last) / float(op_cf_last)

    # --- MOMENTUM ---
    roc_6m = None
    above_200 = None
    rsi_14 = None
    if closes:
        mom = _compute_momentum_metrics_from_prices(closes)
        roc_6m = mom.get("ROC_6M")
        above_200 = mom.get("Above_200SMA")
        rsi_14 = mom.get("RSI_14")

    return {
        "Ticker": ticker,
        "ReturnOnInvestedCapital": roic,
        "RevenueGrowth": revenue_growth_3y,
        "ShareDilution": share_dilution,
        "VEliteYield": velite_yield,
        "IntrinsicToMarketCap": intrinsic_to_market_cap,
        "AltmanZScore": altman_z,
        "PiotroskiFScore": piotroski_f,
        "DebtToEBITDA": debt_to_ebitda,
        "ROC_6M": roc_6m,
        "Above_200SMA": above_200,
        "RSI_14": rsi_14,
        "MarketCap": market_cap,
        "SharesOutstanding": shares_outstanding,
        "SharesOutstanding_1Y_Ago": shares_outstanding_1y_ago,
        "MarketEnterpriseValue": market_enterprise_value,
        "EBIT_LastYear": ebit,
        "IntrinsicValue": intrinsic_value,
    }


def _fetch_valuation_summary_props(driver, ticker: str) -> Dict[str, Any]:
    q = """
    MATCH (m:Metric_ValuationSummary {ticker: $ticker, metricName: 'ValuationSummary'})
    RETURN properties(m) AS props
    """
    with driver.session() as session:
        row = session.run(q, ticker=ticker).single()
    return dict(row.get("props") or {}) if row else {}


def _pick_vs_value(vs_props: Dict[str, Any], base: str) -> Optional[float]:
    """Pick ValuationSummary value allowing for schema differences.

    Common shapes seen in this repo:
      - {base}_PresentValue
      - {base}_0 (when CSV has a single unnamed column like '0')
      - {base} (already flattened)
    """
    candidates = [
        f"{base}_PresentValue",
        f"{base}_presentvalue",
        f"{base}_0",
        base,
    ]
    for k in candidates:
        if k in vs_props:
            val = _safe_float(vs_props.get(k))
            if val is not None:
                return val
    return None


def _pick_metric_extra(metric_props: Dict[str, Any], candidates: List[str]) -> Optional[float]:
    for k in candidates:
        if k in metric_props:
            v = _safe_float(metric_props.get(k))
            if v is not None:
                return v
    return None


def _pick_metric_year(metric_props: Dict[str, Any], year: int) -> Optional[float]:
    return _safe_float(metric_props.get(f"year_{year}"))


def _available_years(metric_props: Dict[str, Any]) -> List[int]:
    """Extract available `year_YYYY` integers from a Metric node properties dict."""
    years: List[int] = []
    for k in (metric_props or {}).keys():
        if not isinstance(k, str) or not k.startswith("year_"):
            continue
        try:
            years.append(int(k.split("year_", 1)[1]))
        except Exception:
            continue
    return sorted(set(years))


def _infer_latest_and_prev_year(mprops: Dict[str, Dict[str, Any]]) -> (int, int):
    """Infer the latest available financial statement year for a ticker.

    This replaces the previous `datetime.now().year - 1` assumption.

    Strategy (strict metric names; no renaming fallbacks):
      1) Prefer years from `Assets`, then `Revenue`, then `NetIncome`.
      2) If none found, union years across any provided metric.
      3) If still none found, fall back to (current_year-1, current_year-2).
    """
    preferred = ["Assets", "Revenue", "NetIncome"]
    years: List[int] = []
    for name in preferred:
        ys = _available_years(mprops.get(name) or {})
        if ys:
            years = ys
            break

    if not years:
        all_years: List[int] = []
        for props in (mprops or {}).values():
            all_years.extend(_available_years(props or {}))
        years = sorted(set(all_years))

    if not years:
        cy = datetime.now().year
        return cy - 1, cy - 2

    last_year = years[-1]
    prev_year = years[-2] if len(years) >= 2 else last_year - 1
    return int(last_year), int(prev_year)


def _avg_last_n_years(metric_props: Dict[str, Any], end_year: int, n: int) -> Optional[float]:
    vals: List[float] = []
    for y in range(end_year - n + 1, end_year + 1):
        v = _pick_metric_year(metric_props, y)
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _pct_rank(series: pd.Series) -> pd.Series:
    """Percentile rank with NaNs treated as neutral (0.5)."""
    r = series.rank(pct=True, method="average")
    return r.fillna(0.5)


def _get_shares_outstanding_ago_yf(ticker_symbol: str, years_ago: int = 1) -> Optional[float]:
    """Fetch shares outstanding historical value from yfinance.

    Returns None if yfinance is unavailable or data is missing.
    """
    if yf is None:
        return None
    try:
        ticker = yf.Ticker(ticker_symbol)
        shares_hist = ticker.get_shares_full()
        if shares_hist is None or shares_hist.empty:
            return None
        shares_hist.index = pd.to_datetime(shares_hist.index).tz_localize(None)
        target_date = pd.Timestamp.today() - pd.DateOffset(years=years_ago)
        filtered = shares_hist.loc[shares_hist.index <= target_date]
        if filtered.empty:
            return None
        shares_ago = filtered.iloc[-1]
        if isinstance(shares_ago, pd.Series):
            return _safe_float(shares_ago.values[0])
        return _safe_float(shares_ago.item())
    except Exception:
        return None


def _get_price_history_yf(ticker_symbol: str, period: str = "1y", interval: str = "1d") -> Optional[List[float]]:
    """Fetch historical closes (oldest->latest) via yfinance."""
    if yf is None:
        return None
    try:
        data = yf.download(ticker_symbol, period=period, interval=interval, progress=False)
        if data is None or data.empty or "Close" not in data.columns:
            return None
        closes = data["Close"].dropna().tolist()
        return [float(x) for x in closes]
    except Exception:
        return None


def _compute_momentum_metrics_from_prices(closes: List[float]) -> Dict[str, Optional[float]]:
    """Compute ROC_6M, Above_200SMA, RSI_14 from closes (oldest->latest)."""
    if not closes or len(closes) < 15:
        return {"ROC_6M": None, "Above_200SMA": None, "RSI_14": None}

    latest = float(closes[-1])

    # ROC 6M: ~126 trading days
    roc_6m = None
    if len(closes) >= 127:
        past = float(closes[-127])
        if past and past > 0:
            roc_6m = ((latest - past) / past) * 100.0

    # 200 SMA
    above_200 = None
    if len(closes) >= 200:
        sma_200 = float(np.mean(closes[-200:]))
        above_200 = 1.0 if latest > sma_200 else 0.0

    # RSI 14 (use last 15 closes)
    rsi_14 = None
    window = closes[-15:]
    deltas = np.diff(window)
    gains = deltas[deltas > 0]
    losses = -deltas[deltas < 0]
    avg_gain = float(np.mean(gains)) if len(gains) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 1e-9
    rs = avg_gain / avg_loss
    rsi_14 = 100.0 - (100.0 / (1.0 + rs))

    return {"ROC_6M": roc_6m, "Above_200SMA": above_200, "RSI_14": rsi_14}


def _compute_altman_z(
    net_operating_working_capital: Optional[float],
    retained_earnings: Optional[float],
    ebit: Optional[float],
    assets: Optional[float],
    liabilities: Optional[float],
    revenue: Optional[float],
    market_cap: Optional[float],
) -> Optional[float]:
    if not all(_is_valid_number(v, positive=False) for v in [assets, liabilities, market_cap]):
        return None
    if float(assets) == 0 or float(liabilities) == 0:
        return None
    if any(v is None for v in [net_operating_working_capital, retained_earnings, ebit, revenue]):
        return None
    try:
        X1 = float(net_operating_working_capital) / float(assets)
        X2 = float(retained_earnings) / float(assets)
        X3 = float(ebit) / float(assets)
        X4 = float(market_cap) / float(liabilities)
        X5 = float(revenue) / float(assets)
        return (1.2 * X1 + 1.4 * X2 + 3.3 * X3 + 0.6 * X4 + 0.999 * X5)
    except Exception:
        return None


def _compute_piotroski_f(
    net_income_last: Optional[float],
    net_income_prev: Optional[float],
    assets_last: Optional[float],
    assets_prev: Optional[float],
    op_cf_last: Optional[float],
    long_term_debt_last: Optional[float],
    long_term_debt_prev: Optional[float],
    assets_current_last: Optional[float],
    assets_current_prev: Optional[float],
    liabilities_current_last: Optional[float],
    liabilities_current_prev: Optional[float],
    shares_outstanding_last: Optional[float],
    shares_outstanding_prev: Optional[float],
    gross_profit_last: Optional[float],
    gross_profit_prev: Optional[float],
    revenue_last: Optional[float],
    revenue_prev: Optional[float],
) -> Optional[int]:
    # Must have key denominators
    if assets_last in (None, 0) or assets_prev in (None, 0) or revenue_last in (None, 0) or revenue_prev in (None, 0):
        return None
    if liabilities_current_last in (None, 0) or liabilities_current_prev in (None, 0):
        return None
    if any(v is None for v in [net_income_last, net_income_prev, op_cf_last, long_term_debt_last, long_term_debt_prev, assets_current_last, assets_current_prev, gross_profit_last, gross_profit_prev]):
        return None

    # Shares can come from cache/yfinance; if missing we cannot compute F7
    if shares_outstanding_last is None or shares_outstanding_prev is None:
        return None

    try:
        F1 = 1 if (float(net_income_last) / float(assets_last)) > 0 else 0
        F2 = 1 if float(op_cf_last) > 0 else 0
        F3 = 1 if (float(net_income_last) / float(assets_last)) > (float(net_income_prev) / float(assets_prev)) else 0
        F4 = 1 if float(op_cf_last) > float(net_income_last) else 0
        F5 = 1 if (float(long_term_debt_last) / float(assets_last)) < (float(long_term_debt_prev) / float(assets_prev)) else 0
        F6 = 1 if (float(assets_current_last) / float(liabilities_current_last)) > (float(assets_current_prev) / float(liabilities_current_prev)) else 0
        F7 = 1 if float(shares_outstanding_last) <= float(shares_outstanding_prev) else 0
        F8 = 1 if (float(gross_profit_last) / float(revenue_last)) > (float(gross_profit_prev) / float(revenue_prev)) else 0
        F9 = 1 if (float(revenue_last) / float(assets_last)) > (float(revenue_prev) / float(assets_prev)) else 0
        return int(F1 + F2 + F3 + F4 + F5 + F6 + F7 + F8 + F9)
    except Exception:
        return None


def _build_vinvest_metrics_row(driver, ticker: str, allow_external: bool) -> Dict[str, Any]:
    """Build one dataframe row of all required base + derived metrics."""
    ticker = ticker.upper().strip()

    # Market inputs
    cache = get_SpecilMetricCache_node_data(driver, ticker) or {}
    shares_outstanding = _safe_float(cache.get("shares_outstanding"))
    current_price = _safe_float(cache.get("price"))
    market_cap = _safe_float(cache.get("market_cap"))
    if market_cap is None:
        market_cap = _calculate_market_cap(current_price, shares_outstanding)

    # NOTE (strict mode per user request):
    # Do NOT backfill missing market inputs (price/shares/market_cap) from any external source.

    # Shares outstanding 1y ago (from OLD cache node)
    shares_outstanding_1y_ago = _get_shares_outstanding_ago_from_old_cache(driver, ticker, years_ago=1)

    # Metric nodes (STRICT: only what was explicitly requested in the prompt)
    metric_names = [
        # V-QUALITY
        "ReturnOnInvestedCapitalInclGoodwill",
        "Revenue",
        # V-VALUE
        "EBIT",
        # V-SAFETY
        "NetOperatingWorkingCapital",
        "Assets",
        "RetainedEarningsAccumulated",
        "Liabilities",
        "NetIncome",
        "OperatingCashFlow",
        "LongTermDebt",
        "AssetsCurrent",
        "LiabilitiesCurrent",
        "GrossProfit",
        "Debt",
    ]

    mprops = _fetch_metric_nodes_props(driver, ticker, metric_names)
    last_year, prev_year = _infer_latest_and_prev_year(mprops)

    # --- QUALITY ---
    roic_props = mprops.get("ReturnOnInvestedCapitalInclGoodwill") or {}
    roic = _safe_float(roic_props.get("Last15Y_AVG"))

    rev_props = mprops.get("Revenue") or {}
    revenue_growth_3y = _safe_float(rev_props.get("Last3Y_CAGR"))

    share_dilution = None
    if _is_valid_number(shares_outstanding, positive=True) and _is_valid_number(shares_outstanding_1y_ago, positive=True):
        share_dilution = (float(shares_outstanding) - float(shares_outstanding_1y_ago)) / float(shares_outstanding)

    # --- VALUE ---
    vs_props = _fetch_valuation_summary_props(driver, ticker)
    debt_pv = _pick_vs_value(vs_props, "Debt")
    op_lease_pv = _pick_vs_value(vs_props, "OperatingLeaseLiabilities")
    fin_lease_pv = _pick_vs_value(vs_props, "FinanceLeaseLiabilities")
    var_lease_pv = _pick_vs_value(vs_props, "VariableLeaseLiabilities")
    excess_cash_pv = _pick_vs_value(vs_props, "ExcessCash")
    intrinsic_value = _safe_float(vs_props.get("EquityIntrinsicValue_PresentValue"))

    market_enterprise_value = None
    if _is_valid_number(market_cap, positive=True):
        me = float(market_cap)
        for v in [debt_pv, op_lease_pv, fin_lease_pv, var_lease_pv]:
            if _is_valid_number(v, positive=False):
                me += float(v)
        if _is_valid_number(excess_cash_pv, positive=False):
            me -= float(excess_cash_pv)
        market_enterprise_value = me

    ebit = _pick_metric_year(mprops.get("EBIT") or {}, last_year)
    velite_yield = None
    if _is_valid_number(ebit, positive=False) and _is_valid_number(market_enterprise_value, positive=True):
        velite_yield = float(ebit) / float(market_enterprise_value)

    intrinsic_to_market_cap = intrinsic_to_mc_calculator(intrinsic_value, market_cap)

    # --- SAFETY ---
    def _year_val(name: str, year: int) -> Optional[float]:
        return _pick_metric_year(mprops.get(name) or {}, year)

    assets_last = _year_val("Assets", last_year)
    assets_prev = _year_val("Assets", prev_year)
    liabilities_last = _year_val("Liabilities", last_year)
    revenue_last = _year_val("Revenue", last_year)
    revenue_prev = _year_val("Revenue", prev_year)
    retained_last = _year_val("RetainedEarningsAccumulated", last_year)

    net_wc_last = _year_val("NetOperatingWorkingCapital", last_year)
    assets_cur_last = _year_val("AssetsCurrent", last_year)
    liab_cur_last = _year_val("LiabilitiesCurrent", last_year)
    if net_wc_last is None and assets_cur_last is not None and liab_cur_last is not None:
        net_wc_last = float(assets_cur_last) - float(liab_cur_last)

    altman_z = _compute_altman_z(
        net_operating_working_capital=net_wc_last,
        retained_earnings=retained_last,
        ebit=ebit,
        assets=assets_last,
        liabilities=liabilities_last,
        revenue=revenue_last,
        market_cap=market_cap,
    )

    op_cf_last = _year_val("OperatingCashFlow", last_year)
    net_income_last = _year_val("NetIncome", last_year)
    net_income_prev = _year_val("NetIncome", prev_year)

    long_debt_last = _year_val("LongTermDebt", last_year)
    long_debt_prev = _year_val("LongTermDebt", prev_year)

    assets_cur_prev = _year_val("AssetsCurrent", prev_year)
    liab_cur_prev = _year_val("LiabilitiesCurrent", prev_year)

    gross_profit_last = _year_val("GrossProfit", last_year)
    gross_profit_prev = _year_val("GrossProfit", prev_year)

    piotroski_f = _compute_piotroski_f(
        net_income_last=net_income_last,
        net_income_prev=net_income_prev,
        assets_last=assets_last,
        assets_prev=assets_prev,
        op_cf_last=op_cf_last,
        long_term_debt_last=long_debt_last,
        long_term_debt_prev=long_debt_prev,
        assets_current_last=assets_cur_last,
        assets_current_prev=assets_cur_prev,
        liabilities_current_last=liab_cur_last,
        liabilities_current_prev=liab_cur_prev,
        shares_outstanding_last=shares_outstanding,
        shares_outstanding_prev=shares_outstanding_1y_ago,
        gross_profit_last=gross_profit_last,
        gross_profit_prev=gross_profit_prev,
        revenue_last=revenue_last,
        revenue_prev=revenue_prev,
    )

    debt_last = _year_val("Debt", last_year)
    debt_to_ebitda = None
    if _is_valid_number(debt_last, positive=False) and _is_valid_number(op_cf_last, positive=False) and float(op_cf_last) != 0:
        debt_to_ebitda = float(debt_last) / float(op_cf_last)

    # --- MOMENTUM ---
    roc_6m = None
    above_200 = None
    rsi_14 = None
    closes = _get_price_history_from_old_cache(driver, ticker, years=1)
    if closes:
        mom = _compute_momentum_metrics_from_prices(closes)
        roc_6m = mom.get("ROC_6M")
        above_200 = mom.get("Above_200SMA")
        rsi_14 = mom.get("RSI_14")

    return {
        "Ticker": ticker,
        "ReturnOnInvestedCapital": roic,
        "RevenueGrowth": revenue_growth_3y,
        "ShareDilution": share_dilution,
        "VEliteYield": velite_yield,
        "IntrinsicToMarketCap": intrinsic_to_market_cap,
        "AltmanZScore": altman_z,
        "PiotroskiFScore": piotroski_f,
        "DebtToEBITDA": debt_to_ebitda,
        "ROC_6M": roc_6m,
        "Above_200SMA": above_200,
        "RSI_14": rsi_14,
        "MarketCap": market_cap,
        "SharesOutstanding": shares_outstanding,
        "SharesOutstanding_1Y_Ago": shares_outstanding_1y_ago,
        "MarketEnterpriseValue": market_enterprise_value,
        "EBIT_LastYear": ebit,
        "IntrinsicValue": intrinsic_value,
    }


def calculate_vinvest_ranking_table(driver, tickers: List[str], allow_external: bool) -> Dict[str, Any]:
    """Compute the full V-Invest ranking table for the given tickers.

    Returns:
      {
        "table": List[dict],          # final ranking table
        "metrics": List[dict],        # raw metrics rows used to build the table
        "rejected": List[dict]
      }
    """

    rows: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    # Bulk fetch everything we need in a few queries to avoid per-ticker round trips.
    tickers_norm = [(t or "").upper().strip() for t in (tickers or []) if (t or "").strip()]
    if not tickers_norm:
        return {"table": [], "metrics": [], "rejected": []}

    metric_names = [
        "ReturnOnInvestedCapitalInclGoodwill",
        "Revenue",
        "EBIT",
        "NetOperatingWorkingCapital",
        "Assets",
        "RetainedEarningsAccumulated",
        "Liabilities",
        "NetIncome",
        "OperatingCashFlow",
        "LongTermDebt",
        "AssetsCurrent",
        "LiabilitiesCurrent",
        "GrossProfit",
        "Debt",
    ]

    with driver.session() as session:
        spec_cache_by_ticker = _bulk_fetch_specil_metric_cache(session, tickers_norm)            # SpecilMetricCache data
        old_cache_by_ticker = _bulk_fetch_old_market_cache(session, tickers_norm)                # StockPrices_SharesOutstanding_MetricOldCache data
        metric_props_by_ticker = _bulk_fetch_metric_nodes_props(session, tickers_norm, metric_names)   # Metric data
        vs_by_ticker = _bulk_fetch_valuation_summary_props(session, tickers_norm)                      #  Metric_ValuationSummary data     

    for t in tickers_norm:
        try:
            row = _build_vinvest_metrics_row_from_payload(
                ticker=t,
                spec_cache=spec_cache_by_ticker.get(t, {}) or {},
                old_cache=old_cache_by_ticker.get(t, {}) or {},
                mprops=metric_props_by_ticker.get(t, {}) or {},
                vs_props=vs_by_ticker.get(t, {}) or {},
            )
            rows.append(row)
        except Exception as e:
            rejected.append({"ticker": t, "reasons": {"exception": str(e)}})

    if not rows:
        return {"table": [], "metrics": [], "rejected": rejected}

    df = pd.DataFrame(rows)

    # DEBUG: export the raw metrics rows (direct output of `_build_vinvest_metrics_row`)
    # so you can inspect all intermediate values easily.
    # NOTE: Use an absolute path to avoid CWD-dependent behavior.
    try:
        charts_dir = _temp_charts_dir()
        charts_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(charts_dir / "vinvest_metrics_rows.csv", index=False, na_rep="NaN")
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to write vinvest_metrics_rows.csv: {e}")

    # --- STEP 1: CALCULATE UNIVERSAL SUB-RATINGS (0-100) ---
    df["V_Quality"] = (
        _pct_rank(df["ReturnOnInvestedCapital"]) * 0.4
        + _pct_rank(df["RevenueGrowth"]) * 0.4
        + (1.0 - _pct_rank(df["ShareDilution"])) * 0.2
    ) * 100.0

    df["V_Value"] = (
        _pct_rank(df["VEliteYield"]) * 0.5
        + _pct_rank(df["IntrinsicToMarketCap"]) * 0.5
    ) * 100.0

    df["V_Safety"] = (
        _pct_rank(df["AltmanZScore"]) * 0.4
        + (df["PiotroskiFScore"].fillna(0) / 9.0) * 0.4
        + (1.0 - _pct_rank(df["DebtToEBITDA"])) * 0.2
    ) * 100.0

    rsi_sig = df["RSI_14"].apply(lambda x: 1.0 if (x is not None and 30 < float(x) < 65) else 0.5)
    df["V_Momentum"] = (
        _pct_rank(df["ROC_6M"]) * 0.4
        + df["Above_200SMA"].fillna(0.5) * 0.4
        + rsi_sig * 0.2
    ) * 100.0

    # --- STEP 2: CALCULATE AGGREGATE V-RATING ---
    df["V_Rating"] = (
        df["V_Quality"] * 0.30
        + df["V_Value"] * 0.30
        + df["V_Safety"] * 0.25
        + df["V_Momentum"] * 0.15
    ).round(2)

    # --- STEP 3: THE GATEKEEPER WATERFALL ---
    # If a gatekeeper metric is missing, reject for missing data.
    missing_gatekeeper = (
        df["AltmanZScore"].isna()
        | df["DebtToEBITDA"].isna()
        | df["ReturnOnInvestedCapital"].isna()
    )
    is_distressed = df["AltmanZScore"].fillna(-np.inf) <= 1.1
    is_overleveraged = df["DebtToEBITDA"].fillna(np.inf) >= 6.0
    is_unprofitable = df["ReturnOnInvestedCapital"].fillna(-np.inf) <= 0

    conditions = [missing_gatekeeper, is_distressed, is_overleveraged, is_unprofitable]
    rejection_labels = [
        "REJECT: Missing Gatekeeper Data",
        "REJECT: Distress Zone",
        "REJECT: Over-Leveraged",
        "REJECT: Zero/Neg ROIC",
    ]
    df["Status"] = np.select(conditions, rejection_labels, default="Qualified")

    # --- STEP 4: NESTED TIERING FOR QUALIFIED TICKERS ---
    qualified_mask = df["Status"] == "Qualified"
    df["Rank"] = np.nan
    if qualified_mask.any():
        sorted_survivors = (
            df.loc[qualified_mask]
            .sort_values(by=["V_Rating", "IntrinsicToMarketCap"], ascending=[False, False])
            .reset_index(drop=True)
        )
        sorted_survivors["Rank"] = sorted_survivors.index + 1
        df.loc[qualified_mask, "Rank"] = sorted_survivors["Rank"].values

    def assign_tier(r):
        if pd.isna(r):
            return None
        r = int(r)
        if r <= 10:
            return "V-Elite 10"
        if r <= 50:
            return "V-Elite 50"
        if r <= 100:
            return "V-Elite 100"
        if r <= 500:
            return "V-Elite 500"
        return "V-Qualified"

    tier_labels = df["Rank"].apply(assign_tier)
    df["Status"] = np.where(df["Status"] == "Qualified", tier_labels, df["Status"])

    # --- STEP 5: FINAL CLEANUP & OUTPUT ---
    cols = [
        "Ticker",
        "V_Rating",
        "Status",
        "Rank",
        "V_Quality",
        "V_Value",
        "V_Safety",
        "V_Momentum",
    ]
    out_df = df[cols].sort_values(by=["Rank", "V_Rating"], ascending=[True, False], na_position="last")

    # DEBUG: export the final ranking table (what the API returns in `table`)
    # NOTE: Use an absolute path to avoid CWD-dependent behavior.
    try:
        charts_dir = _temp_charts_dir()
        charts_dir.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(charts_dir / "vinvest_ranking_table.csv", index=False, na_rep="NaN")
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to write vinvest_ranking_table.csv: {e}")

    table_records = out_df.to_dict(orient="records")

    # IMPORTANT: Starlette's JSONResponse rejects NaN/Inf.
    return _json_sanitize(
        {
            "table": table_records,
            # NOTE: store raw metrics rows too (these are the columns you see in
            # vinvest_metrics_rows.csv). This enables caching + tool access.
            "metrics": rows,
            "rejected": rejected,
        }
    )


def format_output(results):
    """Format results for display"""
    output = []
    for r in results:
        output.append({
            'Overall Rank': r['overall_rank'],
            'Ticker': r['ticker'],
            'ROIC 5Y Avg': f"{r['roic_5y_avg']:.4f} ({r['roic_rank']})" if r['roic_5y_avg'] is not None else "N/A",
            'Earnings Yield': f"{r['earnings_yield']:.4f} ({r['earnings_yield_rank']})" if r['earnings_yield'] is not None else "N/A",
            'Intrinsic to Market Cap': f"{r['intrinsic_to_mc']:.4f} ({r['intrinsic_to_mc_rank']})" if r['intrinsic_to_mc'] is not None else "N/A"
        })
    return output


def create_specil_metric_cache_constraint(driver):
    """Ensure unique constraint for SpecilMetricCache.ticker"""
    with driver.session() as session:
        session.run(
            """
            CREATE CONSTRAINT specil_metric_cache_ticker IF NOT EXISTS
            FOR (c:SpecilMetricCache) REQUIRE c.ticker IS UNIQUE
            """
        )


def upsert_specil_metric_cache(driver, ticker, price=None, shares_outstanding=None, market_cap=None):
    """Create or update SpecilMetricCache node for a ticker with latest values."""
    timestamp = datetime.now().isoformat()
    cache_date = datetime.now().date().isoformat()

    query = """
    MERGE (c:SpecilMetricCache {ticker: $ticker})
    SET c.ticker = $ticker,
        c.timestamp = $timestamp,
        c.cache_date = $cache_date
    """
    params = {
        "ticker": ticker,
        "timestamp": timestamp,
        "cache_date": cache_date,
    }

    if price is not None:
        query += ", c.price = $price"
        params["price"] = price
    if shares_outstanding is not None:
        query += ", c.shares_outstanding = $shares_outstanding"
        params["shares_outstanding"] = shares_outstanding
    if market_cap is not None:
        query += ", c.market_cap = $market_cap"
        params["market_cap"] = market_cap

    with driver.session() as session:
        session.run(query, params)


def calculate_metrics_for_tickers_cache_only(driver, tickers):
    """
    Calculate metrics using ONLY values present in SpecilMetricCache nodes for market data (price, shares_outstanding).
    Market cap is ALWAYS computed as: price × shares_outstanding.
    Metric nodes (ROIC, NetIncome, ValuationSummary) are still read from Neo4j as before.
    No external API calls are made in this function.
    """
    accepted = []
    rejected = []

    for ticker in tickers:
        try:
            roic_5y_avg = get_last_5yr_avg_ROIC(driver, ticker)
            net_income_5y_avg = get_last_5yr_avg_NetIncome(driver, ticker)
            intrinsic_value = get_Intrinsic_value(driver, ticker)

            cached = get_SpecilMetricCache_node_data(driver, ticker)
            shares_outstanding = cached.get('shares_outstanding') if cached else None
            current_price = cached.get('price') if cached else None

            # Market cap MUST be computed (never taken directly from Alpha Vantage)
            market_cap = _calculate_market_cap(current_price, shares_outstanding)

            errors = {}
            if not _is_valid_number(roic_5y_avg, positive=False):
                errors['roic_5y_avg'] = 'missing or NaN'
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

            if errors:
                rejected.append({'ticker': ticker, 'reasons': errors})
                continue

            eps_5y_avg = float(net_income_5y_avg) / float(shares_outstanding)
            earnings_yield = eps_5y_avg / float(current_price)
            intrinsic_to_mc = intrinsic_to_mc_calculator(intrinsic_value, market_cap)

            accepted.append({
                'ticker': ticker,
                'roic_5y_avg': float(roic_5y_avg),
                'earnings_yield': float(earnings_yield),
                'intrinsic_to_mc': float(intrinsic_to_mc)
            })
        except Exception as e:
            rejected.append({'ticker': ticker, 'reasons': {'exception': str(e)}})

    # Ranking logic identical to calculate_metrics_for_tickers
    def make_ranks(items, key):
        ordered = sorted(enumerate(items), key=lambda x: x[1][key], reverse=True)
        ranks = {}
        for rank, (idx, _) in enumerate(ordered, 1):
            ranks[idx] = rank
        return ranks

    roic_ranks = make_ranks(accepted, 'roic_5y_avg') if accepted else {}
    ey_ranks = make_ranks(accepted, 'earnings_yield') if accepted else {}
    imc_ranks = make_ranks(accepted, 'intrinsic_to_mc') if accepted else {}

    final_results = []
    for i, result in enumerate(accepted):
        roic_rank = roic_ranks.get(i)
        ey_rank = ey_ranks.get(i)
        imc_rank = imc_ranks.get(i)
        overall_score = roic_rank + ey_rank + imc_rank
        final_results.append({
            'ticker': result['ticker'],
            'roic_5y_avg': result['roic_5y_avg'],
            'roic_rank': roic_rank,
            'earnings_yield': result['earnings_yield'],
            'earnings_yield_rank': ey_rank,
            'intrinsic_to_mc': result['intrinsic_to_mc'],
            'intrinsic_to_mc_rank': imc_ranks.get(i),
            'overall_score': overall_score
        })

    final_results.sort(key=lambda x: x['overall_score'])
    for overall_rank, item in enumerate(final_results, 1):
        item['overall_rank'] = overall_rank

    return final_results, rejected


def fetch_company_overview_api(ticker: str):
    """Fetch company overview values directly from Alpha Vantage API."""
    url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}'
    try:
        response = requests.get(url)
        data = response.json()
        shares_outstanding = float(data.get('SharesOutstanding', 0)) if data.get('SharesOutstanding') else None
        # DO NOT read MarketCapitalization from Alpha Vantage. Market cap must be computed.
        return {"shares_outstanding": shares_outstanding, "market_cap": None}
    except Exception as e:
        logger.error(f"Error fetching company overview via API for {ticker}: {e}")
        return {"shares_outstanding": None, "market_cap": None}


def fetch_price_api(ticker: str):
    """Fetch latest close price directly from Alpha Vantage API."""
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}'
    try:
        response = requests.get(url)
        data = response.json()
        if 'Time Series (Daily)' in data:
            ts = data['Time Series (Daily)']
            latest = max(ts.keys())
            return float(ts[latest].get('4. close')) if ts[latest].get('4. close') else None
        return None
    except Exception as e:
        logger.error(f"Error fetching price via API for {ticker}: {e}")
        return None




def create_special_metric_ranking_cache_constraint(driver):
    """Ensure one SpecialMetricRankingCache node per cache_date (unique by cache_date)."""
    with driver.session() as session:
        session.run(
            """
            CREATE CONSTRAINT special_metric_ranking_cache_cache_date IF NOT EXISTS
            FOR (c:SpecialMetricRankingCache) REQUIRE c.cache_date IS UNIQUE
            """
        )


def upsert_special_metric_ranking_cache(driver, ranking_list):
    """Create or update a SpecialMetricRankingCache node for the current cache_date (one per date).

    Properties stored on the node:
      - Ranking: JSON structure keyed by ticker that contains BOTH:
          {"TICKER": {"ranking": {...}, "metrics": {...}}, ...}

    Backwards compatibility:
      - Older cache nodes may have Ranking stored as a list[dict] (ranking rows only).
      - We keep read endpoints tolerant to both shapes.
    """
    timestamp = datetime.now().isoformat()
    cache_date = datetime.now().date().isoformat()

    # Accept either:
    #   - list[dict] (ranking rows)
    #   - dict payload: {"table": [...], "metrics": [...]} OR {"Ranking": [...], "Metrics": [...]}
    #   - already combined dict keyed by ticker (advanced)
    table_rows = None
    metrics_rows = None
    combined_by_ticker = None

    if isinstance(ranking_list, list):
        # only ranking rows were provided
        table_rows = ranking_list
    elif isinstance(ranking_list, dict):
        # payload dict
        if "table" in ranking_list or "metrics" in ranking_list:
            table_rows = ranking_list.get("table") or []
            metrics_rows = ranking_list.get("metrics") or []
        elif "Ranking" in ranking_list or "Metrics" in ranking_list:
            table_rows = ranking_list.get("Ranking") or []
            metrics_rows = ranking_list.get("Metrics") or []
        else:
            # assume already a combined-by-ticker map
            combined_by_ticker = ranking_list

    def _ticker_key(row: Any) -> Optional[str]:
        if not isinstance(row, dict):
            return None
        t = row.get("Ticker") or row.get("ticker")
        if not t:
            return None
        return str(t).upper().strip()

    # If we have table_rows/metrics_rows, merge them into dict keyed by ticker
    if combined_by_ticker is None:
        combined_by_ticker = {}
        # Index metrics by ticker
        metrics_by_ticker: Dict[str, Dict[str, Any]] = {}
        if isinstance(metrics_rows, list):
            for r in metrics_rows:
                tk = _ticker_key(r)
                if tk:
                    metrics_by_ticker[tk] = r

        if isinstance(table_rows, list):
            for r in table_rows:
                tk = _ticker_key(r)
                if not tk:
                    continue
                combined_by_ticker[tk] = {
                    "ranking": r,
                    "metrics": metrics_by_ticker.get(tk) or {},
                }

        # If metrics had tickers not present in table_rows, still store them.
        for tk, mr in metrics_by_ticker.items():
            combined_by_ticker.setdefault(tk, {"ranking": {}, "metrics": mr})

    ranking_json = json.dumps(combined_by_ticker)

    with driver.session() as session:
        session.run(
            """
            MERGE (c:SpecialMetricRankingCache {cache_date: $cache_date})
            SET c.Ranking = $ranking,
                c.timestamp = $timestamp
            """,
            ranking=ranking_json,
            cache_date=cache_date,
            timestamp=timestamp,
        )


def compute_and_cache_special_metric_rankings(driver):
    """Compute + cache the daily ranking table for ALL tickers.

    - Uses ONLY SpecilMetricCache nodes for market inputs (price, shares_outstanding)
      and computes market cap as (price × shares_outstanding)
    - Writes the table into a SpecialMetricRankingCache node keyed by today's cache_date

    This is intentionally **not** exposed as a separate API endpoint; it is called from
    `refresh_special_metric_cache_all()`.

    Returns: { cache_date: str, count: int, Ranking: list, rejected: list }
    """
    # Ensure per-date uniqueness constraint exists
    try:
        create_special_metric_ranking_cache_constraint(driver)
    except Exception:
        pass

    tickers = list_all_tickers(driver)
    if not tickers:
        raise HTTPException(status_code=404, detail="No tickers found in database")

    # New V-Invest ranking table logic
    payload = calculate_vinvest_ranking_table(driver, tickers, allow_external=(not USE_ONLY_CACHE_NODES))

    # Upsert cache node with BOTH ranking table + raw metrics (combined under `Ranking`)
    upsert_special_metric_ranking_cache(
        driver,
        {
            "table": payload.get("table") or [],
            "metrics": payload.get("metrics") or [],
        },
    )

    return {
        "cache_date": datetime.now().date().isoformat(),
        "count": len(payload.get("table") or []),
        "Ranking": payload.get("table") or [],
        "Metrics": payload.get("metrics") or [],
        "rejected": payload.get("rejected") or [],
    }





########################################################
######################## APIS ##########################
########################################################



# curl -X POST "http://localhost:8080/api/special_metrics/refresh_special_metric_cache_all?summary=false" -H "Content-Type: application/json"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/refresh_special_metric_cache_all?summary=false" -H "Content-Type: application/json"
@router.post("/api/special_metrics/refresh_special_metric_cache_all")
def refresh_special_metric_cache_all(
    summary: bool = Query(False),
    source: str = Query(
        SPECIAL_METRIC_CACHE_PRIMARY_SOURCE,
        description="Primary data source for market inputs (price, shares). One of: alphavantage|yahoo",
    ),
    alphavantage_max_workers: int = Query(
        SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS,
        ge=1,
        le=50,
        description="When source=alphavantage, number of parallel workers used for AlphaVantage calls.",
    ),
    yahoo_max_workers: int = Query(
        SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS,
        ge=1,
        le=50,
        description="When source=yahoo, number of parallel workers used for Yahoo Finance calls.",
    ),
):
    """
    Create or update SpecilMetricCache nodes for all companies.
    - If node does not exist, it will be created with ticker and latest values.
    - If node exists, all properties (cache_date, price, shares_outstanding, ticker, timestamp)
      will be refreshed from the API, and `market_cap` will be computed as (price × shares_outstanding).

    NOTE: This endpoint calls Alpha Vantage APIs per ticker and may be rate limited.
    Consider running during off-hours or adding batching if you have many tickers.
    """
    # if USE_ONLY_CACHE_NODES:
    #     raise HTTPException(status_code=403, detail="Cache-only mode enabled; cannot call Alpha Vantage APIs")
    driver = _get_driver()
    try:
        # Ensure unique constraint exists
        try:
            create_specil_metric_cache_constraint(driver)
        except Exception:
            pass

        tickers = list_all_tickers(driver)
        if not tickers:
            raise HTTPException(status_code=404, detail="No tickers found in database to refresh cache")

        # Minimal progress logging (requested): only 2 lines per ticker (start/end)
        _progress_log(f"Starting refresh for {len(tickers)} tickers", stage="start")

        updated: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        source_norm = (source or "alphavantage").strip().lower()
        if source_norm not in ("alphavantage", "yahoo"):
            raise HTTPException(status_code=422, detail="source must be one of: alphavantage|yahoo")

        today = datetime.now().date().isoformat()

        # Bulk fetch existing cache dates (single Neo4j round-trip)
        tickers_norm = [(t or "").upper().strip() for t in (tickers or []) if (t or "").strip()]
        cache_date_by_ticker: Dict[str, Optional[str]] = {}
        try:
            with driver.session() as session:
                for r in session.run(
                    """
                    UNWIND $tickers AS t
                    OPTIONAL MATCH (c:SpecilMetricCache {ticker: t})
                    RETURN t AS ticker, c.cache_date AS cache_date
                    """,
                    tickers=tickers_norm,
                ):
                    tk = (r.get("ticker") or "").upper().strip()
                    if tk:
                        cache_date_by_ticker[tk] = r.get("cache_date")
        except Exception:
            cache_date_by_ticker = {}

        def _fetch_market_alphavantage(tk: str) -> Dict[str, Any]:
            """Fetch price+shares from AlphaVantage. Returns {price, shares_outstanding}."""
            tk = (tk or "").upper().strip()
            overview = fetch_company_overview_api(tk) or {}
            price = fetch_price_api(tk)
            shares = overview.get("shares_outstanding")
            return {"price": price, "shares_outstanding": shares}

        def _fetch_market_yahoo(tk: str) -> Dict[str, Any]:
            """Fetch price+shares from Yahoo Finance (yfinance)."""
            tk = (tk or "").upper().strip()
            return _fetch_yahoo_price_and_shares(tk) or {"price": None, "shares_outstanding": None}

        def _choose_with_cross_fallback(tk: str) -> Dict[str, Any]:
            """Use selected primary source; if missing/invalid, fallback to the other source."""
            tk = (tk or "").upper().strip()

            def _valid_payload(p: Dict[str, Any]) -> bool:
                return _is_valid_number(p.get("price"), positive=True) and _is_valid_number(p.get("shares_outstanding"), positive=True)

            primary = _fetch_market_alphavantage if source_norm == "alphavantage" else _fetch_market_yahoo
            secondary = _fetch_market_yahoo if source_norm == "alphavantage" else _fetch_market_alphavantage

            p1 = {}
            try:
                p1 = primary(tk)
            except Exception:
                p1 = {}
            if _valid_payload(p1):
                return p1

            p2 = {}
            try:
                p2 = secondary(tk)
            except Exception:
                p2 = {}

            # Merge: fill missing fields from fallback
            out = {"price": p1.get("price"), "shares_outstanding": p1.get("shares_outstanding")}
            if not _is_valid_number(out.get("price"), positive=True) and _is_valid_number(p2.get("price"), positive=True):
                out["price"] = p2.get("price")
            if not _is_valid_number(out.get("shares_outstanding"), positive=True) and _is_valid_number(p2.get("shares_outstanding"), positive=True):
                out["shares_outstanding"] = p2.get("shares_outstanding")
            return out

        # Decide tickers to process (emit 2-line start/skip here)
        to_process: List[str] = []
        idx_by_ticker = {t: i for i, t in enumerate(tickers_norm, 1)}
        for t in tickers_norm:
            i = idx_by_ticker.get(t) or 0
            _progress_log(f"Ticker {i}/{len(tickers_norm)} START", ticker=t)

            cd = cache_date_by_ticker.get(t)
            if cd == today:
                _progress_log(f"Ticker {i}/{len(tickers_norm)} END (skipped: up-to-date)", ticker=t)
                continue
            to_process.append(t)

        def _write_cache_for_ticker(tk: str, price: Any, shares: Any) -> Dict[str, Any]:
            """Compute market cap, update old cache daily, upsert SpecilMetricCache."""
            tk = (tk or "").upper().strip()
            market_cap = _calculate_market_cap(price, shares)

            # Best-effort daily append for old cache
            try:
                append_old_market_cache_daily(
                    driver,
                    ticker=tk,
                    close_price=price,
                    shares_outstanding=shares,
                    keep_price_days=365,
                    keep_shares_days=730,
                )
            except Exception:
                logger.exception(f"Failed to append old market cache for {tk}")

            upsert_specil_metric_cache(
                driver,
                tk,
                price=price,
                shares_outstanding=shares,
                market_cap=market_cap,
            )
            return {"ticker": tk, "price": price, "shares_outstanding": shares, "market_cap": market_cap}

        # Fetch + write
        if source_norm == "yahoo":
            # Parallelize Yahoo fetches (network I/O heavy)
            max_workers = min(int(yahoo_max_workers), max(1, len(to_process)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_choose_with_cross_fallback, t): t for t in to_process}
                for fut in as_completed(future_map):
                    t = future_map[fut]
                    i = idx_by_ticker.get(t) or 0
                    try:
                        payload = fut.result() or {}
                        price = payload.get("price")
                        shares = payload.get("shares_outstanding")
                        row = _write_cache_for_ticker(t, price, shares)
                        updated.append(row)
                        _progress_log(f"Ticker {i}/{len(tickers_norm)} END", ticker=t)
                    except Exception as e:
                        logger.exception(f"Failed to refresh SpecilMetricCache for {t}")
                        _progress_log(f"Ticker refresh FAILED: {e}", ticker=t, level=logging.ERROR)
                        failed.append({"ticker": t, "error": str(e)})
        else:
            # AlphaVantage-first: default is sequential (rate-limit friendly), but can be parallelized.
            max_workers = min(int(alphavantage_max_workers), max(1, len(to_process)))
            if max_workers <= 1:
                for t in to_process:
                    i = idx_by_ticker.get(t) or 0
                    try:
                        payload = _choose_with_cross_fallback(t)
                        price = payload.get("price")
                        shares = payload.get("shares_outstanding")
                        row = _write_cache_for_ticker(t, price, shares)
                        updated.append(row)
                        _progress_log(f"Ticker {i}/{len(tickers_norm)} END", ticker=t)
                    except Exception as e:
                        logger.exception(f"Failed to refresh SpecilMetricCache for {t}")
                        _progress_log(f"Ticker refresh FAILED: {e}", ticker=t, level=logging.ERROR)
                        failed.append({"ticker": t, "error": str(e)})
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {executor.submit(_choose_with_cross_fallback, t): t for t in to_process}
                    for fut in as_completed(future_map):
                        t = future_map[fut]
                        i = idx_by_ticker.get(t) or 0
                        try:
                            payload = fut.result() or {}
                            price = payload.get("price")
                            shares = payload.get("shares_outstanding")
                            row = _write_cache_for_ticker(t, price, shares)
                            updated.append(row)
                            _progress_log(f"Ticker {i}/{len(tickers_norm)} END", ticker=t)
                        except Exception as e:
                            logger.exception(f"Failed to refresh SpecilMetricCache for {t}")
                            _progress_log(f"Ticker refresh FAILED: {e}", ticker=t, level=logging.ERROR)
                            failed.append({"ticker": t, "error": str(e)})

        # After refreshing today's SpecilMetricCache values, compute + cache the daily rankings
        rankings_info = None
        try:
            _progress_log("Computing + caching daily rankings (after refresh)", stage="rankings")
            rankings_payload = compute_and_cache_special_metric_rankings(driver)
            rankings_info = {
                "cache_date": rankings_payload.get("cache_date"),
                "count": rankings_payload.get("count"),
                "rejected_count": len(rankings_payload.get("rejected") or []),
            }
            _progress_log(f"Rankings cached: count={rankings_info.get('count')}, rejected_count={rankings_info.get('rejected_count')}")
        except Exception as e:
            logger.exception("Failed to compute and cache rankings after refresh")
            rankings_info = {"error": str(e)}
            _progress_log(f"Rankings computation FAILED: {e}", stage="rankings_error", level=logging.ERROR)

        result = {
            "tickers_count": len(tickers),
            "updated_count": len(updated),
            "failed_count": len(failed),
            "updated": updated,
            "failed": failed,
            "rankings": rankings_info,
        }
        if summary:
            _progress_log(
                f"Refresh completed (summary): updated={len(updated)}, failed={len(failed)}",
                stage="complete",
            )
            return {
                "tickers_count": result["tickers_count"],
                "updated_count": result["updated_count"],
                "failed_count": result["failed_count"],
                "rankings": result["rankings"],
            }

        _progress_log(
            f"Refresh completed: updated={len(updated)}, failed={len(failed)}",
            stage="complete",
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to refresh SpecilMetricCache for all", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass



# curl -X POST "http://localhost:8080/api/special_metrics/refresh_StockPrices_SharesOutstanding_MetricOldCache" -H "Content-Type: application/json"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/refresh_StockPrices_SharesOutstanding_MetricOldCache" -H "Content-Type: application/json"
@router.post("/api/special_metrics/refresh_StockPrices_SharesOutstanding_MetricOldCache")
def refresh_StockPrices_SharesOutstanding_MetricOldCache():
    """Populate/update `StockPrices_SharesOutstanding_MetricOldCache` from Yahoo Finance (yfinance).

    What it stores per ticker:
      - 1Y daily closes  (prices_json)
      - 2Y shares outstanding history (shares_json)

    Behavior (simplified):
      - Ignores whatever is currently stored.
      - For every ticker, fetch fresh:
          - 1Y daily closes
          - shares outstanding history (filtered to last 2Y)
      - Overwrites the Neo4j node (upsert) and sets cache_date to today.
    """

    if yf is None:
        raise HTTPException(status_code=500, detail="yfinance is not available in this environment")

    driver = _get_driver()
    try:
        # Ensure unique constraint exists
        try:
            create_stockprices_shares_old_cache_constraint(driver)
        except Exception:
            pass

        tickers = list_all_tickers(driver)
        tickers_norm = [(t or "").upper().strip() for t in (tickers or []) if (t or "").strip()]
        if not tickers_norm:
            raise HTTPException(status_code=404, detail="No tickers found in database")

        _progress_log(f"Starting OLD market cache refresh for {len(tickers_norm)} tickers", stage="start")

        updated: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        today = datetime.now().date().isoformat()
        idx_by_ticker = {t: i for i, t in enumerate(tickers_norm, 1)}
        total = len(tickers_norm)

        # In simplified mode, ALWAYS fetch for every ticker.
        to_fetch: List[str] = list(tickers_norm)

        def _fetch_from_yfinance(ticker_symbol: str) -> Dict[str, Any]:
            """Fetch fresh close prices (1Y) + shares history (filtered to last 2Y) from yfinance."""
            ticker_symbol = (ticker_symbol or "").upper().strip()
            prices_list: List[Dict[str, Any]] = []
            shares_list: List[Dict[str, Any]] = []

            # Prices: full 1Y
            dfp = yf.download(ticker_symbol, period="1y", interval="1d", progress=False)

            if dfp is not None and not dfp.empty and "Close" in dfp.columns:
                close_obj = dfp["Close"]
                if isinstance(close_obj, pd.DataFrame):
                    close_series = close_obj[ticker_symbol] if ticker_symbol in close_obj.columns else close_obj.iloc[:, 0]
                else:
                    close_series = close_obj

                close_series = close_series.dropna()
                for dt, close in close_series.items():
                    ts = pd.to_datetime(dt, errors="coerce")
                    if ts is pd.NaT:
                        continue
                    c = _safe_float(close)
                    if c is None:
                        continue
                    prices_list.append({"date": ts.date().isoformat(), "close": float(c)})

            # Shares outstanding: full history filtered to last 2Y
            ticker_obj = yf.Ticker(ticker_symbol)
            try:
                shares_hist = ticker_obj.get_shares_full()
            except Exception:
                shares_hist = None

            if shares_hist is not None and hasattr(shares_hist, "empty") and not shares_hist.empty:
                try:
                    shares_hist.index = pd.to_datetime(shares_hist.index).tz_localize(None)
                except Exception:
                    shares_hist.index = pd.to_datetime(shares_hist.index)

                cutoff = pd.Timestamp.today().tz_localize(None) - pd.DateOffset(years=2)
                shares_hist = shares_hist.loc[shares_hist.index >= cutoff]

                col = shares_hist.columns[0] if len(getattr(shares_hist, "columns", [])) > 0 else None

                    # yfinance edge-case: `get_shares_full()` can sometimes collapse to a scalar
                    # (e.g., a 1x1 DF -> squeeze() -> numpy scalar). Handle DF/Series/scalar robustly.
                if col is not None:
                    series_obj = shares_hist[col]
                else:
                    series_obj = shares_hist.squeeze()

                    # Normalize to a pandas Series if possible.
                if isinstance(series_obj, pd.DataFrame):
                    # Should not usually happen, but keep first column.
                    if len(series_obj.columns) > 0:
                        series_obj = series_obj.iloc[:, 0]
                if isinstance(series_obj, pd.Series):
                    series = series_obj.dropna()
                    for dt, so in series.items():
                        ts = pd.to_datetime(dt, errors="coerce")
                        if ts is pd.NaT:
                            continue
                        v = _safe_float(so)
                        if v is None:
                            continue
                        shares_list.append({"date": ts.date().isoformat(), "shares_outstanding": float(v)})
                else:
                    # Scalar (no date index) -> skip rather than crash
                    pass

            return {"ticker": ticker_symbol, "prices": prices_list, "shares": shares_list}

        # Parallelize yfinance fetch for all tickers
        if to_fetch:
            max_workers = min(int(SPECIAL_METRIC_OLD_CACHE_YAHOO_MAX_WORKERS), max(1, len(to_fetch)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {}
                for t in to_fetch:
                    i = idx_by_ticker.get(t) or 0
                    _progress_log(f"Ticker {i}/{total} START", ticker=t)
                    future_map[
                        executor.submit(
                            _fetch_from_yfinance,
                            t,
                        )
                    ] = t

                for fut in as_completed(future_map):
                    t = future_map[fut]
                    i = idx_by_ticker.get(t) or 0
                    try:
                        payload = fut.result() or {}
                        prices_fetched = payload.get("prices") or []
                        shares_fetched = payload.get("shares") or []

                        # Final trim (enforce windows) even though we fetched fresh.
                        prices_merged = _merge_timeseries_points(
                            [],
                            prices_fetched,
                            date_key="date",
                            value_key="close",
                            keep_since_days_ago=365,
                        )
                        shares_merged = _merge_timeseries_points(
                            [],
                            shares_fetched,
                            date_key="date",
                            value_key="shares_outstanding",
                            keep_since_days_ago=730,
                        )

                        # Write sequentially to avoid threading issues with Neo4j sessions
                        upsert_stockprices_shares_old_cache(driver, t, prices=prices_merged, shares=shares_merged)
                        updated.append(
                            {
                                "ticker": t,
                                "prices_count": len(prices_merged),
                                "shares_points": len(shares_merged),
                                "mode": "overwrite_full_fetch",
                                "fetched_prices_points": len(prices_fetched),
                                "fetched_shares_points": len(shares_fetched),
                            }
                        )
                        _progress_log(f"Ticker {i}/{total} END", ticker=t)
                    except Exception as e:
                        logger.exception(f"Failed to refresh old market cache for {t}")
                        _progress_log(f"Ticker refresh FAILED: {e}", ticker=t, level=logging.ERROR)
                        failed.append({"ticker": t, "error": str(e)})

        return {
            "tickers_count": len(tickers_norm),
            "updated_count": len(updated),
            "failed_count": len(failed),
            "updated": updated,
            "failed": failed,
        }
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to refresh StockPrices_SharesOutstanding_MetricOldCache", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass





        

# curl -X POST "http://localhost:8080/api/special_metrics/market_cap" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/market_cap" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/market_cap")
def get_market_cap(payload: TickerRequest):
    """Return computed Market Cap for a given ticker.

    Market Cap = Stock Price × Shares Outstanding
    """
    ticker = payload.ticker.upper()
    driver = _get_driver()

    try:
        company_data = fetch_special_metric_cached(driver, ticker)
        stock_price = fetch_current_stock_price_cached(driver, ticker)
        market_cap = _calculate_market_cap(stock_price, company_data.get("shares_outstanding") if company_data else None)

        if market_cap is None:
            raise HTTPException(status_code=404, detail=f"Market cap not found for ticker: {ticker}")
        return {"market_cap": market_cap}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch market cap", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass
    

# curl -X POST "http://localhost:8080/api/special_metrics/shares_outstanding" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/shares_outstanding" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/shares_outstanding")
def get_shares_outstanding(payload: TickerRequest):
    """Return Shares Outstanding and Market Cap for a given ticker"""
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        company_data = fetch_special_metric_cached(driver, ticker)

        if not company_data.get("shares_outstanding"):
            raise HTTPException(status_code=404,detail=f"Market cap not found for ticker: {ticker}")
        return {"shares_outstanding": company_data["shares_outstanding"]}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch shares_outstanding", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass
    


# curl -X POST "http://localhost:8080/api/special_metrics/stock_price" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/stock_price" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/stock_price")
def get_stock_price(payload: TickerRequest):
    """Return Shares Outstanding and Market Cap for a given ticker"""
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        stock_price = fetch_current_stock_price_cached(driver, ticker)

        if not stock_price:
            raise HTTPException(status_code=404,detail=f"Market cap not found for ticker: {ticker}")
        return {"stock_price": stock_price}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch stock_price", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass


# curl -X POST "http://localhost:8080/api/special_metrics/multiples_table_metric" -H "Content-Type: application/json" -d '{"ticker":"AAPL","metric_name":"EBITA_Last10Y_AVG"}'
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/multiples_table_metric" -H "Content-Type: application/json" -d '{"ticker":"AAPL","metric_name":"EBITA_Last10Y_AVG"}'
@router.post("/api/special_metrics/multiples_table_metric")
def get_multiples_table_metric(payload: MultiplesTableMetricRequest):
    """Return a single MultiplesTable metric entry as a **dict**, not a JSON string.

    Background:
      In Neo4j, :Metric_MultiplesTable nodes store each metric property as a JSON
      string (because dicts are json-dumped before write).

    Input:
      - ticker: company ticker
      - metric_name: the property name on the :Metric_MultiplesTable node

    Output example:
      {"Type": "Denominator", "Value": 417878571.4285714}
    """
    ticker = payload.ticker.upper().strip()
    metric_name = (payload.metric_name or "").strip()
    if not ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    if not metric_name:
        raise HTTPException(status_code=422, detail="metric_name is required")

    driver = _get_driver()
    try:
        query = """
        MATCH (m:Metric_MultiplesTable {ticker: $ticker, metricName: 'MultiplesTable'})
        RETURN m[$metric_name] AS v
        """
        with driver.session() as session:
            row = session.run(query, ticker=ticker, metric_name=metric_name).single()

        if not row:
            raise HTTPException(status_code=404, detail=f"Metric_MultiplesTable node not found for ticker: {ticker}")

        raw_val = row.get("v")
        if raw_val is None:
            raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found for ticker: {ticker}")

        # Stored as JSON string in Neo4j; parse into dict for API response.
        if isinstance(raw_val, str):
            try:
                parsed = json.loads(raw_val)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Stored value for '{metric_name}' is not valid JSON: {e}",
                )
        else:
            parsed = raw_val

        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=500,
                detail=f"Stored value for '{metric_name}' is not a dict after parsing",
            )

        # Optional: enforce expected keys
        if "Type" not in parsed or "Value" not in parsed:
            # still return parsed but signal shape mismatch
            return {"data": parsed, "warning": "Expected keys {Type, Value} not found"}

        return parsed
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch MultiplesTable metric", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass



# curl -X POST "http://localhost:8080/api/special_metrics/intrinsic_to_mc" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/intrinsic_to_mc" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/intrinsic_to_mc")
def get_intrinsic_to_mc(payload: TickerRequest):
    """Return intrinsic to market cap ratio for a given ticker"""
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        # Fetch required inputs
        intrinsic_value = get_Intrinsic_value(driver, ticker)
        company_data = fetch_special_metric_cached(driver, ticker)
        stock_price = fetch_current_stock_price_cached(driver, ticker)

        # Market cap MUST be computed (never taken directly from Alpha Vantage)
        market_cap = _calculate_market_cap(stock_price, company_data.get("shares_outstanding") if company_data else None)

        ratio = intrinsic_to_mc_calculator(intrinsic_value, market_cap)
        if ratio is None:
            reasons = {}
            try:
                if intrinsic_value is None or (isinstance(intrinsic_value, float) and math.isnan(intrinsic_value)) or float(intrinsic_value) <= 0:
                    reasons["intrinsic_value"] = "missing, NaN, or <= 0"
            except Exception:
                reasons["intrinsic_value"] = "invalid type"
            try:
                if market_cap is None or (isinstance(market_cap, float) and math.isnan(market_cap)) or float(market_cap) <= 0:
                    reasons["market_cap"] = "missing, NaN, or <= 0"
            except Exception:
                reasons["market_cap"] = "invalid type"
            raise HTTPException(status_code=404, detail={"message": f"intrinsic_to_mc unavailable for ticker: {ticker}", "reasons": reasons})
        return {"intrinsic_to_mc": ratio}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch intrinsic_to_mc", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass



# curl -X POST "http://localhost:8080/api/special_metrics/intrinsic_value" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/intrinsic_value" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/intrinsic_value")
def get_intrinsic_value(payload: TickerRequest):
    """Return intrinsic value (Equity Value) from Neo4j ValuationSummary."""
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        intrinsic_value = get_Intrinsic_value(driver, ticker)
        if not _is_valid_number(intrinsic_value, positive=False):
            raise HTTPException(status_code=404, detail=f"Intrinsic value not found for ticker: {ticker}")
        return {"intrinsic_value": float(intrinsic_value)}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch intrinsic_value", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass


# curl -X POST "http://localhost:8080/api/special_metrics/roic" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/roic" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/roic")
def get_roic(payload: TickerRequest):
    """Return the last 5-year average ROIC from Neo4j Metric node.

    Metric: ReturnOnInvestedCapitalInclGoodwill
    """
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        roic_5y_avg = get_last_5yr_avg_ROIC(driver, ticker)
        if not _is_valid_number(roic_5y_avg, positive=False):
            raise HTTPException(status_code=404, detail=f"ROIC 5Y average not found for ticker: {ticker}")
        return {"roic_5y_avg": float(roic_5y_avg)}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch roic", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass


# curl -X POST "http://localhost:8080/api/special_metrics/earnings_yield" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/earnings_yield" -H "Content-Type: application/json" -d "{\"ticker\": \"AAPL\"}"
@router.post("/api/special_metrics/earnings_yield")
def get_earnings_yield(payload: TickerRequest):
    """Return Earnings Yield using 5-year avg Net Income, Shares Outstanding, and current price.

    Computation:
      EPS(5Y avg) = NetIncome(5Y avg) / SharesOutstanding
      EarningsYield = EPS(5Y avg) / StockPrice

    Notes:
      - price/shares are sourced from SpecilMetricCache if available; otherwise external API calls
        may happen unless USE_ONLY_CACHE_NODES is enabled.
      - Market cap is never read from Alpha Vantage; it is computed elsewhere when needed.
    """
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        net_income_5y_avg = get_last_5yr_avg_NetIncome(driver, ticker)
        company_data = fetch_special_metric_cached(driver, ticker)
        shares_outstanding = company_data.get("shares_outstanding") if company_data else None
        stock_price = fetch_current_stock_price_cached(driver, ticker)

        reasons = {}
        if not _is_valid_number(net_income_5y_avg, positive=False):
            reasons["net_income_5y_avg"] = "missing or NaN"
        if not _is_valid_number(shares_outstanding, positive=True):
            reasons["shares_outstanding"] = "missing, NaN, or <= 0"
        if not _is_valid_number(stock_price, positive=True):
            reasons["stock_price"] = "missing, NaN, or <= 0"
        if reasons:
            raise HTTPException(status_code=404, detail={"message": f"earnings_yield unavailable for ticker: {ticker}", "reasons": reasons})

        eps_5y_avg = float(net_income_5y_avg) / float(shares_outstanding)
        earnings_yield = eps_5y_avg / float(stock_price)

        return {"earnings_yield": float(earnings_yield)}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch earnings_yield", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass


# curl -X POST "http://localhost:8080/api/special_metrics/margin_of_safety" -H "Content-Type: application/json" -d "{\"ticker\": \"COST\"}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/margin_of_safety" -H "Content-Type: application/json" -d "{\"ticker\": \"COST\"}"
@router.post("/api/special_metrics/margin_of_safety")
def get_margin_of_safety(payload: TickerRequest):
    """Return Margin of Safety for a given ticker.

    Formula:
      margin_of_safety = 1 - (stock_price / intrinsic_value)

    Where:
      - intrinsic_value = Equity Value from ValuationSummary (`get_Intrinsic_value`)
      - stock_price from cache/API (`fetch_current_stock_price_cached`)
    """
    ticker = payload.ticker.upper()

    driver = _get_driver()
    try:
        intrinsic_value = get_Intrinsic_value(driver, ticker)
        stock_price = fetch_current_stock_price_cached(driver, ticker)

        reasons = {}
        if not _is_valid_number(intrinsic_value, positive=True):
            reasons["intrinsic_value"] = "missing, NaN, or <= 0"
        if not _is_valid_number(stock_price, positive=True):
            reasons["stock_price"] = "missing, NaN, or <= 0"
        if reasons:
            raise HTTPException(status_code=404, detail={"message": f"margin_of_safety unavailable for ticker: {ticker}", "reasons": reasons})

        margin_of_safety = 1.0 - (float(stock_price) / float(intrinsic_value))

        return {"margin_of_safety": float(margin_of_safety)}
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch margin_of_safety", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass




# curl -X POST "http://localhost:8080/api/special_metrics/investment_factor_ranking_table" -H "Content-Type: application/json" -d '{"user_query": "companies in the Discount Stores industry"}'
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/investment_factor_ranking_table" -H "Content-Type: application/json" -d '{"user_query": "companies in the Discount Stores industry"}'
# curl -X POST "http://localhost:8080/api/special_metrics/investment_factor_ranking_table" -H "Content-Type: application/json" -d "{\"tickers\": [\"AAPL\", \"MSFT\", \"AMZN\"]}"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/investment_factor_ranking_table" -H "Content-Type: application/json" -d "{\"tickers\": [\"AAPL\", \"MSFT\", \"AMZN\"]}"
@router.post("/api/special_metrics/investment_factor_ranking_table")
def get_investment_factor_ranking_table(payload: TickersRequest):
    """Return cached V-Invest Investment Factor ranking data filtered to requested tickers.

    IMPORTANT:
      - This endpoint reads from `SpecialMetricRankingCache` (same logic as
        `investment_factor_ranking_table_for_all_companies`) and therefore does
        **NOT** recalculate V_Quality/V_Value/V_Rating/etc.
      - Tickers that do not have cached ranking data are filtered out.

    Response:
      { cache_date, count, RankingByTicker }
        - RankingByTicker: {"TICKER": {"ranking": {...}, "metrics": {...}}, ...}
    """

    tickers: List[str] = payload.tickers or []

    # If user_query is provided, use the ticker finder to generate tickers.
    user_query = (payload.user_query or "").strip()
    if user_query:
        try:
            # Lazy import to avoid adding heavy LLM deps during app startup if not used.
            from app.utills.ticker_finder import find_tickers

            tickers = find_tickers(user_query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to resolve tickers from user_query: {e}")

    tickers_norm = [(t or "").upper().strip() for t in (tickers or []) if (t or "").strip()]
    if not tickers_norm:
        raise HTTPException(status_code=422, detail="No tickers provided (either pass `tickers` or a non-empty `user_query`).")

    driver = _get_driver()
    try:
        today = datetime.now().date().isoformat()
        with driver.session() as session:
            row = session.run(
                """
                MATCH (c:SpecialMetricRankingCache)
                WITH c, c.cache_date AS cd
                ORDER BY (CASE WHEN cd = $today THEN 1 ELSE 0 END) DESC, cd DESC
                RETURN c.Ranking AS ranking, c.cache_date AS cache_date
                LIMIT 1
                """,
                today=today,
            ).single()

        if not row:
            raise HTTPException(status_code=404, detail="SpecialMetricRankingCache not found. Run refresh_special_metric_cache_all first.")

        ranking_raw = row.get("ranking")
        cache_date = row.get("cache_date")
        if not ranking_raw:
            return {"cache_date": cache_date, "count": 0, "RankingByTicker": {}}

        try:
            parsed = json.loads(ranking_raw) if isinstance(ranking_raw, str) else ranking_raw
        except Exception:
            raise HTTPException(status_code=500, detail="Stored Ranking is not valid JSON")

        # New cache shape: dict keyed by ticker.
        ranking_by_ticker: Dict[str, Dict[str, Any]] = {}
        if isinstance(parsed, dict):
            ranking_by_ticker = parsed
        elif isinstance(parsed, list):
            # Backwards-compat: old shape was list[dict] (ranking rows only). Convert to a ticker-keyed map.
            for r in parsed:
                if not isinstance(r, dict):
                    continue
                tk = r.get("Ticker") or r.get("ticker")
                if not tk:
                    continue
                tkn = str(tk).upper().strip()
                if not tkn:
                    continue
                ranking_by_ticker[tkn] = {"ranking": r, "metrics": {}}
        else:
            raise HTTPException(status_code=500, detail="Stored Ranking is neither a list nor a dict")

        # Filter requested tickers and filter out tickers that have no cached *ranking* data.
        # (We keep the cache payload as-is, but only include tickers where a ranking row exists.)
        filtered: Dict[str, Dict[str, Any]] = {}
        for t in tickers_norm:
            entry = ranking_by_ticker.get(t)
            if entry is None:
                continue

            # Cache values are expected to be one of:
            #   1) {"ranking": {...}, "metrics": {...}}  (new)
            #   2) {...ranking row...}                    (older/custom)
            ranking_row = None
            if isinstance(entry, dict) and "ranking" in entry:
                ranking_row = entry.get("ranking")
            else:
                ranking_row = entry

            # If ranking_row is missing/empty, filter out.
            if not isinstance(ranking_row, dict) or not ranking_row:
                continue

            filtered[t] = entry

        return {
            "cache_date": cache_date,
            "count": len(filtered),
            "RankingByTicker": _json_sanitize(filtered),
        }
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch investment factor ranking table", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass






# curl -X POST "http://localhost:8080/api/special_metrics/investment_factor_ranking_table_for_all_companies" -H "Content-Type: application/json"
# curl -X POST "http://34.68.84.147:8080/api/special_metrics/investment_factor_ranking_table_for_all_companies" -H "Content-Type: application/json"
@router.post("/api/special_metrics/investment_factor_ranking_table_for_all_companies")
def get_investment_factor_ranking_table_for_all_companies():
    """
    Read the most recent SpecialMetricRankingCache (prefer today's date if present) and
    return Ranking as a parsed list (not string).
    Response:
      - New cache format:
          { cache_date, count, RankingByTicker: { "TICKER": {"ranking": {...}, "metrics": {...}}, ... } }
      - Backwards compatible (older cache nodes):
          { cache_date, count, Ranking: [ ... ] }
    """
    driver = _get_driver()
    try:
        today = datetime.now().date().isoformat()
        with driver.session() as session:
            row = session.run(
                """
                MATCH (c:SpecialMetricRankingCache)
                WITH c, c.cache_date AS cd
                ORDER BY (CASE WHEN cd = $today THEN 1 ELSE 0 END) DESC, cd DESC
                RETURN c.Ranking AS ranking, c.cache_date AS cache_date
                LIMIT 1
                """,
                today=today,
            ).single()
        if not row:
            raise HTTPException(status_code=404, detail="SpecialMetricRankingCache not found. Compute rankings first.")

        ranking_raw = row.get("ranking")
        cache_date = row.get("cache_date")
        if not ranking_raw:
            return {"cache_date": cache_date, "count": 0, "Ranking": []}

        try:
            parsed = json.loads(ranking_raw) if isinstance(ranking_raw, str) else ranking_raw
        except Exception:
            raise HTTPException(status_code=500, detail="Stored Ranking is not valid JSON")

        # New: dict keyed by ticker
        if isinstance(parsed, dict):
            return {
                "cache_date": cache_date,
                "count": len(parsed),
                "RankingByTicker": parsed,
            }

        # Old: list[dict] ranking rows
        if not isinstance(parsed, list):
            raise HTTPException(status_code=500, detail="Stored Ranking is neither a list nor a dict")

        return {
            "cache_date": cache_date,
            "count": len(parsed),
            "Ranking": parsed,
        }
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to read SpecialMetricRankingCache", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass


# curl -X GET "http://localhost:8080/api/special_metrics/investment_factor_ranking_table_for_all_companies/2025-12-11" -H "Content-Type: application/json"
# curl -X GET "http://34.68.84.147:8080/api/special_metrics/investment_factor_ranking_table_for_all_companies/2025-12-11" -H "Content-Type: application/json"
@router.get("/api/special_metrics/investment_factor_ranking_table_for_all_companies/{cache_date}")
def get_investment_factor_ranking_table_for_all_companies_by_date(cache_date: str):
    """
    Return the Investment Factor Ranking table for a specific cache_date (YYYY-MM-DD)
    without requiring a request body. Example:
      GET /api/special_metrics/investment_factor_ranking_table_for_all_companies/2025-12-11
    Response:
      - New cache format:
          { cache_date, count, RankingByTicker: { "TICKER": {"ranking": {...}, "metrics": {...}}, ... } }
      - Backwards compatible (older cache nodes):
          { cache_date, count, Ranking: [ ... ] }
    """
    # Validate date format (basic ISO date)
    try:
        datetime.fromisoformat(cache_date)
    except Exception:
        raise HTTPException(status_code=422, detail="cache_date must be ISO format YYYY-MM-DD")

    driver = _get_driver()
    try:
        with driver.session() as session:
            row = session.run(
                """
                MATCH (c:SpecialMetricRankingCache {cache_date: $cache_date})
                RETURN c.Ranking AS ranking, c.cache_date AS cache_date
                """,
                cache_date=cache_date,
            ).single()
        if not row:
            raise HTTPException(status_code=404, detail=f"SpecialMetricRankingCache not found for date: {cache_date}")

        ranking_raw = row.get("ranking")
        if not ranking_raw:
            return {"cache_date": cache_date, "count": 0, "Ranking": []}

        try:
            parsed = json.loads(ranking_raw) if isinstance(ranking_raw, str) else ranking_raw
        except Exception:
            raise HTTPException(status_code=500, detail="Stored Ranking is not valid JSON")

        if isinstance(parsed, dict):
            return {
                "cache_date": cache_date,
                "count": len(parsed),
                "RankingByTicker": parsed,
            }

        if not isinstance(parsed, list):
            raise HTTPException(status_code=500, detail="Stored Ranking is neither a list nor a dict")

        return {
            "cache_date": cache_date,
            "count": len(parsed),
            "Ranking": parsed,
        }
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500(f"Failed to read SpecialMetricRankingCache for {cache_date}", e)
    finally:
        try:
            driver.close()
        except Exception:
            pass




"""


Column Name    | Type               | Description
---------------|--------------------|------------------------------------------------------------
Ticker         | string             | Stock ticker symbol (e.g., COST)

V_Rating       | float              | Final weighted score (~0–100). Higher is better

Status         | string (enum)      | One of:
                                            - V-Elite 10
                                            - V-Elite 50
                                            - V-Elite 100
                                            - V-Elite 500
                                            - V-Qualified
                                            - REJECT: Missing Gatekeeper Data
                                            - REJECT: Distress Zone
                                            - REJECT: Over-Leveraged
                                            - REJECT: Zero/Neg ROIC

Rank           | integer (nullable) | Rank among qualified tickers only (1 = best).
                                            NULL if Status starts with "REJECT"

V_Quality      | float              | Sub-score (0–100) from ROIC, revenue growth, dilution

V_Value        | float              | Sub-score (0–100) from VEliteYield and IntrinsicToMarketCap

V_Safety       | float              | Sub-score (0–100) from Altman Z, Piotroski F, Debt/EBITDA

V_Momentum     | float              | Sub-score (0–100) from 6M ROC, Above 200SMA, RSI





"""
