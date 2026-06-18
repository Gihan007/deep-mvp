from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List, Literal
from config import get_config
from neo4j import GraphDatabase
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)
config = get_config()

def _safe_serialize(value: Any):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_safe_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _safe_serialize(v) for k, v in value.items()}
    # Fallback: represent Neo4j objects (Node, Relationship, Path, etc.) as strings
    try:
        return str(value)
    except Exception:
        return None

# Simple truthy helper
def _truthy(v: Optional[str]) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on") if v is not None else False

class CypherRequest(BaseModel):
    query: str = Field(..., description="Cypher query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    mode: Literal["read", "write"] = Field("read", description="Execute in read or write mode")

class CypherResponse(BaseModel):
    records: List[Dict[str, Any]]
    summary: Optional[Dict[str, Any]] = None

class TenKChunkRemoveItems(BaseModel):
    ticker: str
    years: List[int]

class TenKChunkRemoveRequest(BaseModel):
    items: List[TenKChunkRemoveItems]

class RemoveEmptyTenKRequest(BaseModel):
    min_properties: int = Field(6, description="Minimum number of properties (excluding ticker and year) to be considered valid")

    
def _get_driver():
    if not config.NEO4J_URI:
        raise HTTPException(status_code=500, detail="NEO4J_URI is not configured")
    try:
        return GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD))
    except Exception as e:
        logger.exception("Failed to create Neo4j driver")
        raise HTTPException(status_code=500, detail=f"Neo4j connection error: {e}")


def _is_write(query: str) -> bool:
    q = query.strip().lower()
    write_keywords = [
        "create ", "merge ", "set ", "delete ", "detach delete", "remove ",
        "call dbms.", "apoc.create", "apoc.periodic.commit", "apoc.periodic.iterate"
    ]
    return any(k in q for k in write_keywords)





@router.post("/api/graphdb/cypher", response_model=CypherResponse)
def execute_cypher(req: CypherRequest):
    # Basic safety: block write queries unless explicitly allowed
    allow_write_env = _truthy(getattr(config, "ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER", None))
    if (req.mode == "write" or _is_write(req.query)) and not allow_write_env:
        raise HTTPException(
            status_code=403,
            detail="Write queries are disabled. Set ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER=true to enable."
        )

    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(req.query, **(req.parameters or {}))
            # Collect and safely serialize records
            raw_records = [dict(r) for r in result]
            records = [{k: _safe_serialize(v) for k, v in rec.items()} for rec in raw_records]
            # Consume summary for metadata
            summary_obj = result.consume()

            # Safe extraction for server and database fields across neo4j-driver versions
            server_str = None
            try:
                _sv = getattr(summary_obj, "server", None)
                if _sv is not None:
                    server_str = getattr(_sv, "address", _sv if isinstance(_sv, str) else str(_sv))
            except Exception:
                server_str = None

            database_str = None
            try:
                _db = getattr(summary_obj, "database", None)
                if _db is not None:
                    database_str = _db if isinstance(_db, str) else getattr(_db, "name", str(_db))
            except Exception:
                database_str = None
                
            summary = {
                "server": server_str,
                "database": database_str,
                "counters": {
                    "nodes_created": summary_obj.counters.nodes_created,
                    "nodes_deleted": summary_obj.counters.nodes_deleted,
                    "relationships_created": summary_obj.counters.relationships_created,
                    "relationships_deleted": summary_obj.counters.relationships_deleted,
                    "properties_set": summary_obj.counters.properties_set,
                    "labels_added": summary_obj.counters.labels_added,
                    "labels_removed": summary_obj.counters.labels_removed,
                    "indexes_added": summary_obj.counters.indexes_added,
                    "indexes_removed": summary_obj.counters.indexes_removed,
                    "constraints_added": summary_obj.counters.constraints_added,
                    "constraints_removed": summary_obj.counters.constraints_removed,
                    "contains_updates": summary_obj.counters.contains_updates,
                },
            }
            return CypherResponse(records=records, summary=summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cypher execution failed")
        raise HTTPException(status_code=400, detail=f"Cypher execution error: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



# list all sectors endpoint
@router.get("/api/graphdb/sectors", response_model=List[Dict[str, Any]])
def list_sectors():
    """
    List all Sector nodes with their properties.
    """
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (s:Sector)
                RETURN properties(s) AS sector
                ORDER BY sector.sectorName
                """
            )
            return [_safe_serialize(record["sector"]) for record in result]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list sectors")
        raise HTTPException(status_code=400, detail=f"Failed to list sectors: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



# list the Industries when the Sector is given
@router.get("/api/graphdb/industries_when_sector_given", response_model=List[Dict[str, Any]])
def list_industries_by_sector(sectorId: Optional[str] = None, sectorName: Optional[str] = None):
    """
    List Industry nodes that belong to the given Sector.
    Provide either sectorId or sectorName (case-insensitive exact match).
    """
    if not sectorId and not sectorName:
        raise HTTPException(status_code=400, detail="Provide either sectorId or sectorName")

    driver = _get_driver()
    try:
        with driver.session() as session:
            if sectorId:
                cypher = """
                    MATCH (s:Sector {sectorId: $sectorId})<-[:BELONG_TO]-(i:Industry)
                    RETURN properties(i) AS industry
                    ORDER BY industry.industryName
                """
                params = {"sectorId": sectorId}
            else:
                cypher = """
                    MATCH (s:Sector)<-[:BELONG_TO]-(i:Industry)
                    WHERE toLower(s.sectorName) = toLower($sectorName)
                    RETURN properties(i) AS industry
                    ORDER BY industry.industryName
                """
                params = {"sectorName": sectorName}

            result = session.run(cypher, **params)
            return [_safe_serialize(r["industry"]) for r in result]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list industries by sector")
        raise HTTPException(status_code=400, detail=f"Failed to list industries by sector: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



# endpoint for list the Companies when the Industry is given 
@router.get("/api/graphdb/companies_when_industry_given", response_model=List[Dict[str, Any]])
def list_companies_by_industry(industryId: Optional[str] = None, industryName: Optional[str] = None):
    """
    List Company nodes that belong to the given Industry.
    Provide either industryId or industryName (case-insensitive exact match).
    """
    if not industryId and not industryName:
        raise HTTPException(status_code=400, detail="Provide either industryId or industryName")

    driver = _get_driver()
    try:
        with driver.session() as session:
            if industryId:
                cypher = """
                    MATCH (i:Industry {industryId: $industryId})<-[:BELONG_TO]-(c:Company)
                    RETURN properties(c) AS company
                    ORDER BY company.companyName
                """
                params = {"industryId": industryId}
            else:
                cypher = """
                    MATCH (i:Industry)<-[:BELONG_TO]-(c:Company)
                    WHERE toLower(i.industryName) = toLower($industryName)
                    RETURN properties(c) AS company
                    ORDER BY company.companyName
                """
                params = {"industryName": industryName}

            result = session.run(cypher, **params)
            return [_safe_serialize(r["company"]) for r in result]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list companies by industry")
        raise HTTPException(status_code=400, detail=f"Failed to list companies by industry: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass




# endpoint for list the Companies when the Sector is given 
@router.get("/api/graphdb/companies_when_sector_given", response_model=List[Dict[str, Any]])
def list_companies_by_sector(sectorId: Optional[str] = None, sectorName: Optional[str] = None):
    """
    List Company nodes that belong to the given Sector (via Industry).
    Provide either sectorId or sectorName (case-insensitive exact match).
    """
    if not sectorId and not sectorName:
        raise HTTPException(status_code=400, detail="Provide either sectorId or sectorName")

    driver = _get_driver()
    try:
        with driver.session() as session:
            if sectorId:
                cypher = """
                    MATCH (s:Sector {sectorId: $sectorId})<-[:BELONG_TO]-(i:Industry)<-[:BELONG_TO]-(c:Company)
                    WITH DISTINCT c
                    RETURN properties(c) AS company
                    ORDER BY company.companyName
                """
                params = {"sectorId": sectorId}
            else:
                cypher = """
                    MATCH (s:Sector)<-[:BELONG_TO]-(i:Industry)<-[:BELONG_TO]-(c:Company)
                    WHERE toLower(s.sectorName) = toLower($sectorName)
                    WITH DISTINCT c
                    RETURN properties(c) AS company
                    ORDER BY company.companyName
                """
                params = {"sectorName": sectorName}

            result = session.run(cypher, **params)
            return [_safe_serialize(r["company"]) for r in result]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list companies by sector")
        raise HTTPException(status_code=400, detail=f"Failed to list companies by sector: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


# list all Companies endpoint
@router.get("/api/graphdb/companies", response_model=List[Dict[str, Any]])
def list_companies():
    """
    List all Company nodes with their properties.
    """
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (c:Company)
                WHERE c.ticker IS NOT NULL
                RETURN properties(c) AS company
                ORDER BY company.companyName
                """
            )
            return [_safe_serialize(record["company"]) for record in result]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list companies")
        raise HTTPException(status_code=400, detail=f"Failed to list companies: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass




@router.delete("/api/graphdb/remove/company_nodes")
def remove_company_nodes():
    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run("MATCH (n:Company) DETACH DELETE n")
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "Company nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove company nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove company nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass

@router.delete("/api/graphdb/remove/metric_nodes")
def remove_metric_nodes():
    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run("MATCH (n:Metric) DETACH DELETE n")
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "Metric nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove metric nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove metric nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass



@router.delete("/api/graphdb/remove/industry_nodes")
def remove_industry_nodes():
    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run("MATCH (n:Industry) DETACH DELETE n")
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "Industry nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove industry nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove industry nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass

@router.delete("/api/graphdb/remove/sector_nodes")
def remove_sector_nodes():
    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run("MATCH (n:Sector) DETACH DELETE n")
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "Sector nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove sector nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove sector nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass

@router.delete("/api/graphdb/remove/tenkchunk_nodes")
def remove_tenkchunk_nodes():
    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run("MATCH (n:TenKChunk) DETACH DELETE n")
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "TenKChunk nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove TenKChunk nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove TenKChunk nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass

@router.delete("/api/graphdb/remove/predicted_metric_nodes")
def remove_predicted_metric_nodes():
    driver = _get_driver()
    try:
        with driver.session() as session:
            res = session.run("MATCH (n:PredictedMetric) DETACH DELETE n")
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "PredictedMetric nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove PredictedMetric nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove PredictedMetric nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass

@router.delete("/api/graphdb/remove/tenkchunk_nodes_by_ticker_years")
def remove_tenkchunk_nodes_by_ticker_years(req: TenKChunkRemoveRequest):
    driver = _get_driver()
    try:
        pairs: List[Dict[str, Any]] = []
        for item in req.items:
            # ensure years ints
            years = [int(y) for y in item.years]
            pairs.append({"ticker": item.ticker, "years": years})
        with driver.session() as session:
            cypher = (
                "UNWIND $pairs AS p "
                "MATCH (t:TenKChunk {ticker: p.ticker}) "
                "WHERE t.year IN p.years "
                "DETACH DELETE t"
            )
            res = session.run(cypher, pairs=pairs)
            summary = res.consume()
            deleted = summary.counters.nodes_deleted
            return {"message": "Specific TenKChunk nodes removed", "nodes_deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove specific TenKChunk nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove specific TenKChunk nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.delete("/api/graphdb/remove/tenkchunk_empty_nodes")
def remove_empty_tenkchunk_nodes(payload: RemoveEmptyTenKRequest = RemoveEmptyTenKRequest()):
    """
    Remove TenKChunk nodes where the number of properties excluding ticker and year is less than min_properties.
    Returns deleted count and remaining valid TenKChunk node count.
    """
    driver = _get_driver()
    try:
        with driver.session() as session:
            # Count how many will be deleted, then delete
            count_query = (
                "MATCH (chunk:TenKChunk) "
                "WITH chunk, size([k IN keys(chunk) WHERE k <> 'ticker' AND k <> 'year']) AS prop_count "
                "WHERE prop_count < $minProps "
                "RETURN count(chunk) AS to_delete"
            )
            res_count = session.run(count_query, minProps=payload.min_properties)
            to_delete = res_count.single()["to_delete"] if res_count.peek() is not None else 0

            delete_query = (
                "MATCH (chunk:TenKChunk) "
                "WITH chunk, size([k IN keys(chunk) WHERE k <> 'ticker' AND k <> 'year']) AS prop_count "
                "WHERE prop_count < $minProps "
                "WITH collect(id(chunk)) AS ids "
                "MATCH (c) WHERE id(c) IN ids "
                "DETACH DELETE c"
            )
            res_del = session.run(delete_query, minProps=payload.min_properties)
            _ = res_del.consume()

            # Remaining valid count
            valid_query = (
                "MATCH (chunk:TenKChunk) "
                "WITH size([k IN keys(chunk) WHERE k <> 'ticker' AND k <> 'year']) AS prop_count "
                "WHERE prop_count >= $minProps "
                "RETURN count(*) AS valid_count"
            )
            res_valid = session.run(valid_query, minProps=payload.min_properties)
            valid_count = res_valid.single()["valid_count"] if res_valid.peek() is not None else 0

            return {
                "message": "Removed empty TenKChunk nodes",
                "deleted_count": int(to_delete),
                "valid_tenkchunk_count": int(valid_count),
                "min_properties": payload.min_properties,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove empty TenKChunk nodes")
        raise HTTPException(status_code=400, detail=f"Failed to remove empty TenKChunk nodes: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass


@router.get("/api/graphdb/node_counts", response_model=List[Dict[str, Any]])
def get_node_counts():
    """
    Return counts for each distinct node label as a list of objects:
    [{"node_name": "Company", "count": 10}, ...]
    """
    driver = _get_driver()
    try:
        with driver.session() as session:
            cypher = (
                "MATCH (n) "
                "UNWIND labels(n) AS label "
                "RETURN label AS node_name, count(*) AS count "
                "ORDER BY node_name"
            )
            result = session.run(cypher)
            return [
                {"node_name": r["node_name"], "count": int(r["count"])}
                for r in result
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get node counts")
        raise HTTPException(status_code=400, detail=f"Failed to get node counts: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass
