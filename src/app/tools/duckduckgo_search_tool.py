"""
DuckDuckGo Search Tool - Free web search
"""

from langchain.tools import tool
from ddgs import DDGS
import logging
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

tool_outputs= {}

# No dependencies needed for DuckDuckGo
def set_dependencies(**kwargs):
    """DuckDuckGo doesn't need dependencies"""
    pass


@tool
def duckduckgo_search_tool(query: str, max_results: int = 5) -> str:
    """
    DuckDuckGo web search tool - completely free, no API key required.
    Args:
        query (str): Search query
        max_results (int): Maximum results to return
    Returns:
        str: Search results or error message
    """
    logger.info(">>>>>>>>>>>  Executing DuckDuckGo search")
    #logger.info(f"Query={query}, max_results={max_results}")
    try:
        #print("\n>>>>>>>>>>> duckduckgo_search_tool calling ...")
        #print("")
        #print("Generated_query: ", query)
        #print("")
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=max_results))

            if not search_results:
                logger.info("No search results found.")
                return "No search results found."

            results = [f"Web Search Results for: {query}\n"]

            for i, result in enumerate(search_results, 1):
                results.append(f"""
                {i}. {result.get('title', 'No title')}
                URL: {result.get('href', 'No URL')}
                Content: {result.get('body', 'No content available')[:400]}...
                """)
            
            #print("Results: ", results)
            logger.info("DuckDuckGo search successful")
            tool_outputs={'tool_name':"duckduckgo_search_tool" ,
                        'input_arguments': {'query': query, 'max_results': max_results},
                        'tool_output': "\n".join(results)
                        }
            try:
                add_tool_output(tool_outputs)
            except Exception:
                pass
            return "\n".join(results)

    except Exception as e:
        error_msg = f"Error performing DuckDuckGo web search: {str(e)}"
        logger.error(error_msg)
        #print("Exception occured ...")
        return error_msg
