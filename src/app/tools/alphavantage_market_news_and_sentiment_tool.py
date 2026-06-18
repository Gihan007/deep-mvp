"""
alphavantage_market_news_and_sentiment_tool
"""

from typing import Optional, List, Dict, Any
import requests
from langchain.tools import tool
from ddgs import DDGS
import logging
from app.utills.tool_output_collector import add_tool_output

logger = logging.getLogger(__name__)

from config import get_config
config = get_config()
ALPHA_VANTAGE_API_KEY = config.ALPHA_VANTAGE_API_KEY
ALPHA_VANTAGE_BASE_URL = config.ALPHA_VANTAGE_BASE_URL

tool_outputs= {}


@tool
def alphavantage_market_news_and_sentiment_tool(
    tickers: Optional[str] = None,
    topics: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    sort_order: str = "LATEST",
    limit: int = 50
) -> str:
    """
    Get market news and sentiment analysis for specific tickers or topics.
    This API returns live and historical market news & sentiment data from a large & growing selection of premier news outlets around the world, 
    covering stocks, cryptocurrencies, forex, and a wide range of topics such as fiscal policy, mergers & acquisitions, IPOs, etc. 
    This API, combined with alphavantage's core stock API, fundamental data, and technical indicator APIs, 
    can provide you with a 360-degree view of the financial market and the broader economy.

    Args:
        tickers: Comma-separated stock symbols (e.g., "AAPL,MSFT,CRYPTO:BTC,FOREX:USD")
        topics: Comma-separated topics from available list (e.g., "technology,earnings")
                Available: blockchain, earnings, ipo, mergers_and_acquisitions, financial_markets,
                economy_fiscal, economy_monetary, economy_macro, energy_transportation, finance,
                life_sciences, manufacturing, real_estate, retail_wholesale, technology
        time_from: Start datetime in format YYYYMMDDTHHMM (e.g., "20240701T0000")
        time_to: End datetime in format YYYYMMDDTHHMM (optional)
        sort_order: How to sort results - LATEST, EARLIEST, or RELEVANCE
        limit: Number of articles to return (set this to 40)
    
    Returns:
        String containing news articles with sentiment analysis
    """
    logger.info(">>>>>>>>>>>  Executing alphavantage_market_news_and_sentiment_tool")
    #logger.info(f"Tickers={tickers}, Topics={topics}, Time_from={time_from}, Time_to={time_to}, Sort={sort_order}, Limit={limit}")
    try:
        #print(">>>>>>>>>>> alphavantage_market_news_and_sentiment_tool calling ...")

        
        # Build parameters
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": tickers,
            "topics": topics,
            "time_from": time_from,
            "time_to": time_to,
            "sort": sort_order,
            "limit": limit,
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
        
        #print("")
        #print("tickers: ", tickers)
        #print("topics: ", topics)
        #print("time_from: ", time_from)
        #print("time_to: ", time_to)
        #print("sort_order: ", sort_order)
        #print("limit: ", limit)
        #print("")

        # Make API request
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
        data = response.json()

        if not data or data == {}:
            logger.info(f"No data found for tickers: {tickers}")
            return f"No data found for tickers: {tickers}"
        
        modified_data = data.copy()
        modified_data['feed'] = data['feed'][:10]

        #print("Results: ", str(modified_data))
        logger.info("Market news and sentiment fetched successfully")
        tool_outputs={'tool_name':"alphavantage_market_news_and_sentiment_tool" ,
                    'input_arguments': {'tickers': tickers, 'topics': topics, 'time_from': time_from, 'time_to': time_to, 'sort_order': sort_order, 'limit': limit},
                    'tool_output': str(modified_data)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return str(modified_data)
        
    except Exception as e:
        error_msg = f"Error fetching market news and sentiment: {str(e)}"
        logger.error(error_msg)
        #print("Exception occured ...")
        return error_msg
