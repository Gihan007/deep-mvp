"""Consolidated endpoint for /api/special_metrics/investment_factor_ranking_table.

This version reads V-Rating metrics from Postgres only.
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()
logger = logging.getLogger(__name__)


# =====================
# Minimal config loader
# =====================
class _Config:
    POSTGRES_URL = os.environ.get("POSTGRES_URL", "")


config = _Config()


# =====================
# Models
# =====================
class RankingTableRequest(BaseModel):
    run_date: date = Field(..., description="Run date (YYYY-MM-DD)")
    limit: int = Field(10, ge=1, le=1000, description="Max rows to return")


# =====================
# Core helpers
# =====================

def _log_and_raise_500(msg: str, exc: Exception) -> None:
    logger.exception(msg)
    raise HTTPException(status_code=500, detail=f"{msg}: {exc}")


def _get_pg_conn():
    if not config.POSTGRES_URL:
        raise HTTPException(status_code=500, detail="POSTGRES_URL is not configured")
    try:
        return psycopg2.connect(config.POSTGRES_URL)
    except Exception as e:
        logger.exception("Failed to connect to Postgres")
        raise HTTPException(status_code=500, detail=f"Postgres connection error: {e}")


def _json_sanitize(obj: Any) -> Any:
    """Recursively convert values to JSON-safe primitives.

    - NaN / +/-Inf -> None
    - numpy scalars -> python scalars
    """
    # dict
    if isinstance(obj, dict):
        return {str(k): _json_sanitize(v) for k, v in obj.items()}

    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [_json_sanitize(v) for v in obj]

    # floats
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    return obj


SQL_QUERY = """
SELECT
    c.ticker,
    hmd.data ->> 'RunDate' AS run_date,
    (hmd.data ->> 'FilingYear')::numeric AS filing_year,
    (hmd.data ->> 'VRating')::numeric AS v_rating,
    (hmd.data ->> 'VQuality')::numeric AS v_quality,
    (hmd.data ->> 'VValue')::numeric AS v_value,
    (hmd.data ->> 'VSafety')::numeric AS v_safety,
    (hmd.data ->> 'VMomentum')::numeric AS v_momentum,
    (hmd.data ->> 'PriceToValue')::numeric AS price_to_value,
    hmd.created_at
FROM company_data.historical_metric_data hmd
JOIN company_data.company c
  ON hmd.company_id = c.company_id
JOIN company_data.metric_category mc
  ON hmd.category_id = mc.category_id
WHERE mc.name = 'VRating'
  AND c.ticker IS NOT NULL
  AND COALESCE(hmd.data ->> 'VRating', '') <> ''
  AND (hmd.data ->> 'RunDate') = %s
ORDER BY (hmd.data ->> 'VRating')::numeric DESC,
         c.ticker ASC
LIMIT %s
"""


# =====================
# Endpoint
# =====================
@router.post("/api/special_metrics/investment_factor_ranking_table")
def get_investment_factor_ranking_table(payload: RankingTableRequest):
    """Return V-Rating ranking data from Postgres for a run_date."""

    conn = _get_pg_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL_QUERY, (payload.run_date.isoformat(), payload.limit))
            rows = [dict(r) for r in cur.fetchall()]

        return {
            "run_date": payload.run_date.isoformat(),
            "count": len(rows),
            "results": _json_sanitize(rows),
        }
    except HTTPException:
        raise
    except Exception as e:
        _log_and_raise_500("Failed to fetch investment factor ranking table", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
