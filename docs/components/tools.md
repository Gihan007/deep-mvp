# Tools System Documentation

The Get-Deep platform features an extensive tool system with 20+ specialized tools that enable AI agents to perform complex tasks ranging from financial analysis to document processing. Each tool is designed to be modular, configurable, and easily extensible.

## 🛠️ Tool Architecture

### Tool Interface Pattern

All tools follow a consistent interface pattern:

```python
from typing import Any, Dict, Optional
from langchain.tools import BaseTool

class CustomTool(BaseTool):
    name: str = "tool_name"
    description: str = "Tool description for agent selection"
    
    def _run(self, **kwargs) -> Any:
        """Synchronous execution"""
        pass
    
    async def _arun(self, **kwargs) -> Any:
        """Asynchronous execution"""
        pass
```

### Tool Initialization System

Tools are initialized through a centralized system (`src/app/tools/__init__.py`):

```python
def initialize_all_tools(config, graphdb_vector_store=None, chromadb_vector_store=None):
    """Initialize all available tools based on configuration"""
    tools = []
    
    # Core tools (always available)
    tools.extend(initialize_core_tools())
    
    # Database-dependent tools
    if graphdb_vector_store:
        tools.extend(initialize_graph_tools(graphdb_vector_store))
    
    if chromadb_vector_store:
        tools.extend(initialize_vector_tools(chromadb_vector_store))
    
    # API-dependent tools
    tools.extend(initialize_external_api_tools(config))
    
    return tools
```

## 📊 Financial Analysis Tools

### Alpha Vantage Integration Tools

#### 1. Alpha Vantage Company Overview Tool (`alphavantage_company_overview_tool.py`)

**Purpose**: Retrieve comprehensive company information and fundamental data.

**Parameters**:
- `symbol` (required): Stock ticker symbol (e.g., "AAPL")

**Example Usage**:
```python
tool_result = company_overview_tool.run(symbol="AAPL")
```

**Response Structure**:
```json
{
  "Symbol": "AAPL",
  "Name": "Apple Inc",
  "Sector": "Technology",
  "Industry": "Consumer Electronics",
  "MarketCapitalization": "3000000000000",
  "PERatio": "28.5",
  "DividendYield": "0.44%"
}
```

#### 2. Alpha Vantage Daily Stock Tool (`alphavantage_daily_stock_tool.py`)

**Purpose**: Fetch daily stock price data with technical indicators.

**Parameters**:
- `symbol` (required): Stock ticker symbol
- `outputsize` (optional): "compact" (100 days) or "full" (20+ years)

**Features**:
- OHLCV data retrieval
- Volume analysis
- Price change calculations
- Technical indicator integration

#### 3. Alpha Vantage Intraday Stock Tool (`alphavantage_intraday_stock_tool.py`)

**Purpose**: Real-time and intraday stock price data.

**Parameters**:
- `symbol` (required): Stock ticker symbol  
- `interval` (required): "1min", "5min", "15min", "30min", "60min"
- `adjusted` (optional): True/False for adjusted prices
- `outputsize` (optional): Data range selection

#### 4. Alpha Vantage Market News Tool (`alphavantage_market_news_and_sentiment_tool.py`)

**Purpose**: Market news and sentiment analysis.

**Parameters**:
- `topics` (optional): News categories (earnings, financial_markets, etc.)
- `sort` (optional): "LATEST", "EARLIEST", "RELEVANCE"
- `limit` (optional): Number of articles (1-1000)

**Topics Available**:
```python
AVAILABLE_TOPICS = [
    'blockchain', 'earnings', 'financial_markets',
    'mergers_and_acquisitions', 'ipo', 'technology'
]
```

#### 5. Alpha Vantage Earnings Transcript Tool (`alphavantage_earnings_call_transcript_tool.py`)

**Purpose**: Access earnings call transcripts and analysis.

**Parameters**:
- `symbol` (required): Stock ticker symbol
- `year` (optional): Specific year filter
- `quarter` (optional): Specific quarter (Q1, Q2, Q3, Q4)

### Investment Analysis Tools

#### 6. Investment Metrics Calculator (`investment_metrics_calculator_tool.py`)

**Purpose**: Calculate comprehensive financial ratios and investment metrics.

**Key Metrics Calculated**:
- **Profitability Ratios**: ROE, ROA, Profit Margin, EBITDA Margin
- **Liquidity Ratios**: Current Ratio, Quick Ratio, Cash Ratio
- **Leverage Ratios**: Debt-to-Equity, Interest Coverage, Debt Service Coverage
- **Efficiency Ratios**: Asset Turnover, Inventory Turnover, Receivables Turnover
- **Valuation Ratios**: P/E, P/B, PEG, EV/EBITDA

**Usage Example**:
```python
metrics = investment_calculator.run(
    symbol="AAPL",
    metrics_list=["pe_ratio", "debt_to_equity", "roe", "current_ratio"]
)
```

#### 7. Investment Factor Ranking Table Tool (`investment_factor_ranking_table_tool.py`)

**Purpose**: Generate comparative ranking tables for investment analysis.

**Features**:
- Multi-company comparisons
- Sector-based rankings
- Custom weighting factors
- Historical trend analysis

**Ranking Factors**:
- Growth metrics
- Profitability scores
- Financial stability indicators
- Market performance metrics
- Risk assessments

## 🔍 Data Processing Tools

### Web Search Tools

#### 8. DuckDuckGo Search Tool (`duckduckgo_search_tool.py`)

**Purpose**: Web search with privacy-focused results.

**Parameters**:
- `query` (required): Search query string
- `max_results` (optional): Number of results (default: 5)
- `region` (optional): Geographic region for results

**Features**:
- Privacy-preserving search
- Real-time results
- Multiple result formats
- Geographic targeting

#### 9. Tavily Search Tool (`tavily_search_tool.py`)

**Purpose**: AI-optimized search for research and analysis.

**Parameters**:
- `query` (required): Search query
- `search_depth` (optional): "basic" or "advanced"
- `include_answer` (optional): Include AI-generated answer
- `include_raw_content` (optional): Include full page content

**Advanced Features**:
```python
tavily_config = {
    'max_results': config.TAVILY_MAX_RESULTS,
    'search_depth': 'advanced',
    'include_images': True,
    'include_answer': True
}
```

### Database Tools

#### 10. Graph DB Cypher Query Tool (`graph_db_cypher_query_tool.py`)

**Purpose**: Execute Cypher queries against Neo4j database.

**Parameters**:
- `query` (required): Cypher query string
- `parameters` (optional): Query parameters dictionary

**Example Queries**:
```cypher
-- Find companies by sector
MATCH (c:Company {sector: $sector}) 
RETURN c.name, c.ticker LIMIT 10

-- Complex relationship queries
MATCH (c:Company)-[r:HAS_METRIC]->(m:Metric {name: 'revenue'})
WHERE c.sector = 'Technology'
RETURN c.name, m.value ORDER BY m.value DESC
```

#### 11. Graph DB Vector Search Tool (`graph_db_vector_search_tool.py`)

**Purpose**: Semantic search using vector embeddings in Neo4j.

**Parameters**:
- `query` (required): Natural language search query
- `top_k` (optional): Number of results to return (default: 10)
- `similarity_threshold` (optional): Minimum similarity score

#### 12. Chroma Retrieval Tool (`chroma_retrieval_tool.py`)

**Purpose**: Vector-based document retrieval from ChromaDB.

**Features**:
- Semantic similarity search
- Metadata filtering
- Multi-modal search capabilities
- Context-aware retrieval

## 💻 System Tools

### Code Execution Tools

#### 13. Python REPL Tool (`python_repl_tool.py`)

**Purpose**: Execute Python code dynamically for calculations and analysis.

**Security Features**:
- Sandboxed execution environment
- Import restrictions
- Timeout limitations
- Output size limits

**Example Usage**:
```python
code = """
import pandas as pd
import numpy as np

# Calculate compound annual growth rate
def cagr(start_value, end_value, periods):
    return (end_value / start_value) ** (1/periods) - 1

result = cagr(100, 150, 3)
print(f"CAGR: {result:.2%}")
"""

result = python_repl.run(code)
```

#### 14. Bash Tool (`bash_tool.py`)

**Purpose**: Execute system commands for file operations and system tasks.

**Security Considerations**:
- Command whitelist
- Path restrictions
- User permission limits
- Output sanitization

### Visualization Tools

#### 15. Visualization Tool (`visualization_tool.py`)

**Purpose**: Generate charts, graphs, and visual representations of data.

**Chart Types Supported**:
- Line charts for time series
- Bar charts for comparisons  
- Pie charts for distributions
- Scatter plots for correlations
- Heatmaps for multi-dimensional data
- Candlestick charts for financial data

**Configuration**:
```python
chart_config = {
    'chart_type': 'line',
    'title': 'Stock Price Trend',
    'x_axis': 'Date',
    'y_axis': 'Price',
    'color_scheme': 'professional',
    'export_format': 'png'
}
```

## 🔄 Data Management Tools

#### 16. Update Graph Based on User Query (`update_graph_based_on_user_q.py`)

**Purpose**: Intelligent graph database updates based on natural language requests.

**Capabilities**:
- Natural language to Cypher translation
- Data validation before updates
- Rollback capabilities for failed operations
- Audit logging for all changes

#### 17. Graph DB Structured Data Query Tool (`graph_db_strctured_data_cypher_query_tool.py`)

**Purpose**: Query structured financial data with optimized Cypher patterns.

**Optimized Query Patterns**:
- Financial metric retrieval
- Time-series data queries
- Company relationship mapping
- Sector analysis queries

#### 18. Graph DB 10-K Data Query Tool (`graph_db_tenk_data_cypher_query_tool.py`)

**Purpose**: Specialized tool for querying SEC 10-K filing data.

**Query Types**:
- Financial statement data
- Risk factor analysis
- Business description extraction
- Management discussion queries

## 🔧 Tool Configuration

### Environment-Based Configuration

Tools are configured through environment variables and the central config system:

```python
# API Keys for external services
ALPHA_VANTAGE_API_KEY = "your-api-key"
TAVILY_API_KEY = "your-tavily-key"

# Tool-specific settings
TAVILY_MAX_RESULTS = 5
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Database connectivity
NEO4J_URI = "bolt://localhost:7687"
CHROMA_DB_PATH = "./databases/user_data"
```

### Tool Access Control

Different agents have access to different tool sets:

```python
# General Agent - Basic tools
GENERAL_AGENT_TOOLS = [
    'duckduckgo_search', 'tavily_search', 'python_repl',
    'graph_db_query_readonly', 'visualization_tool'
]

# Deep Agent - All tools
DEEP_AGENT_TOOLS = initialize_all_tools(config)

# Update Agent - Database modification tools
UPDATE_AGENT_TOOLS = [
    'graph_db_write', 'update_graph_tool', 'data_validation'
]

# Report Agent - Document generation tools  
REPORT_AGENT_TOOLS = [
    'visualization_tool', 'python_repl', 'graph_db_query',
    'investment_calculator', 'report_generator'
]
```

## 📈 Performance Optimization

### Caching Strategies

Many tools implement intelligent caching:

```python
class CachedTool(BaseTool):
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def _run(self, query: str) -> str:
        cache_key = hashlib.md5(query.encode()).hexdigest()
        
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_result
        
        result = self.execute_query(query)
        self.cache[cache_key] = (result, time.time())
        return result
```

### Async Support

All tools support asynchronous execution for better performance:

```python
async def _arun(self, **kwargs) -> Any:
    """Asynchronous execution with proper resource management"""
    async with aiohttp.ClientSession() as session:
        result = await self.fetch_data(session, **kwargs)
        return self.process_result(result)
```

## 🔌 Adding New Tools

### Tool Development Template

```python
from typing import Optional
from langchain.tools import BaseTool
from pydantic import Field

class CustomAnalysisTool(BaseTool):
    name: str = "custom_analysis"
    description: str = """
    Detailed description of what this tool does.
    Include parameters and expected outputs.
    """
    
    # Tool-specific configuration
    api_key: Optional[str] = Field(default=None)
    max_results: int = Field(default=10)
    
    def _run(self, query: str, **kwargs) -> str:
        """Implement your tool logic here"""
        try:
            result = self.perform_analysis(query, **kwargs)
            return self.format_result(result)
        except Exception as e:
            return f"Error in {self.name}: {str(e)}"
    
    async def _arun(self, query: str, **kwargs) -> str:
        """Async version of the tool"""
        return self._run(query, **kwargs)
    
    def perform_analysis(self, query: str, **kwargs):
        """Core tool functionality"""
        pass
    
    def format_result(self, result):
        """Format output for agent consumption"""
        pass
```

### Integration Steps

1. **Create Tool File**: Add new tool in `src/app/tools/`
2. **Update Tool Initializer**: Add to `__init__.py`
3. **Configure Access**: Define which agents can use the tool
4. **Add Documentation**: Include usage examples and parameters
5. **Test Integration**: Verify with different agents

### Best Practices

- **Clear Descriptions**: Tools should have detailed, agent-friendly descriptions
- **Error Handling**: Robust error handling with informative messages
- **Input Validation**: Validate all parameters before execution
- **Output Formatting**: Consistent, parseable output formats
- **Resource Management**: Proper cleanup of connections and resources
- **Security**: Input sanitization and access controls

---

This comprehensive tool system provides the foundation for Get-Deep's advanced AI capabilities, enabling agents to perform complex analysis, data processing, and system interactions while maintaining security and performance standards.
