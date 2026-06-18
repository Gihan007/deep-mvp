"""Simple tests for Dynamic Table endpoints.

These endpoints are READ-ONLY and return JSON with:
- columns: list[str]
- rows: list[dict]

Run:
  python testing/api_testing/end_points_checker/dynamic_table_router_tester.py

Make sure your API is running first.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import requests


BASE_URL = "http://localhost:8080"


def post_form(path: str, form: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, data=form, timeout=120)
    print(f"\nPOST {url}")
    print("Status:", resp.status_code)
    try:
        return resp.json()
    except Exception:
        print(resp.text)
        raise


def validate_table_payload(payload: Dict[str, Any]) -> None:
    assert payload.get("status") == "success", payload
    assert isinstance(payload.get("columns"), list), payload
    assert isinstance(payload.get("rows"), list), payload
    if payload["rows"]:
        assert isinstance(payload["rows"][0], dict), payload


def test_dynamic_table(key: str, ticker: str) -> None:
    payload = post_form(f"/api/dynamic_table/{key}", {"ticker": ticker})
    validate_table_payload(payload)

    print("key:", payload.get("key"))
    print("ticker:", payload.get("ticker"))
    print("columns count:", len(payload["columns"]))
    print("rows count:", len(payload["rows"]))
    print("first 3 columns:", payload["columns"][:3])
    print("first row preview:")
    print(json.dumps(payload["rows"][0] if payload["rows"] else {}, indent=2)[:1500])


if __name__ == "__main__":
    # Change ticker if needed.
    TICKER = "COST"

    keys: List[str] = [
        "3StatementModel",
        "FreeCashFlows",
        "ReportedFinancials",
        "InvestedCapital",
        "Performance",
        "ValuationForecastDriverValues",
        "ValuationSummary",
    ]

    for k in keys:
        test_dynamic_table(k, TICKER)
