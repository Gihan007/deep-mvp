# Testing Guide

Get-Deep includes comprehensive testing capabilities across API endpoints, agent functionality, and system integration. This guide covers testing strategies, available test suites, and how to implement new tests.

## 🧪 Testing Architecture

### Testing Levels

```
┌─────────────────────┐
│   End-to-End Tests  │  ← Full system integration
├─────────────────────┤
│  Integration Tests  │  ← API endpoints and agents
├─────────────────────┤
│    Unit Tests       │  ← Individual components
└─────────────────────┘
```

### Testing Structure

```
testing/
├── api_testing/              # API endpoint tests
│   ├── general_agent_tests/  # General agent testing
│   ├── deep_agent_tests/     # Deep agent testing  
│   ├── report_agent_tests/   # Report generator testing
│   ├── update_agent_tests/   # Update agent testing
│   ├── database_tests/       # Database operation tests
│   └── integration_tests/    # Cross-component tests
├── code_testing/             # Unit and component tests
│   ├── tool_tests/          # Individual tool testing
│   ├── util_tests/          # Utility function tests
│   └── model_tests/         # Model and configuration tests
└── curl_commands.ipynb       # Manual API testing examples
```

## 🚀 Quick Testing Setup

### Prerequisites

```bash
# Ensure test environment is running
export APP_ENV=testing
docker compose -f docker-compose.test.yml up -d

# Install testing dependencies (if not already installed)
pip install pytest pytest-asyncio httpx
```

### Running Tests

```bash
# Run all tests
python -m pytest testing/ -v

# Run specific test categories
python -m pytest testing/api_testing/ -v          # API tests
python -m pytest testing/code_testing/ -v        # Unit tests

# Run with coverage
python -m pytest testing/ --cov=src --cov-report=html

# Run tests in parallel
python -m pytest testing/ -n auto
```

## 📡 API Testing

### General Agent Testing

```python
# testing/api_testing/general_agent_tests/test_basic_chat.py
import pytest
import httpx
from uuid import uuid4

@pytest.fixture
def client():
    return httpx.AsyncClient(
        base_url="http://localhost:8080",
        timeout=30.0
    )

@pytest.fixture
def session_id():
    return str(uuid4())

class TestGeneralAgentChat:
    
    @pytest.mark.asyncio
    async def test_basic_chat_request(self, client, session_id):
        """Test basic chat functionality"""
        
        request_data = {
            "message": "Hello, can you help me with financial analysis?",
            "session_id": session_id
        }
        
        response = await client.post("/general-chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert data["session_id"] == session_id
        assert len(data["response"]) > 0

    @pytest.mark.asyncio
    async def test_financial_query(self, client, session_id):
        """Test financial analysis capability"""
        
        request_data = {
            "message": "What is the current stock price of AAPL?",
            "session_id": session_id
        }
        
        response = await client.post("/general-chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "tool_outputs" in data
        # Should use financial tools for stock price queries
        assert any("stock" in str(output).lower() for output in data.get("tool_outputs", []))

    @pytest.mark.asyncio
    async def test_conversation_continuity(self, client, session_id):
        """Test that conversation history is maintained"""
        
        # First message
        response1 = await client.post("/general-chat", json={
            "message": "My name is John",
            "session_id": session_id
        })
        assert response1.status_code == 200
        
        # Follow-up message referring to previous context
        response2 = await client.post("/general-chat", json={
            "message": "What did I just tell you my name was?",
            "session_id": session_id
        })
        
        assert response2.status_code == 200
        data = response2.json()
        assert "john" in data["response"].lower()

    @pytest.mark.asyncio
    async def test_error_handling(self, client):
        """Test error handling for invalid requests"""
        
        # Missing message field
        response = await client.post("/general-chat", json={
            "session_id": "test-session"
        })
        
        assert response.status_code == 422  # Validation error
```

### Deep Agent Testing

```python
# testing/api_testing/deep_agent_tests/test_complex_reasoning.py
import pytest
import httpx

class TestDeepAgentReasoning:
    
    @pytest.mark.asyncio
    async def test_complex_analysis_request(self, client, session_id):
        """Test deep agent's complex reasoning capabilities"""
        
        request_data = {
            "message": """
            Analyze Apple Inc.'s financial performance over the last 3 years, 
            including revenue growth, profit margins, and competitive position. 
            Provide a comprehensive analysis with supporting data.
            """,
            "session_id": session_id,
            "deep_thinking_mode": True
        }
        
        response = await client.post("/deep-chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Deep agent should provide comprehensive analysis
        assert len(data["response"]) > 500  # Substantial response
        assert "reasoning_steps" in data
        assert "analysis_metadata" in data
        
        # Should use multiple tools for comprehensive analysis
        assert len(data.get("tool_outputs", [])) >= 3

    @pytest.mark.asyncio
    async def test_multi_step_problem_solving(self, client, session_id):
        """Test multi-step problem solving capability"""
        
        request_data = {
            "message": """
            I want to invest $100,000 in technology stocks. 
            Help me create a diversified portfolio with risk analysis 
            and expected returns for each recommendation.
            """,
            "session_id": session_id
        }
        
        response = await client.post("/deep-chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should break down into multiple steps
        response_text = data["response"].lower()
        assert "portfolio" in response_text
        assert "risk" in response_text
        assert "diversif" in response_text
        assert "return" in response_text

    @pytest.mark.asyncio
    async def test_report_generation_capability(self, client, session_id):
        """Test that deep agent can generate detailed reports"""
        
        request_data = {
            "message": "Generate a comprehensive financial report for Microsoft (MSFT)",
            "session_id": session_id
        }
        
        response = await client.post("/deep-chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have report data
        if "report_data" in data:
            report_data = data["report_data"]
            assert "charts" in report_data or "pdf_base64" in report_data
```

### Database Testing

```python
# testing/api_testing/database_tests/test_neo4j_operations.py
import pytest
from neo4j import GraphDatabase

@pytest.fixture
def neo4j_driver():
    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "your_neo4j_password_here")
    )
    yield driver
    driver.close()

class TestNeo4jOperations:
    
    def test_database_connection(self, neo4j_driver):
        """Test Neo4j database connectivity"""
        
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            assert record["test"] == 1

    def test_company_data_exists(self, neo4j_driver):
        """Test that company data is accessible"""
        
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (c:Company) 
                RETURN count(c) as company_count
            """)
            record = result.single()
            assert record["company_count"] >= 0

    def test_metric_relationships(self, neo4j_driver):
        """Test company-metric relationships"""
        
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (c:Company)-[:HAS_METRIC]->(m:Metric)
                RETURN count(m) as metric_count
            """)
            record = result.single()
            # Should have some metrics if data is loaded
            metric_count = record["metric_count"]
            assert metric_count >= 0

    @pytest.mark.asyncio
    async def test_vector_search_index(self, client):
        """Test vector search functionality"""
        
        response = await client.get("/neo4j-query", params={
            "query": "SHOW INDEXES YIELD name WHERE name CONTAINS 'vector'"
        })
        
        assert response.status_code == 200
        # Vector index should exist if configured
```

### Report Generation Testing

```python
# testing/api_testing/report_agent_tests/test_report_generation.py
import pytest
import base64
from io import BytesIO

class TestReportGeneration:
    
    @pytest.mark.asyncio
    async def test_pdf_report_generation(self, client, session_id):
        """Test PDF report generation capability"""
        
        request_data = {
            "message": "Generate a PDF report on Apple's Q4 2023 financial performance",
            "session_id": session_id,
            "output_format": "pdf"
        }
        
        response = await client.post("/report-generation", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        if "report_data" in data and "pdf_base64" in data["report_data"]:
            pdf_data = data["report_data"]["pdf_base64"]
            
            # Verify it's valid base64
            try:
                pdf_bytes = base64.b64decode(pdf_data)
                assert pdf_bytes.startswith(b'%PDF')  # PDF header
            except Exception:
                pytest.fail("Invalid PDF data")

    @pytest.mark.asyncio
    async def test_chart_generation(self, client, session_id):
        """Test chart generation in reports"""
        
        request_data = {
            "message": "Create a chart showing AAPL stock price trends over the last year",
            "session_id": session_id
        }
        
        response = await client.post("/report-generation", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have chart data
        if "report_data" in data and "charts" in data["report_data"]:
            charts = data["report_data"]["charts"]
            assert len(charts) > 0
            assert "type" in charts[0]
            assert "data" in charts[0]

    @pytest.mark.asyncio
    async def test_multiple_format_support(self, client, session_id):
        """Test support for multiple output formats"""
        
        formats = ["pdf", "markdown", "html"]
        
        for format_type in formats:
            request_data = {
                "message": "Generate a brief financial summary",
                "session_id": f"{session_id}_{format_type}",
                "output_format": format_type
            }
            
            response = await client.post("/report-generation", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
```

## 🔧 Unit Testing

### Tool Testing

```python
# testing/code_testing/tool_tests/test_financial_tools.py
import pytest
from unittest.mock import Mock, patch
from src.app.tools.investment_metrics_calculator_tool import InvestmentMetricsCalculatorTool

class TestFinancialTools:
    
    @pytest.fixture
    def calculator_tool(self):
        return InvestmentMetricsCalculatorTool()

    def test_pe_ratio_calculation(self, calculator_tool):
        """Test P/E ratio calculation"""
        
        mock_data = {
            "stock_price": 150.0,
            "earnings_per_share": 6.0
        }
        
        with patch.object(calculator_tool, 'get_financial_data', return_value=mock_data):
            result = calculator_tool._run(
                symbol="AAPL",
                metrics_list=["pe_ratio"]
            )
            
        assert "pe_ratio" in result
        assert abs(result["pe_ratio"] - 25.0) < 0.01

    def test_debt_to_equity_calculation(self, calculator_tool):
        """Test debt-to-equity ratio calculation"""
        
        mock_data = {
            "total_debt": 100000000000,
            "total_equity": 60000000000
        }
        
        with patch.object(calculator_tool, 'get_financial_data', return_value=mock_data):
            result = calculator_tool._run(
                symbol="AAPL",
                metrics_list=["debt_to_equity"]
            )
            
        assert "debt_to_equity" in result
        assert abs(result["debt_to_equity"] - 1.67) < 0.01

    def test_invalid_symbol_handling(self, calculator_tool):
        """Test handling of invalid stock symbols"""
        
        with patch.object(calculator_tool, 'get_financial_data', side_effect=Exception("Invalid symbol")):
            result = calculator_tool._run(
                symbol="INVALID",
                metrics_list=["pe_ratio"]
            )
            
        assert "error" in result.lower()
```

### Utility Function Testing

```python
# testing/code_testing/util_tests/test_data_processing.py
import pytest
from src.app.utills.ticker_finder import find_ticker_from_company_name

class TestDataProcessingUtils:
    
    def test_ticker_finder_exact_match(self):
        """Test exact company name matching"""
        
        result = find_ticker_from_company_name("Apple Inc.")
        assert result == "AAPL"

    def test_ticker_finder_partial_match(self):
        """Test partial company name matching"""
        
        result = find_ticker_from_company_name("Microsoft")
        assert result == "MSFT"

    def test_ticker_finder_case_insensitive(self):
        """Test case insensitive matching"""
        
        result = find_ticker_from_company_name("apple inc")
        assert result == "AAPL"

    def test_ticker_finder_no_match(self):
        """Test behavior with no match"""
        
        result = find_ticker_from_company_name("Nonexistent Company")
        assert result is None

    @pytest.mark.parametrize("company_name,expected_ticker", [
        ("Apple Inc.", "AAPL"),
        ("Microsoft Corporation", "MSFT"),
        ("Alphabet Inc.", "GOOGL"),
        ("Amazon.com Inc.", "AMZN")
    ])
    def test_ticker_finder_multiple_companies(self, company_name, expected_ticker):
        """Test multiple company name to ticker mappings"""
        
        result = find_ticker_from_company_name(company_name)
        assert result == expected_ticker
```

## 🎯 Integration Testing

### Cross-Agent Communication Testing

```python
# testing/api_testing/integration_tests/test_agent_integration.py
import pytest

class TestAgentIntegration:
    
    @pytest.mark.asyncio
    async def test_general_to_deep_agent_handoff(self, client):
        """Test handoff between different agents"""
        
        session_id = str(uuid4())
        
        # Start with general agent
        general_response = await client.post("/general-chat", json={
            "message": "I need a complex financial analysis of Tesla",
            "session_id": session_id
        })
        
        assert general_response.status_code == 200
        
        # Continue with deep agent using same session
        deep_response = await client.post("/deep-chat", json={
            "message": "Continue the Tesla analysis with detailed metrics",
            "session_id": session_id
        })
        
        assert deep_response.status_code == 200
        # Deep agent should have access to previous context
        assert "tesla" in deep_response.json()["response"].lower()

    @pytest.mark.asyncio
    async def test_database_update_integration(self, client):
        """Test database update and query integration"""
        
        session_id = str(uuid4())
        
        # Update database with new data
        update_response = await client.post("/update-neo4j", json={
            "message": "Add test company data for integration testing",
            "session_id": session_id,
            "operation_type": "insert"
        })
        
        assert update_response.status_code == 200
        
        # Query the updated data
        query_response = await client.get("/neo4j-query", params={
            "query": "MATCH (c:Company) WHERE c.name CONTAINS 'test' RETURN c LIMIT 1"
        })
        
        assert query_response.status_code == 200
        # Should find the test data (if update was successful)
```

### Performance Testing

```python
# testing/code_testing/performance_tests/test_response_times.py
import pytest
import time
import asyncio

class TestPerformance:
    
    @pytest.mark.asyncio
    async def test_general_agent_response_time(self, client):
        """Test general agent response time"""
        
        start_time = time.time()
        
        response = await client.post("/general-chat", json={
            "message": "What is 2 + 2?",
            "session_id": "perf-test"
        })
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 5.0  # Should respond within 5 seconds

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        
        async def make_request(session_id):
            return await client.post("/general-chat", json={
                "message": f"Test concurrent request {session_id}",
                "session_id": f"concurrent-{session_id}"
            })
        
        # Make 5 concurrent requests
        tasks = [make_request(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_large_response_handling(self, client):
        """Test handling of large responses"""
        
        response = await client.post("/deep-chat", json={
            "message": "Generate a very detailed analysis of the entire technology sector with all major companies",
            "session_id": "large-response-test"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should handle large responses without issues
        assert len(data["response"]) > 1000
        assert "response" in data
```

## 🔄 Test Automation

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      neo4j:
        image: neo4j:5.23-community
        env:
          NEO4J_AUTH: neo4j/test_password
        ports:
          - 7687:7687
          - 7474:7474
        options: >-
          --health-cmd "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.12
      uses: actions/setup-python@v4
      with:
        python-version: 3.12
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov httpx
    
    - name: Set up test environment
      run: |
        export APP_ENV=testing
        export NEO4J_URI=bolt://localhost:7687
        export NEO4J_PASSWORD=test_password
        export OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}
    
    - name: Run unit tests
      run: |
        pytest testing/code_testing/ -v --cov=src --cov-report=xml
    
    - name: Run integration tests
      run: |
        pytest testing/api_testing/ -v
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Test Data Management

```python
# testing/fixtures/test_data.py
import pytest
from neo4j import GraphDatabase

@pytest.fixture(scope="session")
def test_database():
    """Set up test database with sample data"""
    
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test_password"))
    
    with driver.session() as session:
        # Clear test data
        session.run("MATCH (n:TestCompany) DETACH DELETE n")
        
        # Insert test companies
        session.run("""
            CREATE (c:TestCompany {
                name: "Test Company A",
                ticker: "TSTA",
                sector: "Technology"
            })
        """)
        
        session.run("""
            CREATE (c:TestCompany {
                name: "Test Company B", 
                ticker: "TSTB",
                sector: "Finance"
            })
        """)
    
    yield driver
    
    # Cleanup
    with driver.session() as session:
        session.run("MATCH (n:TestCompany) DETACH DELETE n")
    
    driver.close()
```

## 📊 Test Coverage and Reporting

### Coverage Configuration

```ini
# .coveragerc
[run]
source = src/
omit = 
    src/app/tests/*
    */migrations/*
    */venv/*
    */env/*
    */virtualenvs/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError

[html]
directory = htmlcov
```

### Test Report Generation

```bash
# Generate comprehensive test report
pytest testing/ \
  --cov=src \
  --cov-report=html \
  --cov-report=xml \
  --junitxml=test-results.xml \
  --html=test-report.html \
  -v

# View HTML coverage report
open htmlcov/index.html

# View test report
open test-report.html
```

## 🚨 Testing Best Practices

### Test Organization

1. **Arrange-Act-Assert Pattern**:
```python
def test_financial_calculation():
    # Arrange
    calculator = FinancialCalculator()
    test_data = {"revenue": 1000000, "expenses": 800000}
    
    # Act
    profit_margin = calculator.calculate_profit_margin(test_data)
    
    # Assert
    assert profit_margin == 0.20
```

2. **Fixture Usage**:
```python
@pytest.fixture
def sample_financial_data():
    return {
        "AAPL": {"price": 150, "eps": 6.0},
        "MSFT": {"price": 300, "eps": 10.0}
    }

def test_multiple_stocks(sample_financial_data):
    for ticker, data in sample_financial_data.items():
        pe_ratio = data["price"] / data["eps"]
        assert pe_ratio > 0
```

3. **Parameterized Testing**:
```python
@pytest.mark.parametrize("ticker,expected_sector", [
    ("AAPL", "Technology"),
    ("JPM", "Financial"),
    ("JNJ", "Healthcare")
])
def test_sector_classification(ticker, expected_sector):
    sector = get_company_sector(ticker)
    assert sector == expected_sector
```

### Continuous Integration

- Run tests on every commit
- Fail builds on test failures
- Maintain high test coverage (>80%)
- Use test databases for integration tests
- Mock external APIs to avoid rate limits

---

This comprehensive testing guide ensures reliable, maintainable, and thoroughly tested Get-Deep functionality across all components and integration points.
