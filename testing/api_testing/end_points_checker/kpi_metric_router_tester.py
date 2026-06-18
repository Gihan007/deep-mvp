"""Simple tests for KPI Metric endpoints.

Make sure your API is running first.

Run:
  python3 testing/api_testing/end_points_checker/kpi_metric_router_tester.py

Endpoints:
  - POST /api/kpi/ingest
  - POST /api/kpi/properties
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import requests


BASE_URL = "http://localhost:8080"

# Provide the xlsx path on YOUR machine to upload to the API.
EXCEL_PATH = "/Users/dimuth/Documents/chat_bot/data_given_anand/stage_6/MetricsSoWhats.xlsx"


def post_json(path: str, payload: Dict[str, Any] | None = None, timeout_s: int = 180) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, json=payload, timeout=timeout_s)
    print(f"\nPOST {url}")
    print("Status:", resp.status_code)
    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        raise
    print(json.dumps(data, indent=2)[:3000])
    return data


def test_ingest() -> Dict[str, Any]:
    """Triggers Excel -> Neo4j ingest."""
    url = f"{BASE_URL}/api/kpi/ingest"
    with open(EXCEL_PATH, "rb") as f:
        files = {"file": ("MetricsSoWhats.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        resp = requests.post(url, files=files, timeout=180)
    print(f"\nPOST {url} (multipart file upload)")
    print("Status:", resp.status_code)
    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        raise
    print(json.dumps(data, indent=2)[:3000])
    return data


def test_properties(metric_names: List[str]) -> Dict[str, Any]:
    """Fetch properties for a list of metric names."""
    return post_json("/api/kpi/properties", {"metric_names": metric_names})


if __name__ == "__main__":
    # 1) ingest
    # NOTE: this requires Neo4j config to be correct in your backend.
    # If Neo4j is not configured/reachable, this will return a 500/400 error.
    #test_ingest()

    # 2) fetch properties
    test_properties(
        [
            "RevenueGrowthRate",
            "Revenue",
            "GrossMargin",
            "OperatingIncome",
            "SomeMissingMetricName"  # should return null
        ]
    )
