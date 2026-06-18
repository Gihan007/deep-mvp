"""Compare expected metric names vs. metric names present in Neo4j.

Reads expected metric names from:
  src/app/routes/distinct_metric_names_excluding_6_7.txt

Fetches actual metric names from Neo4j:
  MATCH (m:Metric) RETURN DISTINCT m.metricName

Outputs:
  - counts
  - missing (expected but not in Neo4j)
  - extra (in Neo4j but not expected)
  - writes missing/extra lists to txt files next to the expected list

Usage:
  python3 scripts/compare_expected_metrics_with_neo4j.py

Neo4j connection is configured via the same environment variables used by the app:
  NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Set, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase


EXPECTED_PATH = Path("src/app/routes/distinct_metric_names_excluding_6_7.txt")


def _repo_root() -> Path:
    # scripts/compare_expected_metrics_with_neo4j.py -> repo root is one level up from scripts/
    return Path(__file__).resolve().parents[1]


def _resolve_path(p: Path) -> Path:
    # Allow running from any working directory.
    root = _repo_root()
    return p if p.is_absolute() else (root / p)


def _load_neo4j_env() -> Tuple[str, str, str]:
    """Load Neo4j connection settings from environment / .env.

    We intentionally don't import the app's config module here, so this script can be
    run directly from anywhere (repo root, scripts folder, etc.).
    """
    root = _repo_root()
    load_dotenv(root / ".env")

    uri = os.environ.get("NEO4J_URI", "").strip()
    username = os.environ.get("NEO4J_USERNAME", "neo4j").strip()
    password = os.environ.get("NEO4J_PASSWORD", "").strip()

    if not uri:
        raise RuntimeError(
            "NEO4J_URI is not configured. Set NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD in your environment or .env"
        )
    return uri, username, password


def _load_expected_metrics(path: Path) -> Set[str]:
    path = _resolve_path(path)
    if not path.exists():
        raise FileNotFoundError(f"Expected metrics file not found: {path}")
    out: Set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        name = line.strip()
        if name:
            out.add(name)
    return out


def _fetch_metric_names_from_neo4j() -> Set[str]:
    uri, username, password = _load_neo4j_env()

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        with driver.session() as session:
            res = session.run(
                """
                MATCH (m:Metric)
                WHERE m.metricName IS NOT NULL AND trim(toString(m.metricName)) <> ""
                RETURN DISTINCT toString(m.metricName) AS metricName
                """
            )
            names = {record["metricName"].strip() for record in res}
            return {n for n in names if n}
    finally:
        driver.close()


def _write_list(path: Path, items: Iterable[str]) -> None:
    items = list(items)
    path.write_text("\n".join(items) + ("\n" if items else ""), encoding="utf-8")


def main() -> None:
    expected = _load_expected_metrics(EXPECTED_PATH)
    actual = _fetch_metric_names_from_neo4j()

    missing = sorted(expected - actual, key=str.lower)
    extra = sorted(actual - expected, key=str.lower)

    expected_abs = _resolve_path(EXPECTED_PATH)
    missing_path = expected_abs.with_name("missing_metrics_in_neo4j.txt")
    extra_path = expected_abs.with_name("extra_metrics_in_neo4j.txt")

    _write_list(missing_path, missing)
    _write_list(extra_path, extra)

    print(f"Expected metrics file: {expected_abs}")
    print(f"Expected distinct count: {len(expected)}")
    print(f"Neo4j distinct Metric.metricName count: {len(actual)}")
    print(f"Missing metrics (expected but not in Neo4j): {len(missing)}")
    print(f"Extra metrics (in Neo4j but not expected): {len(extra)}")
    print("---")
    print(f"Wrote missing list to: {missing_path}")
    print(f"Wrote extra list to:   {extra_path}")


if __name__ == "__main__":
    main()
