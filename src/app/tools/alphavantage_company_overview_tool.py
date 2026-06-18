"""
alphavantage_company_overview_tool
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
def alphavantage_company_overview_tool(symbol: str) -> str:
    """
    This API use to get  55 key values listed under Returns
    Data is generally refreshed on the same day a company reports its latest earnings and financial
    
    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "IBM", "MSFT")
    
    Returns:
        returns a dictionary with the following keys:
            ["Symbol", "AssetType", "Name", "Description", "CIK", "Exchange", "Currency", "Country", "Sector", "Industry", "Address", "OfficialSite", "FiscalYearEnd",
            "LatestQuarter", "MarketCapitalization", "EBITDA", "PERatio", "PEGRatio", "BookValue", "DividendPerShare", "DividendYield", "EPS", "RevenuePerShareTTM",
            "ProfitMargin", "OperatingMarginTTM", "ReturnOnAssetsTTM", "ReturnOnEquityTTM", "RevenueTTM", "GrossProfitTTM", "DilutedEPSTTM", "QuarterlyEarningsGrowthYOY",
            "QuarterlyRevenueGrowthYOY", "AnalystTargetPrice", "AnalystRatingStrongBuy", "AnalystRatingBuy", "AnalystRatingHold", "AnalystRatingSell", "AnalystRatingStrongSell",
            "TrailingPE", "ForwardPE", "PriceToSalesRatioTTM", "PriceToBookRatio", "EVToRevenue", "EVToEBITDA", "Beta", "52WeekHigh", "52WeekLow", "50DayMovingAverage",
            "200DayMovingAverage", "SharesOutstanding", "SharesFloat", "PercentInsiders", "PercentInstitutions", "DividendDate", "ExDividendDate"]
    """
    logger.info(f">>>>>>>>>>> Executing alphavantage_company_overview_tool for Symbol={symbol}")
    try:
        params = {"function": "OVERVIEW","symbol": symbol.upper(),"apikey": ALPHA_VANTAGE_API_KEY}
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
        data = response.json()
        
        if not data or data == {}:
            logger.info(f"No data found for symbol: {symbol}")
            return f"No data found for symbol: {symbol}"

        logger.info("Company overview fetched successfully ")
        tool_outputs={'tool_name':"alphavantage_company_overview_tool" ,
                    'input_arguments': {'symbol': symbol},
                    'tool_output': str(data)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return str(data)
        
    except Exception as e:
        error_msg = f"Error fetching company overview: {str(e)}"
        logger.error(error_msg)
        #print("Exception occured ...")
        return error_msg
