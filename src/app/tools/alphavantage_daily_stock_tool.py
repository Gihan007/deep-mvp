"""
alphavantage_daily_stock_tool
"""

from typing import Optional
import requests
from langchain.tools import tool
import logging
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

from config import get_config
config = get_config()
ALPHA_VANTAGE_API_KEY = config.ALPHA_VANTAGE_API_KEY
ALPHA_VANTAGE_BASE_URL = config.ALPHA_VANTAGE_BASE_URL

tool_outputs= {}

@tool
def alphavantage_daily_stock_tool(
    symbol: str,
    days: int = 30,
    datatype: str = "json"
) -> str:
    """
    Get raw (as-traded) daily OHLCV (Open, High, Low, Close, Volume) time series data 
    for a specific global equity, covering 20+ years of historical data.
    
    This API returns daily "candle" data as-traded without split/dividend adjustments.
    For adjusted close values and historical split/dividend events, use the Daily Adjusted API instead.

    Args:
        symbol: Stock ticker symbol (e.g., "IBM", "AAPL", "MSFT", "TSLA")
        days: Number of recent days to retrieve (default: 30, max: 100 for compact)
        datatype: Response format - "json" or "csv". Default: "json"
    
    Returns:
        String containing daily OHLCV time series data with metadata
        
    Example:
        Get recent 30 days of Apple stock data:
        alphavantage_daily_stock_tool(symbol="AAPL")
        
        Get recent 7 days of IBM data:
        alphavantage_daily_stock_tool(symbol="IBM", days=7)
    """
    logger.info(">>>>>>>>>>> Executing alphavantage_daily_stock_tool")
    logger.info(f"Symbol={symbol}, days={days}, datatype={datatype}")
    try:
        # Validate datatype
        valid_datatypes = ["json", "csv"]
        if datatype not in valid_datatypes:
            logger.error("Invalid datatype. Must be one of: {', '.join(valid_datatypes)}")
            return f"Invalid datatype. Must be one of: {', '.join(valid_datatypes)}"

        # Validate days parameter
        if days <= 0:
            return "Error: 'days' parameter must be greater than 0"

        # Build parameters
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "datatype": datatype,
            "apikey": ALPHA_VANTAGE_API_KEY
        }

        logger.info(f"Fetching daily data for {symbol} (last {days} days)...")

        # Make API request
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
        
        # Handle CSV response
        if datatype == "csv":
            if response.status_code == 200:
                # For CSV, split by lines and take only the requested days (+1 for header)
                csv_lines = response.text.split('\n')
                filtered_csv = '\n'.join(csv_lines[:days + 1])  # +1 to include header
                
                logger.info("Daily stock CSV fetched successfully")
                tool_outputs={'tool_name':"alphavantage_daily_stock_tool" ,
                            'input_arguments': {'symbol': symbol, 'days': days, 'datatype': datatype},
                            'tool_output': filtered_csv
                            }
                try:
                    add_tool_output(tool_outputs)
                except Exception:
                    pass
                return filtered_csv
            else:
                logger.error(f"Error fetching CSV data: HTTP {response.status_code}")
                return f"Error fetching CSV data: HTTP {response.status_code}"
        
        # Handle JSON response
        data = response.json()

        if not data or data == {}:
            logger.error(f"No data found for symbol: {symbol}")
            return f"No data found for symbol: {symbol}"
        
        # Check for API error messages
        if "Error Message" in data:
            logger.error(f"API Error: {data['Error Message']}")
            return f"API Error: {data['Error Message']}"
        
        if "Note" in data:
            logger.warning(f"API Note: {data['Note']}")
            return f"API Note: {data['Note']}"
        
        if "Information" in data:
            logger.info(f"API Information: {data['Information']}")
            return f"API Information: {data['Information']}"

        # Filter time series data to only include requested number of days
        modified_data = data.copy()
        
        if "Time Series (Daily)" in modified_data:
            time_series = modified_data["Time Series (Daily)"]
            # Get only the first N days (data is in reverse chronological order)
            filtered_time_series = dict(list(time_series.items())[:days])
            modified_data["Time Series (Daily)"] = filtered_time_series
            
            logger.info(f"Filtered to {len(filtered_time_series)} days of data")
        
        logger.info("Daily stock JSON fetched successfully")
        tool_outputs={'tool_name':"alphavantage_daily_stock_tool" ,
                    'input_arguments': {'symbol': symbol, 'days': days, 'datatype': datatype},
                    'tool_output': str(modified_data)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return str(modified_data)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error fetching daily stock data: {str(e)}"
        logger.error(error_msg)
        return error_msg
    
    except Exception as e:
        error_msg = f"Error fetching daily stock data: {str(e)}"
        logger.error(error_msg)
        return error_msg