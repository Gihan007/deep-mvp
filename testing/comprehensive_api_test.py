#!/usr/bin/env python3
"""
Comprehensive API Test Suite for Get-Deep Application
Tests all endpoints except data injection and delete operations
Generates detailed success/failure reports
"""

import requests
import json
import time
import datetime
import os
import sys
import traceback
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import threading

# Configuration
BASE_URL = "http://localhost:8080"
TEST_RESULTS_DIR = "test_results"
REPORT_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_FILE = f"{TEST_RESULTS_DIR}/api_test_report_{REPORT_TIMESTAMP}.json"
REPORT_HTML = f"{TEST_RESULTS_DIR}/api_test_report_{REPORT_TIMESTAMP}.html"

# Test Configuration
DEFAULT_TIMEOUT = 30
MAX_CONCURRENT_TESTS = 5
TEST_TICKERS = ["AAPL", "MSFT", "GOOGL", "COST", "WMT"]  # Mix of tickers for testing

@dataclass
class TestResult:
    """Test result data structure"""
    endpoint: str
    method: str
    status: str  # SUCCESS, FAILURE, SKIP
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    response_size: Optional[int] = None
    error_message: Optional[str] = None
    response_data: Optional[Dict] = None
    test_params: Optional[Dict] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()

class APITester:
    """Main API testing class"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.session = requests.Session()
        self.lock = threading.Lock()
        
        # Ensure test results directory exists
        os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
        
        print(f"🚀 Starting API Test Suite")
        print(f"📍 Base URL: {self.base_url}")
        print(f"⏰ Timestamp: {REPORT_TIMESTAMP}")
        print("="*60)
    
    def add_result(self, result: TestResult):
        """Thread-safe result addition"""
        with self.lock:
            self.results.append(result)
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> Tuple[requests.Response, float]:
        """Make HTTP request with timing"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            response = self.session.request(
                method=method, 
                url=url, 
                timeout=kwargs.pop('timeout', DEFAULT_TIMEOUT),
                **kwargs
            )
            response_time = time.time() - start_time
            return response, response_time
        except Exception as e:
            response_time = time.time() - start_time
            raise Exception(f"Request failed: {str(e)}")
    
    def test_endpoint(self, endpoint: str, method: str = "GET", **kwargs) -> TestResult:
        """Test a single endpoint"""
        print(f"🔍 Testing {method} {endpoint}")
        
        try:
            response, response_time = self.make_request(method, endpoint, **kwargs)
            
            # Determine status
            if 200 <= response.status_code <= 299:
                status = "SUCCESS"
                error_message = None
            else:
                status = "FAILURE"
                error_message = f"HTTP {response.status_code}: {response.text[:200]}"
            
            # Try to parse JSON response
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text[:500]}
            
            return TestResult(
                endpoint=endpoint,
                method=method,
                status=status,
                status_code=response.status_code,
                response_time=round(response_time, 3),
                response_size=len(response.content),
                error_message=error_message,
                response_data=response_data,
                test_params=kwargs.get('json') or kwargs.get('params') or kwargs.get('data')
            )
            
        except Exception as e:
            return TestResult(
                endpoint=endpoint,
                method=method,
                status="FAILURE",
                error_message=str(e),
                test_params=kwargs.get('json') or kwargs.get('params') or kwargs.get('data')
            )

    def test_chat_endpoints(self):
        """Test chat-related endpoints"""
        print("\n📝 Testing Chat Endpoints")
        print("-" * 40)
        
        test_cases = [
            # General QA Bot
            {
                "endpoint": "/api/qa_bot",
                "method": "POST",
                "json": {
                    "question": "What is Apple's current stock price?",
                    "session_id": f"test_session_{int(time.time())}",
                    "base64_images": [],
                    "base64_files": [],
                    "base64_audios": []
                }
            },
            
            # Deep QA Bot
            {
                "endpoint": "/api/deep_qa_bot",
                "method": "POST", 
                "json": {
                    "question": "Analyze Microsoft's financial performance over the last 5 years",
                    "session_id": f"deep_session_{int(time.time())}",
                    "base64_images": [],
                    "base64_files": [],
                    "base64_audios": []
                }
            },
            
            # Report Generation
            {
                "endpoint": "/api/deep_qa_bot_report",
                "method": "POST",
                "json": {
                    "session_id": f"report_session_{int(time.time())}",
                    "report_type": "company_performance_and_investment_thesis",
                    "ticker": "AAPL",
                    "time_horizon": "last 3 years",
                    "instructions": "Include financial metrics and growth analysis"
                }
            }
        ]
        
        for test_case in test_cases:
            result = self.test_endpoint(**test_case)
            self.add_result(result)

    def test_special_metrics_endpoints(self):
        """Test special metrics endpoints"""
        print("\n📊 Testing Special Metrics Endpoints")
        print("-" * 40)
        
        metrics_endpoints = [
            "market_cap", "shares_outstanding", "stock_price", 
            "intrinsic_to_mc", "intrinsic_value", "roic",
            "earnings_yield", "margin_of_safety"
        ]
        
        for ticker in ["AAPL", "COST"]:  # Test with multiple tickers
            for metric in metrics_endpoints:
                result = self.test_endpoint(
                    endpoint=f"/api/special_metrics/{metric}",
                    method="POST",
                    json={"ticker": ticker}
                )
                self.add_result(result)
        
        # Test multiples table metric
        result = self.test_endpoint(
            endpoint="/api/special_metrics/multiples_table_metric",
            method="POST",
            json={"ticker": "AAPL", "metric_name": "MarketCap_Fundamental"}
        )
        self.add_result(result)
        
        # Test investment factor ranking
        result = self.test_endpoint(
            endpoint="/api/special_metrics/investment_factor_ranking_table",
            method="POST",
            json={"tickers": ["AAPL", "MSFT", "GOOGL"]}
        )
        self.add_result(result)
        
        # Test ranking for all companies
        result = self.test_endpoint(
            endpoint="/api/special_metrics/investment_factor_ranking_table_for_all_companies",
            method="POST"
        )
        self.add_result(result)

    def test_graphdb_endpoints(self):
        """Test Neo4j graph database endpoints"""
        print("\n🗄️ Testing Graph Database Endpoints")
        print("-" * 40)
        
        test_cases = [
            # Cypher query
            {
                "endpoint": "/api/graphdb/cypher",
                "method": "POST",
                "json": {
                    "query": "MATCH (n:Company) RETURN n.ticker, n.companyName LIMIT 5",
                    "parameters": {},
                    "mode": "read"
                }
            },
            
            # List sectors
            {
                "endpoint": "/api/graphdb/sectors",
                "method": "GET"
            },
            
            # List industries by sector
            {
                "endpoint": "/api/graphdb/industries_when_sector_given",
                "method": "GET",
                "params": {"sectorName": "Technology"}
            },
            
            # List companies by industry
            {
                "endpoint": "/api/graphdb/companies_when_industry_given",
                "method": "GET",
                "params": {"industryName": "Software"}
            },
            
            # List companies by sector
            {
                "endpoint": "/api/graphdb/companies_when_sector_given",
                "method": "GET", 
                "params": {"sectorName": "Technology"}
            },
            
            # List all companies
            {
                "endpoint": "/api/graphdb/companies",
                "method": "GET"
            },
            
            # Get node counts
            {
                "endpoint": "/api/graphdb/node_counts",
                "method": "GET"
            }
        ]
        
        for test_case in test_cases:
            result = self.test_endpoint(**test_case)
            self.add_result(result)

    def test_update_graph_endpoints(self):
        """Test graph update endpoints (non-destructive operations only)"""
        print("\n🔄 Testing Graph Update Endpoints")
        print("-" * 40)
        
        # Only test read-like operations that won't modify data
        test_cases = [
            {
                "endpoint": "/api/update_graph/execute",
                "method": "POST",
                "json": {
                    "question": "Show me the structure of Company nodes",
                    "session_id": f"update_test_{int(time.time())}"
                }
            }
        ]
        
        for test_case in test_cases:
            result = self.test_endpoint(**test_case)
            self.add_result(result)

    def test_central_api_endpoints(self):
        """Test central financial analysis API endpoints"""
        print("\n💼 Testing Central API Endpoints")
        print("-" * 40)
        
        test_cases = [
            # Get companies
            {
                "endpoint": "/api/central/companies",
                "method": "GET"
            },
            
            # Get metrics
            {
                "endpoint": "/api/central/metrics",
                "method": "GET",
                "params": {"include_predicted": "false", "display_names": "false"}
            },
            
            # Get industries
            {
                "endpoint": "/api/central/industries", 
                "method": "GET"
            },
            
            # Get aggregated data
            {
                "endpoint": "/api/central/aggregated-data",
                "method": "GET",
                "params": {
                    "tickers": "AAPL,MSFT",
                    "metric": "Revenue",
                    "period": "5Y",
                    "periodType": "Annual"
                }
            },
            
            # Financial statements
            {
                "endpoint": "/api/central/financials/income-statement/AAPL",
                "method": "GET"
            },
            {
                "endpoint": "/api/central/financials/balance-sheet/AAPL",
                "method": "GET"
            },
            {
                "endpoint": "/api/central/financials/cash-flow/AAPL",
                "method": "GET"
            },
            
            # Analysis endpoints
            {
                "endpoint": "/api/central/analysis/nopat/AAPL",
                "method": "GET"
            },
            {
                "endpoint": "/api/central/analysis/invested-capital/AAPL",
                "method": "GET"
            },
            {
                "endpoint": "/api/central/analysis/free-cash-flow/AAPL",
                "method": "GET"
            },
            {
                "endpoint": "/api/central/analysis/roic/AAPL",
                "method": "GET"
            },
            
            # Rankings
            {
                "endpoint": "/api/central/rankings/types",
                "method": "GET"
            }
        ]
        
        for test_case in test_cases:
            result = self.test_endpoint(**test_case)
            self.add_result(result)

    def test_dynamic_table_endpoints(self):
        """Test dynamic table endpoints"""
        print("\n📋 Testing Dynamic Table Endpoints")
        print("-" * 40)
        
        table_types = [
            "3StatementModel", "FreeCashFlows", "ReportedFinancials",
            "InvestedCapital", "Performance", "HistoricalCagrAvg",
            "ExtractedItems", "ValuationForecastDriverValues",
            "ValuationSummary"
        ]
        
        for table_type in table_types:
            result = self.test_endpoint(
                endpoint=f"/api/dynamic_table/{table_type}",
                method="POST",
                data={"ticker": "AAPL"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            self.add_result(result)

    def test_kpi_endpoints(self):
        """Test KPI properties endpoints"""
        print("\n📈 Testing KPI Endpoints")
        print("-" * 40)
        
        result = self.test_endpoint(
            endpoint="/api/kpi/properties",
            method="POST",
            json={"metric_names": ["Revenue", "GrossMargin", "EBITDA"]}
        )
        self.add_result(result)

    def test_session_endpoints(self):
        """Test session management endpoints"""
        print("\n👥 Testing Session Endpoints")
        print("-" * 40)
        
        test_cases = [
            {
                "endpoint": "/api/sessions",
                "method": "GET"
            }
            # Note: Not testing specific session details or deletion as requested
        ]
        
        for test_case in test_cases:
            result = self.test_endpoint(**test_case)
            self.add_result(result)

    def run_all_tests(self):
        """Run all test suites"""
        start_time = time.time()
        
        # Run test suites
        test_suites = [
            self.test_chat_endpoints,
            self.test_special_metrics_endpoints,
            self.test_graphdb_endpoints,
            self.test_update_graph_endpoints,
            self.test_central_api_endpoints,
            self.test_dynamic_table_endpoints,
            self.test_kpi_endpoints,
            self.test_session_endpoints
        ]
        
        for test_suite in test_suites:
            try:
                test_suite()
            except Exception as e:
                print(f"❌ Test suite failed: {test_suite.__name__}: {str(e)}")
                traceback.print_exc()
        
        total_time = time.time() - start_time
        
        print(f"\n✅ All tests completed in {total_time:.2f} seconds")
        print(f"📊 Total endpoints tested: {len(self.results)}")
        
        return total_time

    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n📄 Generating Test Report")
        print("-" * 40)
        
        # Calculate statistics
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.status == "SUCCESS"])
        failed_tests = len([r for r in self.results if r.status == "FAILURE"])
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Group by endpoint category
        endpoint_categories = {}
        for result in self.results:
            category = result.endpoint.split('/')[2] if len(result.endpoint.split('/')) > 2 else 'root'
            if category not in endpoint_categories:
                endpoint_categories[category] = []
            endpoint_categories[category].append(result)
        
        # Create report data
        report_data = {
            "test_summary": {
                "timestamp": REPORT_TIMESTAMP,
                "base_url": self.base_url,
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": round(success_rate, 2),
                "avg_response_time": round(sum(r.response_time for r in self.results if r.response_time) / len([r for r in self.results if r.response_time]), 3) if any(r.response_time for r in self.results) else 0
            },
            "category_breakdown": {},
            "detailed_results": [asdict(result) for result in self.results],
            "failed_tests_details": [asdict(result) for result in self.results if result.status == "FAILURE"]
        }
        
        # Category breakdown
        for category, results in endpoint_categories.items():
            category_success = len([r for r in results if r.status == "SUCCESS"])
            category_total = len(results)
            report_data["category_breakdown"][category] = {
                "total": category_total,
                "successful": category_success,
                "failed": category_total - category_success,
                "success_rate": round((category_success / category_total * 100) if category_total > 0 else 0, 2)
            }
        
        # Save JSON report
        with open(REPORT_FILE, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        # Generate HTML report
        self.generate_html_report(report_data)
        
        print(f"📊 JSON Report saved: {REPORT_FILE}")
        print(f"🌐 HTML Report saved: {REPORT_HTML}")
        
        return report_data

    def generate_html_report(self, report_data: Dict):
        """Generate HTML report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>API Test Report - {REPORT_TIMESTAMP}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .card {{ background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 5px; flex: 1; }}
        .success {{ color: #28a745; }}
        .failure {{ color: #dc3545; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .status-success {{ background-color: #d4edda; }}
        .status-failure {{ background-color: #f8d7da; }}
        .category-section {{ margin: 30px 0; }}
        .expandable {{ cursor: pointer; }}
        .details {{ display: none; background: #f8f9fa; padding: 10px; }}
    </style>
    <script>
        function toggleDetails(id) {{
            var element = document.getElementById(id);
            element.style.display = element.style.display === 'none' ? 'block' : 'none';
        }}
    </script>
</head>
<body>
    <div class="header">
        <h1>🔍 API Test Report</h1>
        <p>Generated: {report_data['test_summary']['timestamp']}</p>
        <p>Base URL: {report_data['test_summary']['base_url']}</p>
    </div>
    
    <div class="summary">
        <div class="card">
            <h3>📊 Overall Results</h3>
            <p><strong>Total Tests:</strong> {report_data['test_summary']['total_tests']}</p>
            <p class="success"><strong>Successful:</strong> {report_data['test_summary']['successful_tests']}</p>
            <p class="failure"><strong>Failed:</strong> {report_data['test_summary']['failed_tests']}</p>
            <p><strong>Success Rate:</strong> {report_data['test_summary']['success_rate']}%</p>
        </div>
        <div class="card">
            <h3>⏱️ Performance</h3>
            <p><strong>Avg Response Time:</strong> {report_data['test_summary']['avg_response_time']}s</p>
        </div>
    </div>
"""
        
        # Category breakdown
        html_content += "<div class='category-section'><h2>📂 Category Breakdown</h2>"
        for category, stats in report_data['category_breakdown'].items():
            html_content += f"""
            <div class="card">
                <h4>{category}</h4>
                <p>Total: {stats['total']} | Success: {stats['successful']} | Failed: {stats['failed']} | Rate: {stats['success_rate']}%</p>
            </div>
            """
        html_content += "</div>"
        
        # Detailed results table
        html_content += """
        <h2>📋 Detailed Test Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Response Time</th>
                    <th>Status Code</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for i, result in enumerate(report_data['detailed_results']):
            status_class = f"status-{result['status'].lower()}"
            html_content += f"""
                <tr class="{status_class}">
                    <td>{result['endpoint']}</td>
                    <td>{result['method']}</td>
                    <td>{result['status']}</td>
                    <td>{result.get('response_time', 'N/A')}s</td>
                    <td>{result.get('status_code', 'N/A')}</td>
                    <td>
                        <span class="expandable" onclick="toggleDetails('details-{i}')">Show Details</span>
                        <div id="details-{i}" class="details">
                            <strong>Error:</strong> {result.get('error_message', 'None')}<br>
                            <strong>Response Size:</strong> {result.get('response_size', 'N/A')} bytes<br>
                            <strong>Test Params:</strong> <pre>{json.dumps(result.get('test_params'), indent=2) if result.get('test_params') else 'None'}</pre>
                        </div>
                    </td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        </body>
        </html>
        """
        
        with open(REPORT_HTML, 'w') as f:
            f.write(html_content)

    def print_summary(self):
        """Print test summary to console"""
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.status == "SUCCESS"])
        failed_tests = len([r for r in self.results if r.status == "FAILURE"])
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*60)
        print("🎯 TEST SUMMARY")
        print("="*60)
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Successful: {successful_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        print("="*60)
        
        if failed_tests > 0:
            print("\n🔥 FAILED TESTS:")
            print("-"*40)
            for result in self.results:
                if result.status == "FAILURE":
                    print(f"❌ {result.method} {result.endpoint}")
                    print(f"   Error: {result.error_message}")
                    print()

def main():
    """Main function to run tests"""
    # Allow custom base URL via command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    
    # Create tester instance
    tester = APITester(base_url)
    
    try:
        # Run all tests
        total_time = tester.run_all_tests()
        
        # Generate reports
        report_data = tester.generate_report()
        
        # Print summary
        tester.print_summary()
        
        print(f"\n🏁 Testing completed in {total_time:.2f} seconds")
        print(f"📁 Reports saved in: {TEST_RESULTS_DIR}/")
        
        # Exit with error code if tests failed
        failed_count = len([r for r in tester.results if r.status == "FAILURE"])
        sys.exit(1 if failed_count > 0 else 0)
        
    except KeyboardInterrupt:
        print("\n⚠️ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
