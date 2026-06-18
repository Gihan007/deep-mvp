# File: tools/__init__.py
"""
QA Tools package - Shared tool exports
"""

# Core/shared tools
from .python_repl_tool import python_repl_tool
from .bash_tool import bash_tool

# Search and retrieval
from .tavily_search_tool import tavily_search_tool
from .duckduckgo_search_tool import duckduckgo_search_tool
# from .chroma_retrieval_tool import chroma_retrieval_tool  # optional

# Graph DB tools
from .graph_db_strctured_data_cypher_query_tool import graph_db_strctured_data_cypher_query_tool
from .graph_db_tenk_data_cypher_query_tool import graph_db_tenk_data_cypher_query_tool
from .graph_db_vector_search_tool import graph_db_vector_search_tool
from .graph_db_cypher_query_tool import graph_db_cypher_query_tool
from .update_graph_based_on_user_q import update_graph_based_on_user_q


# Alpha Vantage
from .alphavantage_company_overview_tool import alphavantage_company_overview_tool
from .alphavantage_earnings_call_transcript_tool import alphavantage_earnings_call_transcript_tool
from .alphavantage_market_news_and_sentiment_tool import alphavantage_market_news_and_sentiment_tool
from .alphavantage_daily_stock_tool import alphavantage_daily_stock_tool
from .alphavantage_intraday_stock_tool import alphavantage_intraday_stock_tool
from .alphavantage_comprehensive_tool import alphavantage_comprehensive_tool
from .visualization_tool import visualization_tool

# custom tool
from .investment_metrics_calculator_tool import investment_metrics_calculator_tool
from .investment_factor_ranking_table_tool import investment_factor_ranking_table_tool


# Tool registry for batch operations (order can matter for some graphs)
ALL_TOOLS = [
    # Core utilities
    python_repl_tool,
    bash_tool,

    # Search
    tavily_search_tool,
    duckduckgo_search_tool,

    # Graph DB
    graph_db_strctured_data_cypher_query_tool,
    graph_db_tenk_data_cypher_query_tool,
    graph_db_vector_search_tool,
    graph_db_cypher_query_tool,
    update_graph_based_on_user_q,

    # Alpha Vantage
    alphavantage_company_overview_tool,
    alphavantage_earnings_call_transcript_tool,
    alphavantage_market_news_and_sentiment_tool,
    alphavantage_daily_stock_tool,
    alphavantage_intraday_stock_tool,
    alphavantage_comprehensive_tool,
    visualization_tool,

    # custom tools
    investment_metrics_calculator_tool,
    investment_factor_ranking_table_tool,
]


def initialize_all_tools(graphdb_vector_store, chromadb_vector_store, llm, config):
    """
    Initialize all tools. Many tools are now self-initializing from env and require no external injection.
    We keep initializer for backward-compatibility (e.g., vector-based tools, legacy cypher tools).
    """
    try:
        from .tool_initializer import ToolInitializer
        initializer = ToolInitializer(graphdb_vector_store, chromadb_vector_store, llm, config)
        # This will set optional deps for legacy tools; self-initializing tools will ignore.
        _ = initializer.initialize_all()
    except Exception as e:
        print(f"initialize_all_tools warning: {e}")

    try:
        print("Registered tools:", [t.name for t in ALL_TOOLS])
    except Exception as _e:
        print(f"Registered tools logging failed: {_e}")
    return ALL_TOOLS
