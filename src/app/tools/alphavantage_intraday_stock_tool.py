"""
alphavantage_intraday_stock_tool
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
def alphavantage_intraday_stock_tool(
    symbol: str,
    interval: str = "5min",
    adjusted: bool = True,
    extended_hours: bool = True,
    month: Optional[str] = None,
    outputsize: str = "compact",
    datatype: str = "json"
) -> str:
    """
    Get current and historical intraday OHLCV (Open, High, Low, Close, Volume) time series data 
    for a specific stock, covering pre-market and post-market hours where applicable.
    
    This API returns intraday "candle" data with 20+ years of historical coverage since 2000.
    The data can be queried as raw (as-traded) or split/dividend-adjusted.

    Args:
        symbol: Stock ticker symbol (e.g., "IBM", "AAPL", "MSFT")
        interval: Time interval between data points. Options: "1min", "5min", "15min", "30min", "60min"
        adjusted: If True, adjusts for historical splits and dividends. Default: True
        extended_hours: If True, includes pre-market (4:00am) and post-market (8:00pm) data. 
                       If False, only regular trading hours (9:30am-4:00pm ET). Default: True
        month: Query specific month in YYYY-MM format (e.g., "2024-01"). 
               If not set, returns most recent trading days. Any month since 2000-01 is supported.
        outputsize: "compact" returns latest 100 data points; 
                   "full" returns trailing 30 days or full month if month parameter is set.
                   Default: "compact"
        datatype: Response format - "json" or "csv". Default: "json"
    
    Returns:
        String containing intraday OHLCV time series data with metadata
    """
    logger.info(">>>>>>>>>>> Executing alphavantage_intraday_stock_tool")
    #logger.info(f"Symbol={symbol}, interval={interval}, adjusted={adjusted}, extended_hours={extended_hours}, month={month}, outputsize={outputsize}, datatype={datatype}")
    try:
        #print(">>>>>>>>>>> alphavantage_intraday_stock_tool calling ...")

        # Validate interval
        valid_intervals = ["1min", "5min", "15min", "30min", "60min"]
        if interval not in valid_intervals:
            logger.error(f"Invalid interval. Must be one of: {', '.join(valid_intervals)}")
            return f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"

        # Build parameters
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "adjusted": "true" if adjusted else "false",
            "extended_hours": "true" if extended_hours else "false",
            "outputsize": outputsize,
            "datatype": datatype,
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        # Add optional month parameter if provided
        if month:
            params["month"] = month

        # Make API request
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
        
        # Handle CSV response
        if datatype == "csv":
            logger.info("Intraday stock data fetched successfully")
            tool_outputs={'tool_name':"alphavantage_intraday_stock_tool" ,
                        'input_arguments': {'symbol': symbol, 'interval': interval, 'adjusted': adjusted, 'extended_hours': extended_hours, 'month': month, 'outputsize': outputsize, 'datatype': datatype},
                        'tool_output': response.text
                        }
            try:
                add_tool_output(tool_outputs)
            except Exception:
                pass
            return response.text
        
        # Handle JSON response
        data = response.json()

        if not data or data == {}:
            logger.info(f"No data found for symbol: {symbol}")
            return f"No data found for symbol: {symbol}"
        
        # Check for API error messages
        if "Error Message" in data:
            logger.error(f"API Error: {data['Error Message']}")
            return f"API Error: {data['Error Message']}"
        
        if "Note" in data:
            logger.info(f"API Error: {data['Error Message']}")
            return f"API Note: {data['Note']}"

        # For compact output, limit the time series data to make response manageable
        modified_data = data.copy()
        
        # Get the time series key (it varies based on parameters)
        time_series_key = None
        for key in data.keys():
            if key.startswith("Time Series"):
                time_series_key = key
                break
        
        if time_series_key and outputsize == "compact":
            # Get first 20 entries for compact view
            time_series = data[time_series_key]
            limited_series = dict(list(time_series.items())[:20])
            modified_data[time_series_key] = limited_series

        #print(f"Results for {symbol}: Retrieved {len(data.get(time_series_key, {}))} data points")
        logger.info("Intraday stock data fetched successfully")
        tool_outputs={'tool_name':"alphavantage_intraday_stock_tool" ,
                    'input_arguments': {'symbol': symbol, 'interval': interval, 'adjusted': adjusted, 'extended_hours': extended_hours, 'month': month, 'outputsize': outputsize, 'datatype': datatype},
                    'tool_output': str(modified_data)
                    }
        try:
            add_tool_output(tool_outputs)
        except Exception:
            pass
        return str(modified_data)
        
    except Exception as e:
        error_msg = f"Error fetching intraday stock data: {str(e)}"
        logger.error(error_msg)
        #print(error_msg)
        return error_msg
