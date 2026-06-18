"""
Chroma Retrieval Tool - Document retrieval and QA
"""

from langchain.tools import tool
from langchain.chains import RetrievalQA
from langchain.chains.retrieval_qa.base import RetrievalQA
import logging
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

tool_outputs= {}

# Global dependencies
chromadb_vector_store = None
llm = None


def set_dependencies(**kwargs):
    """Set tool dependencies"""
    global chromadb_vector_store, llm
    chromadb_vector_store = kwargs.get('chromadb_vector_store')
    llm = kwargs.get('llm')


@tool
def chroma_retrieval_tool(question: str) -> str:
    """
    Answers questions using Retrieval-based Question Answering system.
    
    Args:
        question (str): Question to be answered
        
    Returns:
        str: Answer from documents or error message
    """
    logger.info("Executing chroma_retrieval_tool")
    logger.info(f"Question={question}")
    try:
        if not chromadb_vector_store or not llm:
            return "Error: Vector store or LLM not initialized. Please call set_dependencies first."
            
        #print("\n>>>>>>>>>>> chroma_retrieval_tool calling ...")
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=chromadb_vector_store.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True
        )
        results = qa_chain({"query": question})
        logger.info("Chroma retrieval successful")
        tool_outputs={'tool_name':"chroma_retrieval_tool" ,
                    'input_arguments': {'question': question},
                    'tool_output': str(results)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return results
    
    except Exception as e:
        error_msg = f"Error executing retrieval query: {str(e)}"
        logger.error(error_msg)
        return error_msg





# ============================================================================
# USAGE EXAMPLES:

# Example 1: Import individual tools
# from utills.tools import cypher_query_tool
# from utills.tools import vector_search_tool
# from utills.tools import calculator_tool
# from utills.tools import visualization_tool

# Example 2: Import by category
# from utills.tools import get_tools_by_category
# search_tools = get_tools_by_category('search')
# db_tools = get_tools_by_category('database')

# Example 3: Initialize and use
# from utills.tools import initialize_all_tools
# tools = initialize_all_tools(vector_store, llm, config)

# Example 4: Use individual tool after initialization
# from utills.tools.tool_initializer import ToolInitializer
# initializer = ToolInitializer(vector_store, llm, config)
# initializer.initialize_all()
# 
# from utills.tools import cypher_query_tool
# result = cypher_query_tool("What companies are in the tech sector?")
