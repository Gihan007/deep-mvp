"""
alphavantage_earnings_call_transcript_tool
"""

from langchain.tools import tool
from ddgs import DDGS
from typing import Optional, List, Dict, Any
import requests
import logging
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

from config import get_config
config = get_config()
ALPHA_VANTAGE_API_KEY = config.ALPHA_VANTAGE_API_KEY
ALPHA_VANTAGE_BASE_URL = config.ALPHA_VANTAGE_BASE_URL

tool_outputs= {}

@tool
def alphavantage_earnings_call_transcript_tool(symbol: str, quarter: Optional[str] = None) -> str:

    """
    This API returns the earnings call transcript(a conference call where company executives (usually the CEO, CFO, and other senior leaders) discuss the company’s financial performance) 
    for a given company in a specific quarter, covering over 15 years of history and enriched with LLM-based sentiment signals

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "IBM", "MSFT")
        quarter: Specific quarter in format YYYYQN (e.g., "2024Q1", "2023Q4")
                If not provided, returns the latest available transcript.
    
    Returns:
        String containing the earnings call transcript or available quarters.
    """
    logger.info(">>>>>>>>>>> Executing alphavantage_earnings_call_transcript_tool")
    #logger.info(f"Symbol={symbol}, quarter={quarter}")
    try:
        #print("")
        #print(f">>>>>>>>>>> alphavantage_earnings_call_transcript_tool calling for company ticker: {symbol} and quarter: {quarter}")
        
        params = {
            "function": "EARNINGS_CALL_TRANSCRIPT",
            "symbol": symbol.upper(),
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        # Add quarter if specified
        if quarter:
            params["quarter"] = quarter
        
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
        data = response.json()
        
        # Get top 10 executive statements with highest sentiment
        executive_keywords = ['ceo', 'cfo', 'chief', 'president']
        executive_transcripts = []
        for item in data['transcript']:
            title_lower = item['title'].lower()
            if any(keyword in title_lower for keyword in executive_keywords):
                executive_transcripts.append(item)
        top_executive = sorted(executive_transcripts, key=lambda x: float(x['sentiment']), reverse=True)[:3]
        logger.info("Earnings call transcript fetched successfully")
        tool_outputs={'tool_name':"alphavantage_earnings_call_transcript_tool" ,
                    'input_arguments': {'symbol': symbol, 'quarter': quarter},
                    'tool_output': str(top_executive)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return str(top_executive)

    except Exception as e:
        error_msg = f"Error fetching earnings call transcript: {str(e)}"
        logger.error(error_msg)
        #print("Exception occured ...")
        return error_msg
