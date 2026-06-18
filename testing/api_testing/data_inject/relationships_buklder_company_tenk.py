

import json
import requests

API_URL = "http://localhost:8080/api/data_inject_graph_db/create_all_company_tenk_relationships"
API_URL = "http://localhost:8080/api/data_inject_graph_db/create_all_company_tenk_relationships"

def test_create_all_company_tenk_relationships():
    """
    Calls the API endpoint that creates HAS_TENK_DATA relationships for ALL matching
    Company and TenKChunk nodes (by ticker). Prints status and response.
    """
    print(f"POST {API_URL}")
    try:
        resp = requests.post(API_URL, timeout=120)
        print("Status Code:", resp.status_code)
        try:
            print("Response JSON:", json.dumps(resp.json(), indent=2))
        except Exception:
            print("Response Text:", resp.text)
    except Exception as e:
        print("Request failed:", e)


if __name__ == "__main__":
    test_create_all_company_tenk_relationships()
