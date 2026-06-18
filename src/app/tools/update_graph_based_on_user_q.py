"""
Graph Database Update Tool - Modify Neo4j data based on user requests
"""

from langchain.tools import tool
import logging
from app.utills.tool_output_collector import add_tool_output
from langchain_neo4j import Neo4jGraph
from config import get_config

config = get_config()
logger = logging.getLogger(__name__)

tool_outputs= {}

neo4j_graph = Neo4jGraph(
    url=config.NEO4J_URI,
    username=config.NEO4J_USERNAME,
    password=config.NEO4J_PASSWORD
)


@tool
def update_graph_based_on_user_q(query: str, user_approved_update: bool = False) -> str:
    """
    Execute Cypher queries on Neo4j - handles BOTH read and write operations.
    
    For READ queries (MATCH...RETURN): Executes immediately
    For WRITE queries (SET/CREATE/DELETE): Requires user_approved_update=True
    
    Args:
        query (str): The Cypher query (read or write)
        user_approved_update (bool): Must be True for write operations
        
    Returns:
        str: Query results or confirmation message
    """
    logger.info(">>>>>>>>>>> Executing update_graph_based_on_user_q")
    logger.info(f"Query: {query}")
    
    query_upper = query.upper()
    write_operations = ['CREATE', 'MERGE', 'SET', 'DELETE', 'REMOVE']
    is_write_query = any(op in query_upper for op in write_operations)
    
    # SAFETY CHECK for write operations
    if is_write_query:
        logger.info("🔍 WRITE operation detected - Checking approval")
        logger.info(f"   user_approved_update: {user_approved_update}")
        
        if not user_approved_update:
            logger.warning("   ⏸️ BLOCKED - No approval yet")
            return (
                "⚠️ This is a WRITE operation that requires confirmation.\n\n"
                "FIRST INTERACTION - You must:\n"
                "1. Use a READ query (MATCH...RETURN) to check the current value\n"
                "2. Show user what will change\n"
                "3. Ask: 'Do you want me to proceed?'\n"
                "4. STOP and wait for user confirmation\n\n"
                "SECOND INTERACTION - After user says 'yes':\n"
                "5. Call this tool again with the WRITE query and user_approved_update=True"
            )
        
        logger.info("   ✅ Approval confirmed - Executing write")
    

    
    # Execute query
    try:
        if not neo4j_graph:
            return "Error: Neo4j graph not initialized"
        
        result = neo4j_graph.query(query)
        logger.info(f"Query executed successfully. Is write: {is_write_query}")
        
        # Format response
        if result:
            tool_outputs={'tool_name':"update_graph_based_on_user_q" ,
                        'input_arguments': {'query': query, 'user_approved_update': user_approved_update},
                        'tool_output': f"Query result: {str(result)}"
                        }
            try:
                add_tool_output(tool_outputs)
            except Exception:
                pass
            return f"Query result: {str(result)}"
        else:
            return "Query executed successfully. No results returned." if is_write_query else "No data found."
    
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return error_msg
