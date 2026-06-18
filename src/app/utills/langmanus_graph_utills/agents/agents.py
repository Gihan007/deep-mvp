from langgraph.prebuilt import create_react_agent

from app.prompts.markdown import apply_prompt_template
from app.tools import (
    bash_tool,
    python_repl_tool,
    tavily_search_tool,
    duckduckgo_search_tool,
    graph_db_strctured_data_cypher_query_tool,
    graph_db_tenk_data_cypher_query_tool,
    alphavantage_company_overview_tool,
    alphavantage_earnings_call_transcript_tool,
    alphavantage_market_news_and_sentiment_tool,
    alphavantage_daily_stock_tool,
    visualization_tool,
    investment_metrics_calculator_tool,
    investment_factor_ranking_table_tool
)

from .llm import get_llm_by_type, get_tool_llm_by_type
from ..agents.agent_map import AGENT_LLM_MAP



researcher_agent = create_react_agent(
    get_tool_llm_by_type(AGENT_LLM_MAP["researcher"]),
    tools=[graph_db_strctured_data_cypher_query_tool, 
           graph_db_tenk_data_cypher_query_tool,
           duckduckgo_search_tool,
           alphavantage_company_overview_tool,
           alphavantage_earnings_call_transcript_tool,
           alphavantage_market_news_and_sentiment_tool,
           alphavantage_daily_stock_tool,
           investment_metrics_calculator_tool,
           investment_factor_ranking_table_tool],
    prompt=lambda state: apply_prompt_template("researcher_agent", state),
)

# coder: Python + Bash
coder_agent = create_react_agent(
    get_tool_llm_by_type(AGENT_LLM_MAP["coder"]),
    tools=[python_repl_tool, bash_tool],
    prompt=lambda state: apply_prompt_template("coder_agent", state),
)

# visualization_agent: charting/plotting
visualization_agent = create_react_agent(
    get_tool_llm_by_type(AGENT_LLM_MAP.get("visualization", "basic")),
    tools=[visualization_tool],
    prompt=lambda state: apply_prompt_template("visualization_agent", state),
)
