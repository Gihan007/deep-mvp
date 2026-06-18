# 🧪 Comprehensive API Testing Suite

A complete testing framework for the Get-Deep API that tests all endpoints (excluding data injection and delete operations) and generates detailed success/failure reports.

## 📋 Overview

This testing suite provides:
- **Comprehensive Coverage**: Tests all major API endpoints
- **Detailed Reporting**: Generates both JSON and HTML reports
- **Performance Metrics**: Tracks response times and success rates
- **Error Analysis**: Detailed failure tracking and debugging information
- **Easy Execution**: Simple command-line interface

## 🏗️ Test Coverage

### Endpoints Tested

1. **Chat Endpoints**
   - `/api/qa_bot` - General QA bot
   - `/api/deep_qa_bot` - Deep analysis bot
   - `/api/deep_qa_bot_report` - Report generation bot

2. **Special Metrics Endpoints**
   - `/api/special_metrics/market_cap`
   - `/api/special_metrics/shares_outstanding`
   - `/api/special_metrics/stock_price`
   - `/api/special_metrics/intrinsic_to_mc`
   - `/api/special_metrics/intrinsic_value`
   - `/api/special_metrics/roic`
   - `/api/special_metrics/earnings_yield`
   - `/api/special_metrics/margin_of_safety`
   - `/api/special_metrics/investment_factor_ranking_table`

3. **Graph Database Endpoints**
   - `/api/graphdb/cypher` - Execute Cypher queries
   - `/api/graphdb/sectors` - List all sectors
   - `/api/graphdb/industries_when_sector_given` - Get industries by sector
   - `/api/graphdb/companies_when_industry_given` - Get companies by industry
   - `/api/graphdb/companies_when_sector_given` - Get companies by sector
   - `/api/graphdb/companies` - List all companies
   - `/api/graphdb/node_counts` - Get node statistics

4. **Central API Endpoints**
   - `/api/central/companies` - Get all companies
   - `/api/central/metrics` - Get available metrics
   - `/api/central/industries` - Get industries
   - `/api/central/aggregated-data` - Get aggregated financial data
   - `/api/central/financials/*` - Financial statements (Income, Balance, Cash Flow)
   - `/api/central/analysis/*` - Financial analysis (NOPAT, ROIC, etc.)
   - `/api/central/rankings/types` - Get ranking types

5. **Dynamic Table Endpoints**
   - `/api/dynamic_table/3StatementModel`
   - `/api/dynamic_table/FreeCashFlows`
   - `/api/dynamic_table/ReportedFinancials`
   - `/api/dynamic_table/Performance`
   - And more...

6. **KPI Endpoints**
   - `/api/kpi/properties` - Get KPI metadata

7. **Session Management**
   - `/api/sessions` - List sessions

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+** installed
2. **Get-Deep application** running
3. **Dependencies** installed

### Installation

1. **Install dependencies**:
   ```bash
   cd /home/sajeepan/Senzmate/Get-Deep/testing
   pip install -r requirements.txt
   ```

2. **Make script executable**:
   ```bash
   chmod +x comprehensive_api_test.py
   ```

### Running Tests

#### Basic Usage (localhost)
```bash
python comprehensive_api_test.py
```

#### Custom Base URL
```bash
python comprehensive_api_test.py http://your-server:8080
```

#### Background Execution
```bash
nohup python comprehensive_api_test.py > test_execution.log 2>&1 &
```

## 📊 Understanding the Reports

### Console Output
The script provides real-time progress updates:
```
🚀 Starting API Test Suite
📍 Base URL: http://localhost:8080
⏰ Timestamp: 20241216_142530
============================================================

📝 Testing Chat Endpoints
----------------------------------------
🔍 Testing POST /api/qa_bot
🔍 Testing POST /api/deep_qa_bot
...

🎯 TEST SUMMARY
============================================================
📊 Total Tests: 45
✅ Successful: 42
❌ Failed: 3
📈 Success Rate: 93.3%
============================================================
```

### JSON Report
**Location**: `test_results/api_test_report_[timestamp].json`

**Structure**:
```json
{
  "test_summary": {
    "timestamp": "20241216_142530",
    "base_url": "http://localhost:8080",
    "total_tests": 45,
    "successful_tests": 42,
    "failed_tests": 3,
    "success_rate": 93.33,
    "avg_response_time": 1.245
  },
  "category_breakdown": {
    "qa_bot": {
      "total": 2,
      "successful": 2,
      "failed": 0,
      "success_rate": 100.0
    },
    ...
  },
  "detailed_results": [...],
  "failed_tests_details": [...]
}
```

### HTML Report
**Location**: `test_results/api_test_report_[timestamp].html`

Features:
- **Visual Dashboard**: Color-coded success/failure indicators
- **Interactive Details**: Click to expand test details
- **Category Breakdown**: Organized by API category
- **Performance Metrics**: Response times and success rates
- **Error Analysis**: Detailed failure information

## 🔧 Configuration

### Environment Variables
```bash
# Set custom timeout (default: 30 seconds)
export API_TIMEOUT=60

# Set custom base URL
export API_BASE_URL=http://your-server:8080
```

### Script Modifications

#### Adding New Endpoints
1. Add test case to appropriate test suite method
2. Example:
```python
def test_your_endpoints(self):
    test_cases = [
        {
            "endpoint": "/api/your/endpoint",
            "method": "POST",
            "json": {"param": "value"}
        }
    ]
    
    for test_case in test_cases:
        result = self.test_endpoint(**test_case)
        self.add_result(result)
```

#### Customizing Test Data
Modify the `TEST_TICKERS` constant:
```python
TEST_TICKERS = ["AAPL", "MSFT", "GOOGL", "YOUR_TICKER"]
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Connection Refused
**Error**: `Connection refused`
**Solution**: Ensure the Get-Deep application is running
```bash
# Check if service is running
curl http://localhost:8080/health
```

#### 2. Timeout Errors
**Error**: `Request timeout`
**Solutions**:
- Increase timeout in script or via environment variable
- Check network connectivity
- Verify server performance

#### 3. Authentication Errors
**Error**: `401 Unauthorized`
**Solution**: Check if API keys or authentication is required

#### 4. Missing Dependencies
**Error**: `ModuleNotFoundError`
**Solution**:
```bash
pip install -r requirements.txt
```

### Debug Mode
Add debug logging to the script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance Optimization

### Concurrent Testing
The script supports concurrent test execution. Modify `MAX_CONCURRENT_TESTS` for better performance:

```python
MAX_CONCURRENT_TESTS = 10  # Increase for faster execution
```

### Selective Testing
To test only specific categories, comment out unwanted test suites in `run_all_tests()`:

```python
test_suites = [
    self.test_chat_endpoints,          # Keep
    # self.test_special_metrics_endpoints,  # Skip
    self.test_graphdb_endpoints,       # Keep
    # ...
]
```

## 🔍 Report Analysis

### Success Rate Benchmarks
- **90%+**: Excellent API health
- **80-89%**: Good, minor issues
- **70-79%**: Acceptable, needs attention
- **<70%**: Poor, requires investigation

### Response Time Analysis
- **<1s**: Excellent performance
- **1-3s**: Good performance
- **3-5s**: Acceptable performance
- **>5s**: Slow, needs optimization

### Common Failure Patterns
1. **404 Errors**: Missing endpoints or data
2. **500 Errors**: Server-side issues
3. **Timeout Errors**: Performance problems
4. **400 Errors**: Invalid request parameters

## 🔄 Continuous Integration

### GitHub Actions Example
```yaml
name: API Tests
on: [push, pull_request]

jobs:
  api-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r testing/requirements.txt
      - name: Run API tests
        run: python testing/comprehensive_api_test.py
```

### Scheduled Testing
Set up cron jobs for regular testing:
```bash
# Run tests daily at 2 AM
0 2 * * * cd /path/to/Get-Deep/testing && python comprehensive_api_test.py
```

## 📁 File Structure

```
testing/
├── comprehensive_api_test.py      # Main test script
├── requirements.txt               # Python dependencies
├── README_API_TESTING.md         # This documentation
├── test_results/                  # Generated reports
│   ├── api_test_report_*.json    # JSON reports
│   └── api_test_report_*.html    # HTML reports
└── api_testing/                   # Legacy test files
    ├── end_points_checker/        # Individual endpoint tests
    └── ...
```

## 🤝 Contributing

### Adding New Tests
1. Follow the existing pattern in test suite methods
2. Use descriptive test names
3. Include proper error handling
4. Add documentation for new endpoints

### Reporting Issues
When reporting issues, include:
- Test execution logs
- Generated JSON report
- System environment details
- Expected vs actual behavior

## 📚 Additional Resources

- **API Documentation**: `/docs/api/endpoints.md`
- **Example Usage**: `/docs/api/examples.md`
- **Legacy Tests**: `/testing/api_testing/`

## ⚡ Quick Reference

### Essential Commands
```bash
# Run all tests
python comprehensive_api_test.py

# Run with custom URL
python comprehensive_api_test.py http://production-server:8080

# Run in background
nohup python comprehensive_api_test.py > test.log 2>&1 &

# Check test results
ls -la test_results/

# View latest HTML report
open test_results/api_test_report_*.html
```

### Exit Codes
- **0**: All tests passed
- **1**: Some tests failed or error occurred

---

**Happy Testing! 🎉**

For questions or issues, check the troubleshooting section or review the generated reports for detailed error information.
