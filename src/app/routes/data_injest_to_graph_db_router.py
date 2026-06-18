from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
import pandas as pd
import PyPDF2
import requests
from bs4 import BeautifulSoup
from neo4j import GraphDatabase
import uuid
from datetime import datetime
import os
import tempfile
import io
import traceback
from typing import List, Optional, Dict, Any, Union
from config import get_config
from app.utills.inteligent_pdf_data_extractor import pdf_data_extract
from app.data_injestor.graphDB_builder_with_structured_data import process_structured_csv_files
from app.data_injestor.graphDB_builder_with_metric_structured_data import store_structured_metric_data
from app.data_injestor.graphDB_builder_with_unstructured_data import tenK_data_injestor, create_all_company_tenk_relationships
import asyncio
from typing import List
import os, tempfile, traceback, logging
import csv
from io import StringIO
import uuid
import os
from datetime import date
# --------------------------------------------------------------------------
# Configuration & Logging
# --------------------------------------------------------------------------

config = get_config()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
NEO4J_TEXT_NODE_PROPERTY = config.NEO4J_TEXT_NODE_PROPERTY

# --------------------------------------------------------------------------
# Pydantic Models
# --------------------------------------------------------------------------

class WebpagesRequest(BaseModel):
    urls: List[str]
class ProcessingResponse(BaseModel):
    message: str
    success_files: Optional[List[str]] = None
    failed_files: Optional[List[str]] = None
    success_urls: Optional[List[str]] = None
    failed_urls: Optional[List[str]] = None
    token_usage: Optional[List[Dict[str, Any]]] = None






# -----------------------------------------------------------------------------------------
# ---------------------------- UnStructured 10K Data Ingestion ----------------------------

@router.post("/api/data_inject_graph_db/csv_unstructured")
async def data_inject_csv_unstructured(file: UploadFile = File(...)):

    
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Invalid file type (only TXT allowed)")

    # Keep the filename format: TICKER_YEAR.txt (spaces removed)
    safe_filename = file.filename.replace(" ", "")
    logger.info(f"Processing unstructured file: {safe_filename}")
    temp_path = None  # 👈 Initialize before try
    try:
        # Read content
        content = await file.read()
        # Check empty file
        if not content.strip():
            raise HTTPException(status_code=400, detail="File is empty")

        # Validate TXT structure: at least one non-empty line
        try:
            decoded = content.decode("utf-8", errors="ignore")
            lines = [ln.strip() for ln in decoded.splitlines() if ln.strip() != ""]
            if not lines:
                raise HTTPException(status_code=400, detail="TXT contains no non-empty lines")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid TXT structure ({str(e)})")

        # Save to temporary file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, safe_filename)
        with open(temp_path, "wb") as tmp_file:
            tmp_file.write(content)
        logger.info(f"Temporary file saved at: {temp_path}")

        # Process file
        response = await tenK_data_injestor(temp_path)
        os.remove(temp_path)

        
        return JSONResponse(status_code=response["http_status"], content=response)

    except Exception as e:
        # ⚠️ Developer-side / backend logic error
        logging.error("Traceback:\n%s", traceback.format_exc())
        return JSONResponse(status_code=400,content={"detail": f"Internal server error: {str(e)}"})







# ------------------------------------------------------------------------------------------------------------
# --------------------------- Structured Company Industry sector  Data Ingestion -------------------------------

@router.post("/api/data_inject_graph_db/csv_structured_company_industry_sector_data")
def data_inject_csv_structured_company_industry_sector_data(
    files: Optional[List[UploadFile]] = File(None),
    keys: Optional[List[str]] = Form(None)
):
    try:
        errors = {}
        
        # Validation: missing files/keys
        if not files and not keys:
            errors["file"] = "No files uploaded"
            errors["key"] = "No keys provided"
            return JSONResponse(status_code=400, content={"detail": errors})

        if not files and keys:
            errors["file"] = "No files uploaded"
            errors["key"] = "Keys provided"
            return JSONResponse(status_code=400, content={"detail": errors})

        if files and not keys:
            errors["file"] = "Files uploaded"
            errors["key"] = "No keys provided"
            return JSONResponse(status_code=400, content={"detail": errors})

        if len(keys) != len(files):
            errors["file"] = f"{len(files)} file(s) uploaded"
            errors["key"] = f"{len(keys)} key(s) provided — must match file count"
            return JSONResponse(status_code=400, content={"detail": errors})

        # ✅ All good — call processing function
        result = process_structured_csv_files(files, keys)

        return JSONResponse(status_code=result["http_status"], content=result)

    except Exception as e:
        # ⚠️ Developer-side / backend logic error
        logging.error("Traceback:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=400,
            content={"detail": f"Internal server error: {str(e)}"}
        )






# --------------------------------------------------------------------------
# -------------------- Structured Metrics Data Ingestion -------------------

# New structured metric CSV types
valid_keys = {
    "3StatementModel",
    "FreeCashFlows",
    "ReportedFinancials",
    "InvestedCapital",
    "Performance",
    "HistoricalCagrAvg",
    "ExtractedItems",
    "ValuationForecastDriverValues",
    "ValuationSummary",
    "MultiplesTable",
}

@router.post("/api/data_inject_graph_db/csv_structured_metrics_data")
def data_inject_csv_structured_metrics_data(
    file: UploadFile = File(...),
    key: str = Form(...),
    ticker: str = Form(...)
):
    errors = {}
    currentyear= date.today().year

    # -------------------------
    # Validate ticker
    # -------------------------
    if not ticker or ticker.strip() == "":
        errors["ticker"] = "Ticker symbol is required"
    elif not ticker.strip().isalpha():
        errors["ticker"] = "Ticker symbol must contain only letters (A–Z or a–z)"

    # -------------------------
    # Validate year
    # -------------------------
    if currentyear is not None:
        if not (2000 <= currentyear <= 2050):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": [f"Invalid CurrentYear value: {currentyear}. Must be between 2000–2050."],
                    "http_status": 400
                }
            )
    # -------------------------
    # Validate key
    # -------------------------
    if key not in valid_keys:
        errors["invalid_key"] = (
            f"Invalid key: {key}. Allowed keys: {', '.join(sorted(valid_keys))}"
        )

    # -------------------------
    # Validate file extension
    # -------------------------
    if not file.filename.lower().endswith(".csv"):
        errors["invalid_file"] = f"Only .csv files are allowed. Invalid file: {file.filename}"

    # -------------------------
    # If errors → return
    # -------------------------
    if errors:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": list(errors.values()),
                "http_status": 400
            }
        )

    # -------------------------
    # Process file
    # -------------------------
    try:
        # Sync endpoint: read from underlying file object.
        try:
            file.file.seek(0)
        except Exception:
            pass
        content = file.file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            temp_path = tmp.name

        response = store_structured_metric_data(temp_path, key, ticker)
        os.remove(temp_path)
        # IMPORTANT: return the real backend response + status code, so clients can see failures.
        return JSONResponse(status_code=response.get("http_status", 500), content=response)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": [f"Error: {e}"],
                "http_status": 500
            }
        )








# ---------------------- Create Relationships ------------------------------
# --------------------------------------------------------------------------

@router.post("/api/data_inject_graph_db/create_all_company_tenk_relationships")
def create_all_company_tenk_relationships_route():
    """
    Create HAS_TENK_DATA relationships for ALL matching Company and TenKChunk nodes.
    No inputs required; ticker matches are used to link nodes.
    """
    try:
        result = create_all_company_tenk_relationships()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message", "Failed to create relationships"))
        return JSONResponse(status_code=200, content={
            "message": "HAS_TENK_DATA relationships created for all matching Company and TenKChunk nodes",
            "summary": result
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating HAS_TENK_DATA for all companies:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
