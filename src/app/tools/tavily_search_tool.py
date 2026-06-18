"""
Tavily Search Tool - Real-time web search (self-initializing)
"""

import os
from typing import Optional, List
from langchain.tools import tool
import logging
from app.utills.tool_output_collector import add_tool_output
from tavily import TavilyClient
from config import get_config
config = get_config()

logger = logging.getLogger(__name__)

tool_outputs= {}


# Global dependencies
tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)



@tool
def tavily_search_tool(
    query: str,
    max_results: int = 5,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
) -> str:
    """
    Tavily Search Tool - Performs real-time web search using the Tavily API.

    Args:
        query (str): Search query
        max_results (int): Maximum results to return
        include_domains (List[str], optional): Domains to prioritize
        exclude_domains (List[str], optional): Domains to exclude

    Returns:
        str: Search results or error message
    """
    logger.info(">>>>>>>>>>> Executing Tavily search")
    #logger.info(f"Query={query}, max_results={max_results}, include_domains={include_domains}, exclude_domains={exclude_domains}")
    try:

        if not tavily_client:
            logger.error("Tavily search tool is not available. Please set the TAVILY_API_KEY environment variable.")
            return "Tavily search tool is not available. Please set the TAVILY_API_KEY environment variable."

        search_params = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False,
        }

        if include_domains:
            search_params["include_domains"] = include_domains
        if exclude_domains:
            search_params["exclude_domains"] = exclude_domains

        response = tavily_client.search(**search_params)

        results = []

        if response.get("answer"):
            results.append(f"Summary:\n{response['answer']}\n")

        results.append("Results:")
        for i, item in enumerate(response.get("results", []), 1):
            results.append(
                f"""{i}. {item.get('title', 'No Title')}
            URL: {item.get('url', 'No URL')}
            Published: {item.get('published_date', 'Unknown')}
            Snippet: {item.get('content', 'No content available')}
            """
            )

        #print("Results: ", results)
        logger.info("Tavily search successful")
        tool_outputs={'tool_name':"tavily_search_tool" ,
                    'input_arguments': {'query': query, 'max_results': max_results, 'include_domains': include_domains, 'exclude_domains': exclude_domains},
                    'tool_output': "\n".join(results)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return "\n".join(results)

    except Exception as e:
        error_msg = f"Error during Tavily search: {str(e)}"
        logger.error(error_msg)
        #print("Exception occured ...")
        return error_msg
