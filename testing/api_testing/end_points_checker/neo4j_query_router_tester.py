"""
4 Simple Python Functions to Test GraphDB Endpoints
Copy and use these functions individually
"""

import requests

BASE_URL = "http://localhost:8080"


# FUNCTION 1: Test Cypher Query Endpoint
def test_cypher():
    url = f"{BASE_URL}/api/graphdb/cypher"
    data = {
        "query": "MATCH (n) RETURN n LIMIT 5",
        "parameters": {},
        "mode": "read"
    }
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())


# FUNCTION 2: Test List Sectors Endpoint
def test_sectors():
    url = f"{BASE_URL}/api/graphdb/sectors"
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(response.json())


# FUNCTION 3: Test List Industries by Sector
def test_industries():
    url = f"{BASE_URL}/api/graphdb/industries_when_sector_given"
    params = {"sectorName": "Technology"}  # or use sectorId
    response = requests.get(url, params=params)
    print(f"Status: {response.status_code}")
    print(response.json())


# FUNCTION 4: Test List Companies by Industry
def test_companies():
    url = f"{BASE_URL}/api/graphdb/companies_when_industry_given"
    params = {"industryName": "Software"}  # or use industryId
    response = requests.get(url, params=params)
    print(f"Status: {response.status_code}")
    print(response.json())


# Run all tests
if __name__ == "__main__":
    # print("Test 1: Cypher Query")
    # test_cypher()
    
    print("\nTest 2: List Sectors")
    test_sectors()
    
    print("\nTest 3: List Industries")
    test_industries()
    
    print("\nTest 4: List Companies")
    test_companies()