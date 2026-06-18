"""
Cypher Query Tool - Direct Neo4j Graph Database queries (READ ONLY)
"""

from langchain.tools import tool
import logging
from app.utills.tool_output_collector import add_tool_output
from langchain_neo4j import Neo4jGraph
from config import get_config
config = get_config()

logger = logging.getLogger(__name__)
tool_outputs = {}

neo4j_graph = Neo4jGraph(
    url=config.NEO4J_URI,
    username=config.NEO4J_USERNAME,
    password=config.NEO4J_PASSWORD
)

FORBIDDEN_KEYWORDS = [
    "CREATE ", "MERGE ", "SET ", "DELETE ", "REMOVE ", "DROP ", "CALL DB."
]


@tool
def graph_db_strctured_data_cypher_query_tool(query: str) -> str:
    """
    Execute a raw READ-ONLY Cypher query for structured data.
    """

    logger.info(">>>>>>>>>>> Executing Structured GraphDB Query Tool")
    logger.info(f"Query: {query}")

    # Read-only enforcement
    upper_q = query.upper()
    if any(k in upper_q for k in FORBIDDEN_KEYWORDS):
        return "Error: Write operations are not allowed. This tool is READ-ONLY."

    try:
        if not neo4j_graph:
            return "Error: Neo4j graph not initialized."

        result = neo4j_graph.query(query)

        if not result:
            return "No results found."

        tool_outputs = {
            "tool_name": "graph_db_strctured_data_cypher_query_tool",
            "input_arguments": {"query": query},
            "tool_output": str(result)
        }

        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass

        return str(result)

    except Exception as e:
        msg = f"Error executing Cypher query: {str(e)}"
        logger.error(msg)
        return msg
