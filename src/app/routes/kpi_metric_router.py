from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

from config import get_config


router = APIRouter()
logger = logging.getLogger(__name__)
config = get_config()


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


def _truthy_kpi(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v)
    s = s.strip()
    return s if s else None


def _read_kpi_excel(path: str) -> pd.DataFrame:
    """Read all sheets and concatenate.

    Expected columns (case-insensitive best-effort):
      Parameter, KPI, Category, Definition, Trend Scenarios, VInvest Action
    """
    try:
        xl = pd.ExcelFile(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"KPI Excel file not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to open KPI Excel file: {e}")

    frames: List[pd.DataFrame] = []
    for sh in xl.sheet_names:
        try:
            df = xl.parse(sh)
            if df is None or df.empty:
                continue
            df["__sheet__"] = sh
            frames.append(df)
        except Exception as e:
            logger.warning("Skipping sheet '%s' due to parse error: %s", sh, e)

    if not frames:
        raise HTTPException(status_code=400, detail="No readable sheets found in KPI Excel file")

    out = pd.concat(frames, ignore_index=True)
    return out


def _read_kpi_excel_bytes(content: bytes) -> pd.DataFrame:
    """Read an uploaded xlsx file from bytes, all sheets concatenated."""
    try:
        xl = pd.ExcelFile(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to open uploaded KPI Excel file: {e}")

    frames: List[pd.DataFrame] = []
    for sh in xl.sheet_names:
        try:
            df = xl.parse(sh)
            if df is None or df.empty:
                continue
            df["__sheet__"] = sh
            frames.append(df)
        except Exception as e:
            logger.warning("Skipping sheet '%s' due to parse error: %s", sh, e)

    if not frames:
        raise HTTPException(status_code=400, detail="No readable sheets found in uploaded KPI Excel file")

    return pd.concat(frames, ignore_index=True)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize column names so we can tolerate minor changes/case.
    col_map = {}
    for c in df.columns:
        key = str(c).strip().lower()
        col_map[key] = c

    def _get_col(*candidates: str) -> Optional[str]:
        for cand in candidates:
            k = cand.strip().lower()
            if k in col_map:
                return col_map[k]
        return None

    param_col = _get_col("parameter", "metric", "metricname", "metric_name")
    if not param_col:
        raise HTTPException(status_code=400, detail="Excel is missing required column: 'Parameter'")

    kpi_col = _get_col("kpi", "is_kpi", "iskpi")
    category_col = _get_col("category")
    definition_col = _get_col("definition", "definetion")
    trend_col = _get_col("trend scenarios", "trend_scenarios", "trend")
    action_col = _get_col("vinvest action", "vinvest_action", "action")
    sheet_col = _get_col("__sheet__")

    norm = pd.DataFrame()
    norm["metricName"] = df[param_col]
    if kpi_col:
        norm["is_kpi"] = df[kpi_col]
    else:
        norm["is_kpi"] = None

    norm["category"] = df[category_col] if category_col else None
    norm["definition"] = df[definition_col] if definition_col else None
    norm["trend_scenarios"] = df[trend_col] if trend_col else None
    norm["vInvest_action"] = df[action_col] if action_col else None
    norm["source_sheet"] = df[sheet_col] if sheet_col else None

    return norm


class KPIIngestResponse(BaseModel):
    status: str
    ingested: int
    skipped: int
    updated: int
    created: int
    file_name: str


class KPIPropsRequest(BaseModel):
    metric_names: List[str] = Field(..., description="Metric names (Parameter) to query")


class KPIPropsOut(BaseModel):
    metricName: str
    is_kpi: Optional[bool] = None
    category: Optional[str] = None
    definition: Optional[str] = None
    trend_scenarios: Optional[str] = None
    vInvest_action: Optional[str] = None


@router.post("/api/kpi/ingest", response_model=KPIIngestResponse)
def ingest_kpi_metrics_to_neo4j(file: UploadFile = File(...)):
    """Read KPI definitions from the Excel and MERGE them into Neo4j.

    Creates one node per metric:
      (:KPI_metric {metricName})
    and sets properties:
      is_kpi, category, definition, trend_scenarios, vInvest_action

    Re-running this endpoint will UPDATE existing nodes (MERGE + SET +=).
    """

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid file type (only .xlsx allowed)")

    try:
        try:
            file.file.seek(0)
        except Exception:
            pass
        content = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    df_raw = _read_kpi_excel_bytes(content)
    df = _normalize_columns(df_raw)

    batch: List[Dict[str, Any]] = []
    skipped = 0
    for _, row in df.iterrows():
        metric_name = _safe_str(row.get("metricName"))
        if not metric_name:
            skipped += 1
            continue

        props = {
            "metricName": metric_name,
            "is_kpi": _truthy_kpi(row.get("is_kpi")),
            "category": _safe_str(row.get("category")),
            "definition": _safe_str(row.get("definition")),
            "trend_scenarios": _safe_str(row.get("trend_scenarios")),
            "vInvest_action": _safe_str(row.get("vInvest_action")),
            "source_sheet": _safe_str(row.get("source_sheet")),
        }
        batch.append({"metricName": metric_name, "props": props})

    if not batch:
        raise HTTPException(status_code=400, detail="No KPI metrics found to ingest")

    driver = _get_driver()
    try:
        with driver.session() as session:
            # Use MERGE to avoid duplicates; SET += to update/add properties.
            # We also count created vs matched using apoc? (not guaranteed available)
            # We'll return Neo4j summary counters instead.
            result = session.run(
                """
                UNWIND $batch AS item
                MERGE (k:KPI_metric {metricName: item.metricName})
                SET k += item.props
                """,
                batch=batch,
            )
            summary = result.consume()

            return KPIIngestResponse(
                status="success",
                ingested=len(batch),
                skipped=skipped,
                created=int(summary.counters.nodes_created or 0),
                updated=int(summary.counters.properties_set or 0),
                file_name=file.filename,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to ingest KPI metrics")
        raise HTTPException(status_code=400, detail=f"Failed to ingest KPI metrics: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.post("/api/kpi/properties", response_model=Dict[str, Optional[KPIPropsOut]])
def get_kpi_properties(req: KPIPropsRequest):
    """Return KPI properties for the given metric names.

    Input: {"metric_names": ["Revenue", "GrossMargin", ...]}
    Output: {"Revenue": {...}, "GrossMargin": {...}, "MissingOne": null}
    """

    names = [str(n).strip() for n in (req.metric_names or []) if str(n).strip()]
    # de-dupe preserving order
    seen = set()
    names_unique: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            names_unique.append(n)

    if not names_unique:
        raise HTTPException(status_code=422, detail="metric_names must contain at least one metric name")

    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run(
                """
                UNWIND $names AS name
                OPTIONAL MATCH (k:KPI_metric {metricName: name})
                RETURN name AS inputName, properties(k) AS props
                """,
                names=names_unique,
            )

            out: Dict[str, Optional[KPIPropsOut]] = {}
            for r in res:
                input_name = str(r.get("inputName"))
                props = r.get("props")
                if not props:
                    out[input_name] = None
                    continue

                out[input_name] = KPIPropsOut(
                    metricName=str(props.get("metricName") or input_name),
                    is_kpi=props.get("is_kpi"),
                    category=props.get("category"),
                    definition=props.get("definition"),
                    trend_scenarios=props.get("trend_scenarios"),
                    vInvest_action=props.get("vInvest_action"),
                )
            return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch KPI properties")
        raise HTTPException(status_code=400, detail=f"Failed to fetch KPI properties: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass