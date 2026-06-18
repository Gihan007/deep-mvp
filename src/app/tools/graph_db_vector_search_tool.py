"""
Vector Search Tool - Similarity search on vector store
"""

from langchain.tools import tool
import logging
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

tool_outputs= {}

# Global dependencies
graphdb_vector_store = None


def set_dependencies(**kwargs):
    """Set tool dependencies"""
    global graphdb_vector_store
    graphdb_vector_store = kwargs.get('graphdb_vector_store')


@tool
def graph_db_vector_search_tool(question: str, k: int = 5) -> str:
    """
    Perform vector similarity search on Chunks Nodes.
    Use this for finding relevant information from Chunk Nodes. which includes financial data
    
    Args:
        question (str): Search query
        k (int): Number of results to return
        
    Returns:
        str: Similar documents or error message
    """
    logger.info("Executing graph_db_vector_search_tool")
    logger.info(f"Question={question}, k={k}")
    try:
        if not graphdb_vector_store:
            return "Error: Vector store not initialized. Please call set_dependencies first."
            
        #print("\n>>>>>>>>>>> vector_search_tool calling ...")
        similar_docs = graphdb_vector_store.similarity_search(question, k=k)
        logger.info("Vector search successful")
        tool_outputs={'tool_name':"graph_db_vector_search_tool" ,
                    'input_arguments': {'question': question, 'k': k},
                    'tool_output': str(similar_docs)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return similar_docs
    except Exception as e:
        error_msg = f"Error performing vector search: {str(e)}"
        logger.error(error_msg)
        return error_msg
