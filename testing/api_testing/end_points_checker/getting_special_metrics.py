"""
4 Simple Python Functions to Test Special Metrics Endpoints
Run with: python test_special_metrics.py
"""

import requests
import pandas as pd

BASE_URL = "http://localhost:8080"

# NOTE:
# This repo's Neo4j demo dataset uses tickers like COST/WMT/TGT/DG/DLTR/BJ.
# If you query a ticker that doesn't exist in Neo4j (e.g., GOOGL), you'll get 404.
DEFAULT_TICKER = "COST"


# FUNCTION 1: Test Market Cap Endpoint
def test_market_cap():
    """Test POST /api/special_metrics/market_cap"""
    url = f"{BASE_URL}/api/special_metrics/market_cap"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()


# FUNCTION 2: Test Shares Outstanding Endpoint
def test_shares_outstanding():
    """Test POST /api/special_metrics/shares_outstanding"""
    url = f"{BASE_URL}/api/special_metrics/shares_outstanding"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()


# FUNCTION 3: Test Stock Price Endpoint
def test_stock_price():
    """Test POST /api/special_metrics/stock_price"""
    url = f"{BASE_URL}/api/special_metrics/stock_price"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()



# FUNCTION 4: Test Stock Price Endpoint
def test_intrinsic_to_mc():
    """Test POST /api/special_metrics/intrinsic_to_mc"""
    url = f"{BASE_URL}/api/special_metrics/intrinsic_to_mc"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()


def test_intrinsic_value():
    """Test POST /api/special_metrics/intrinsic_value"""
    url = f"{BASE_URL}/api/special_metrics/intrinsic_value"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()


def test_roic():
    """Test POST /api/special_metrics/roic"""
    url = f"{BASE_URL}/api/special_metrics/roic"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()


def test_earnings_yield():
    """Test POST /api/special_metrics/earnings_yield"""
    url = f"{BASE_URL}/api/special_metrics/earnings_yield"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()


def test_margin_of_safety():
    """Test POST /api/special_metrics/margin_of_safety"""
    url = f"{BASE_URL}/api/special_metrics/margin_of_safety"
    data = {"ticker": DEFAULT_TICKER}
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
    return response.json()



def test_investment_ranking():
    """Test POST /api/special_metrics/investment_factor_ranking_table"""
    url = f"{BASE_URL}/api/special_metrics/investment_factor_ranking_table"
    data = {
        "tickers": ['WMT', 'SPB', 'SFM']             # ['WMT', 'SPB', 'SFM']  , ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]   
    }
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    # Convert JSON response to pandas DataFrame
    result_json = response.json()
    table_data = result_json.get('table', [])
    df = pd.DataFrame(table_data)
    print("\n--- Full Table ---")
    print(df)
    print("\n--- Preview (head()) ---")
    print(df.head())

    return result_json


# Run all tests
if __name__ == "__main__":
    # print("\n" + "="*60)
    # print("Test 1: Market Cap")
    # print("="*60)
    # test_market_cap()
    
    # print("\n" + "="*60)
    # print("Test 2: Shares Outstanding")
    # print("="*60)
    # test_shares_outstanding()
    
    # print("\n" + "="*60)
    # print("Test 3: Stock Price")
    # print("="*60)
    # test_stock_price()

    # NOTE:
    # Special metric endpoints now return ONLY the intended value (no ticker field).
    # Examples:
    #   {"intrinsic_to_mc": 0.39}
    #   {"earnings_yield": 0.01}

    print("\n" + "="*60)
    print("Test 1: Market Cap")
    print("="*60)
    test_market_cap()

    print("\n" + "="*60)
    print("Test 2: Shares Outstanding")
    print("="*60)
    test_shares_outstanding()

    print("\n" + "="*60)
    print("Test 3: Stock Price")
    print("="*60)
    test_stock_price()

    print("\n" + "="*60)
    print("Test 4: Intrinsic_to_MC")
    print("="*60)
    test_intrinsic_to_mc()

    print("\n" + "="*60)
    print("Test 5: Intrinsic Value")
    print("="*60)
    test_intrinsic_value()

    print("\n" + "="*60)
    print("Test 6: ROIC")
    print("="*60)
    test_roic()

    print("\n" + "="*60)
    print("Test 7: Earnings Yield")
    print("="*60)
    test_earnings_yield()

    print("\n" + "="*60)
    print("Test 8: Margin of Safety")
    print("="*60)
    test_margin_of_safety()
    
    # print("\n" + "="*60)
    # print("Test 4: Investment Factor Ranking Table")
    # print("="*60)
    # test_investment_ranking()
