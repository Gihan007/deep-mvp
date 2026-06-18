"""investment_factor_ranking_table_tool

LangChain tool that retrieves the most recent cached **V-Invest (Investment Factor)**
ranking table and returns focused subsets around a target ticker.

This mirrors the API logic in:
  `src/app/routes/get_special_metric_data_router.py`
    `POST /api/special_metrics/investment_factor_ranking_table_for_all_companies`

---------------------------------
Cache read behavior
---------------------------------
- Prefer **today's** `cache_date` if present; otherwise return the **latest** `cache_date`.
- Parses the stored JSON string in `(:SpecialMetricRankingCache).Ranking`.
- Supports BOTH formats in the stored cache:
  1) **New**: dict keyed by ticker =>
     `{ "AAPL": {"ranking": {...}, "metrics": {...}}, "MSFT": {...}, ... }`
  2) **Old**: list of dict rows (ranking only), where each row includes `Ticker`/`Rank`.
- Returns a **JSON string**.

---------------------------------
Output schema (what keys exist)
---------------------------------
The tool returns a JSON string with the following top-level keys:

- `cache_date`: str (YYYY-MM-DD)
- `target_ticker`: str
- `target_rank`: int | null
- `industry`: str | null
- `sector`: str | null

And the following focused subsets (all lists):
- `set_0_target_company_ranking_data`
- `set_1_overall_top10`
- `set_2_overall_rank_window` (target rank ± ~5 ranks)
- `set_3_same_industry_top10`
- `set_4_same_sector_top10`
- `set_5_same_industry_rank_window` (target ± ~5 positions within industry list)
- `set_6_same_sector_rank_window` (target ± ~5 positions within sector list)

Each list item is shaped like:

```json
{
  "ticker": "AAPL",
  "rank": 7,
  "ranking": { ... },
  "metrics": { ... }
}
```

---------------------------------
`ranking` object keys
---------------------------------
The `ranking` object is the score/status payload produced by the ranking system.
Common keys include (not all are always present):

- `Rank` (int)
- `Status` (str)
- `V_Rating` (float|int)
- `V_Quality` (float|int)
- `V_Value` (float|int)
- `V_Safety` (float|int)
- `V_Momentum` (float|int)

---------------------------------
`metrics` object keys
---------------------------------
The `metrics` object contains the underlying factor metrics used to compute rankings.
Common keys include (not all are always present):

- `ReturnOnInvestedCapital`
- `RevenueGrowth`
- `ShareDilution`
- `VEliteYield`
- `IntrinsicToMarketCap`
- `AltmanZScore`
- `PiotroskiFScore`
- `DebtToEBITDA`
- `ROC_6M`
- `Above_200SMA`
- `RSI_14`
- `MarketCap`
- `SharesOutstanding`
- `SharesOutstanding_1Y_Ago`
- `MarketEnterpriseValue`
- `EBIT_LastYear`
- `IntrinsicValue`

Notes:
- **Do not assume** a key exists; treat missing keys as missing data.
- `rank` is the universe rank among **Qualified** companies (1 = best). If a company
  is present in cache but not ranked/qualified, `rank` may be `null`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain.tools import tool
from neo4j import GraphDatabase

from config import get_config
from app.utills.tool_output_collector import add_tool_output

logger = logging.getLogger(__name__)
config = get_config()


def _get_driver():
    if not config.NEO4J_URI:
        raise ValueError("NEO4J_URI is not configured")
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
    )


def _fetch_most_recent_ranking(driver) -> Dict[str, Any]:
    """Return the most recent ranking cache payload.
    Response shape:
      New cache format:
        {"cache_date": str|None, "count": int, "RankingByTicker": dict}
      Backwards compatible (older cache nodes):
        {"cache_date": str|None, "count": int, "Ranking": list[dict]}
    """
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
        return {"error": "SpecialMetricRankingCache not found. Compute rankings first (refresh_special_metric_cache_all)."}

    ranking_raw = row.get("ranking")
    cache_date = row.get("cache_date")
    if not ranking_raw:
        return {"cache_date": cache_date, "count": 0, "Ranking": []}

    try:
        parsed = json.loads(ranking_raw) if isinstance(ranking_raw, str) else ranking_raw
    except Exception as e:
        return {"error": f"Stored Ranking is not valid JSON: {e}", "cache_date": cache_date}

    if isinstance(parsed, dict):
        return {"cache_date": cache_date, "count": len(parsed), "RankingByTicker": parsed}

    if isinstance(parsed, list):
        return {"cache_date": cache_date, "count": len(parsed), "Ranking": parsed}

    return {"error": "Stored Ranking is neither a list nor a dict", "cache_date": cache_date}


def _parse_tool_input_target_ticker(raw: Optional[str]) -> Optional[str]:
    """Accept either a plain ticker string or a JSON string like {"target_ticker": "AAPL"}."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                v = obj.get("target_ticker") or obj.get("ticker")
                if v:
                    return str(v).upper().strip()
        except Exception:
            # fall back to raw string
            pass
    return s.upper().strip()


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        # handle floats like 7.0
        if isinstance(v, float) and (v != v):
            return None
        iv = int(float(v))
        return iv
    except Exception:
        return None


def _normalize_to_ranking_by_ticker(payload: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Dict[str, Any]]]:
    """Normalize payload into {ticker: {ranking:{...}, metrics:{...}}}.

    Returns: (cache_date, ranking_by_ticker)
    """
    cache_date = payload.get("cache_date")

    rbt = payload.get("RankingByTicker")
    if isinstance(rbt, dict):
        # Normalize keys to upper tickers
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in rbt.items():
            tk = str(k).upper().strip()
            if not tk:
                continue
            if isinstance(v, dict):
                out[tk] = {
                    "ranking": v.get("ranking") if isinstance(v.get("ranking"), dict) else (v.get("ranking") or {}),
                    "metrics": v.get("metrics") if isinstance(v.get("metrics"), dict) else (v.get("metrics") or {}),
                }
            else:
                out[tk] = {"ranking": {}, "metrics": {}}
        return cache_date, out

    ranking_list = payload.get("Ranking")
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(ranking_list, list):
        for row in ranking_list:
            if not isinstance(row, dict):
                continue
            tk = row.get("Ticker") or row.get("ticker")
            if not tk:
                continue
            tk = str(tk).upper().strip()
            out[tk] = {"ranking": row, "metrics": {}}
    return cache_date, out


def _sorted_ranked_entries(ranking_by_ticker: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return list entries sorted by Rank asc, excluding items with missing Rank."""
    entries: List[Dict[str, Any]] = []
    for tk, obj in (ranking_by_ticker or {}).items():
        ranking = (obj or {}).get("ranking") or {}
        r = _safe_int(ranking.get("Rank"))
        if r is None:
            continue
        entries.append({"ticker": tk, "rank": r, "ranking": ranking, "metrics": (obj or {}).get("metrics") or {}})
    entries.sort(key=lambda x: x["rank"])
    return entries


def _get_target_industry_sector(driver, target_ticker: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (industryName, sectorName) for the target ticker."""
    q = """
    MATCH (c:Company {ticker: $ticker})-[:BELONG_TO]->(i:Industry)
    OPTIONAL MATCH (i)-[:BELONG_TO]->(s:Sector)
    RETURN i.industryName AS industryName, s.sectorName AS sectorName
    """
    with driver.session() as session:
        row = session.run(q, ticker=target_ticker).single()
    if not row:
        return None, None
    return row.get("industryName"), row.get("sectorName")


def _get_tickers_in_industry(driver, industry_name: str) -> List[str]:
    if not industry_name:
        return []
    q = """
    MATCH (c:Company)-[:BELONG_TO]->(i:Industry)
    WHERE toLower(i.industryName) = toLower($industryName)
    RETURN DISTINCT c.ticker AS ticker
    """
    with driver.session() as session:
        return [str(r.get("ticker")).upper().strip() for r in session.run(q, industryName=industry_name) if r.get("ticker")]


def _get_tickers_in_sector(driver, sector_name: str) -> List[str]:
    if not sector_name:
        return []
    q = """
    MATCH (c:Company)-[:BELONG_TO]->(:Industry)-[:BELONG_TO]->(s:Sector)
    WHERE toLower(s.sectorName) = toLower($sectorName)
    RETURN DISTINCT c.ticker AS ticker
    """
    with driver.session() as session:
        return [str(r.get("ticker")).upper().strip() for r in session.run(q, sectorName=sector_name) if r.get("ticker")]



@tool
def investment_factor_ranking_table_tool(target_ticker: str) -> str:
    """Return focused V-Invest ranking subsets around a target ticker.

    Input:
      - target_ticker: e.g. "AAPL" (also accepts JSON string: {"target_ticker":"AAPL"})

    Output JSON (string) top-level keys:
      {
        "cache_date": "YYYY-MM-DD",
        "target_ticker": "AAPL",
        "target_rank": 7,
        "industry": "Discount Stores",
        "sector": "Consumer Defensive",
        "set_0_target_company_ranking_data": [ {"ticker": "AAPL", "rank": 7, "ranking": {...}, "metrics": {...}} ],
        "set_1_overall_top10": [ {ticker, rank, ranking, metrics}, ... ],
        "set_2_overall_rank_window": [ ... ],
        "set_3_same_industry_top10": [ ... ],
        "set_4_same_sector_top10": [ ... ],
        "set_5_same_industry_rank_window": [ ... ],
        "set_6_same_sector_rank_window": [ ... ]
      }

    Per-entry shape:
      { "ticker": str, "rank": int|null, "ranking": dict, "metrics": dict }

    `ranking` commonly includes:
      - Rank, Status, V_Rating, V_Quality, V_Value, V_Safety, V_Momentum

    `metrics` commonly includes:
      - ReturnOnInvestedCapital, RevenueGrowth, ShareDilution, VEliteYield,
        IntrinsicToMarketCap, AltmanZScore, PiotroskiFScore, DebtToEBITDA,
        ROC_6M, Above_200SMA, RSI_14, MarketCap, SharesOutstanding,
        SharesOutstanding_1Y_Ago, MarketEnterpriseValue, EBIT_LastYear,
        IntrinsicValue
    """
    logger.info(">>>>>>>>>>> Executing investment_factor_ranking_table_tool (focused subsets)")

    driver = None
    try:
        driver = _get_driver()
        # 1) Load cached ranking payload
        payload = _fetch_most_recent_ranking(driver)
        if payload.get("error"):
            return json.dumps(payload, default=str)

        # 2) Parse input
        target = _parse_tool_input_target_ticker(target_ticker)
        if not target:
            return json.dumps({"error": "target_ticker is required"})

        cache_date, ranking_by_ticker = _normalize_to_ranking_by_ticker(payload)

        # 2a) Target-only details (ranking + metrics). This is intentionally NOT filtered by Rank.
        # It should include the target even if Rank is missing (rank will be null).
        target_obj = ranking_by_ticker.get(target) if isinstance(ranking_by_ticker, dict) else None
        if not isinstance(target_obj, dict):
            target_obj = {"ranking": {}, "metrics": {}}
        target_ranking = target_obj.get("ranking") if isinstance(target_obj.get("ranking"), dict) else {}
        target_metrics = target_obj.get("metrics") if isinstance(target_obj.get("metrics"), dict) else {}
        set_0_target_company_ranking_data: List[Dict[str, Any]] = [
            {
                "ticker": target,
                "rank": _safe_int(target_ranking.get("Rank")),
                "ranking": target_ranking,
                "metrics": target_metrics,
            }
        ]

        ranked = _sorted_ranked_entries(ranking_by_ticker)

        # Build lookup rank -> entry and ticker -> entry
        by_rank: Dict[int, Dict[str, Any]] = {int(e["rank"]): e for e in ranked}
        by_ticker: Dict[str, Dict[str, Any]] = {str(e["ticker"]).upper().strip(): e for e in ranked}

        # 3) Set 1: top 10 overall
        set_1_overall_top10 = ranked[:10]

        # 4) Set 2: sliding window around target rank (+/- 5)
        # Prefer rank from the target-only payload. If missing, fall back to ranked list lookup.
        target_rank = set_0_target_company_ranking_data[0].get("rank")
        if target_rank is None:
            target_entry = by_ticker.get(target)
            target_rank = target_entry.get("rank") if target_entry else None
        set_2_overall_rank_window: List[Dict[str, Any]] = []
        if target_rank is not None:
            low = max(1, int(target_rank) - 5)
            high = int(target_rank) + 5
            # Collect existing ranks in [low, high]
            for r in range(low, high + 1):
                if r in by_rank:
                    set_2_overall_rank_window.append(by_rank[r])
            set_2_overall_rank_window.sort(key=lambda x: x["rank"])

        # 5) Same industry / sector (top 10 by rank within those groups)
        industry, sector = _get_target_industry_sector(driver, target)

        industry_tickers: set = set()
        sector_tickers: set = set()
        if industry:
            industry_tickers = set(_get_tickers_in_industry(driver, industry))
        if sector:
            sector_tickers = set(_get_tickers_in_sector(driver, sector))

        def _sliding_window_within(filtered_ranked: List[Dict[str, Any]], center_ticker: str, half_window: int = 5) -> List[Dict[str, Any]]:
            """Return window (center±half_window) within a pre-filtered rank-sorted list."""
            if not filtered_ranked:
                return []
            idx = None
            for i, e in enumerate(filtered_ranked):
                if str(e.get("ticker") or "").upper().strip() == center_ticker:
                    idx = i
                    break
            if idx is None:
                return []
            start = max(0, idx - int(half_window))
            end = min(len(filtered_ranked), idx + int(half_window) + 1)
            return filtered_ranked[start:end]

        # 5a) Sliding rank window inside same industry/sector lists (target ± 5 positions)
        set_5_same_industry_rank_window: List[Dict[str, Any]] = []
        if industry_tickers:
            industry_ranked = [e for e in ranked if e["ticker"] in industry_tickers]
            set_5_same_industry_rank_window = _sliding_window_within(industry_ranked, target, half_window=5)

        set_6_same_sector_rank_window: List[Dict[str, Any]] = []
        if sector_tickers:
            sector_ranked = [e for e in ranked if e["ticker"] in sector_tickers]
            set_6_same_sector_rank_window = _sliding_window_within(sector_ranked, target, half_window=5)

        set_3_same_industry_top10: List[Dict[str, Any]] = []
        if industry_tickers:
            set_3_same_industry_top10 = [e for e in ranked if e["ticker"] in industry_tickers][:10]

        set_4_same_sector_top10: List[Dict[str, Any]] = []
        if sector_tickers:
            set_4_same_sector_top10 = [e for e in ranked if e["ticker"] in sector_tickers][:10]

        result = {
            "cache_date": cache_date,
            "target_ticker": target,
            "target_rank": target_rank,
            "industry": industry,
            "sector": sector,
            # Primary (preferred) key name
            "set_0_target_company_ranking_data": set_0_target_company_ranking_data,
            "set_1_overall_top10": set_1_overall_top10,
            "set_2_overall_rank_window": set_2_overall_rank_window,
            "set_3_same_industry_top10": set_3_same_industry_top10,
            "set_4_same_sector_top10": set_4_same_sector_top10,
            "set_5_same_industry_rank_window": set_5_same_industry_rank_window,
            "set_6_same_sector_rank_window": set_6_same_sector_rank_window,
        }

        tool_output = {
            "tool_name": "investment_factor_ranking_table_tool",
            "input_arguments": {"target_ticker": target_ticker},
            "tool_output": str(result),
        }
        try:
            add_tool_output(tool_output)
        except Exception:
            pass

        return json.dumps(result, default=str)
    except Exception as e:
        msg = {"error": f"Failed to read SpecialMetricRankingCache: {e}"}
        logger.exception(msg["error"])
        return json.dumps(msg)
    finally:
        if driver:
            try:
                driver.close()
            except Exception:
                pass
