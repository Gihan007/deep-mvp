# Contributing Guide

Welcome to the Get-Deep project! This guide provides everything you need to know about contributing to the codebase, from setting up your development environment to submitting pull requests.

## 🤝 Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.12+**: Required runtime environment
- **Docker & Docker Compose**: For local development and testing
- **Node.js 18+**: For frontend development
- **Git**: Version control system
- **IDE/Editor**: VS Code, PyCharm, or your preferred editor

### Development Environment Setup

1. **Fork and Clone the Repository**
   ```bash
   # Fork the repository on GitHub first
   git clone https://github.com/your-username/Get-Deep.git
   cd Get-Deep
   
   # Add upstream remote
   git remote add upstream https://github.com/original-repo/Get-Deep.git
   ```

2. **Set up Python Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Install development dependencies
   pip install -r requirements-dev.txt  # If exists
   pip install pytest pytest-asyncio black flake8 mypy
   ```

3. **Set up Environment Variables**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Add your API keys (required for development)
   # Edit .env with your actual API keys
   ```

4. **Start Development Services**
   ```bash
   # Start Neo4j database
   docker compose up neo4j -d
   
   # Verify database is running
   curl http://localhost:7474
   ```

5. **Run the Application**
   ```bash
   # Start the backend
   cd src/
   python run.py
   
   # In another terminal, start the frontend
   cd react-chatgpt_original/
   npm install
   npm run dev
   ```

## 🏗️ Code Architecture

### Project Structure Overview

Understanding the codebase structure is crucial for effective contributions:

```
Get-Deep/
├── src/                          # Backend source code
│   ├── app/                      # Main application
│   │   ├── graphs/              # AI agent implementations
│   │   ├── routes/              # API endpoints
│   │   ├── tools/               # AI tools and integrations
│   │   ├── models/              # Data models and LLM configs
│   │   ├── prompts/             # AI prompts and templates
│   │   └── utills/              # Utility functions
│   ├── config.py                # Configuration management
│   └── run.py                   # Application entry point
├── react-chatgpt_original/      # Frontend React app
├── docs/                        # Documentation
├── testing/                     # Test suites
└── scripts/                     # Utility scripts
```

### Key Components

1. **AI Agents** (`src/app/graphs/`): LangGraph-based conversational agents
2. **Tools System** (`src/app/tools/`): Extensible tool architecture
3. **API Layer** (`src/app/routes/`): FastAPI endpoints
4. **Configuration** (`src/config.py`): Environment-based configuration
5. **Database Layer** (`src/app/utills/`): Neo4j and vector store integrations

## 📝 Development Guidelines

### Code Style and Standards

#### Python Code Style

We follow PEP 8 with some modifications. Use these tools:

```bash
# Format code with Black
black src/ --line-length 100

# Check style with flake8
flake8 src/ --max-line-length=100 --ignore=E203,W503

# Type checking with mypy
mypy src/ --ignore-missing-imports
```

#### Code Style Rules

```python
# ✅ Good: Clear function names and docstrings
def calculate_financial_metrics(ticker: str, metrics: List[str]) -> Dict[str, float]:
    """
    Calculate specified financial metrics for a given ticker.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        metrics: List of metric names to calculate
        
    Returns:
        Dictionary mapping metric names to calculated values
        
    Raises:
        ValueError: If ticker is invalid or metrics list is empty
    """
    if not ticker or not metrics:
        raise ValueError("Ticker and metrics must be provided")
    
    results = {}
    for metric in metrics:
        results[metric] = _calculate_metric(ticker, metric)
    
    return results

# ❌ Bad: Unclear names and no documentation
def calc(t, m):
    r = {}
    for i in m:
        r[i] = do_calc(t, i)
    return r
```

#### TypeScript/React Code Style

```typescript
// ✅ Good: Proper interfaces and component structure
interface ChatMessageProps {
  message: Message;
  onEdit?: (messageId: string, newContent: string) => void;
  isLoading?: boolean;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ 
  message, 
  onEdit, 
  isLoading = false 
}) => {
  const [isEditing, setIsEditing] = useState(false);
  
  const handleSave = useCallback((newContent: string) => {
    onEdit?.(message.id, newContent);
    setIsEditing(false);
  }, [message.id, onEdit]);
  
  return (
    <div className={`message ${message.role}`}>
      {/* Component content */}
    </div>
  );
};
```

### Git Workflow

#### Branch Naming Convention

```bash
# Feature branches
git checkout -b feature/add-financial-calculator
git checkout -b feature/improve-agent-routing

# Bug fixes
git checkout -b fix/neo4j-connection-timeout
git checkout -b fix/frontend-memory-leak

# Documentation
git checkout -b docs/update-api-reference
git checkout -b docs/add-deployment-guide

# Refactoring
git checkout -b refactor/simplify-tool-initialization
git checkout -b refactor/extract-common-utilities
```

#### Commit Message Format

Follow the Conventional Commits specification:

```bash
# Format: <type>(<scope>): <description>

# Examples:
git commit -m "feat(agents): add new report generation capabilities"
git commit -m "fix(api): resolve timeout issues in deep chat endpoint" 
git commit -m "docs(readme): update installation instructions"
git commit -m "test(tools): add unit tests for financial calculator"
git commit -m "refactor(database): simplify Neo4j connection management"
```

#### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   git push -u origin feature/your-feature-name
   ```

2. **Make Changes and Test**
   ```bash
   # Make your changes
   # Run tests
   pytest testing/ -v
   
   # Check code style
   black src/ --check
   flake8 src/
   ```

3. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat(component): add new functionality"
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request**
   - Use the PR template
   - Include clear description of changes
   - Reference any related issues
   - Add screenshots for UI changes

## 🧩 Adding New Features

### Adding a New AI Tool

1. **Create Tool Class**
   ```python
   # src/app/tools/my_new_tool.py
   from langchain.tools import BaseTool
   from typing import Optional
   from pydantic import Field
   
   class MyNewTool(BaseTool):
       name: str = "my_new_tool"
       description: str = """
       Detailed description of what this tool does.
       Include parameters and expected usage.
       """
       
       # Tool-specific configuration
       api_key: Optional[str] = Field(default=None)
       max_results: int = Field(default=10)
       
       def _run(self, query: str, **kwargs) -> str:
           """Implement tool functionality"""
           try:
               # Your tool logic here
               result = self.process_query(query, **kwargs)
               return self.format_result(result)
           except Exception as e:
               return f"Error in {self.name}: {str(e)}"
       
       def process_query(self, query: str, **kwargs):
           """Core tool functionality"""
           # Implement your tool's main logic
           pass
       
       def format_result(self, result):
           """Format output for agent consumption"""
           # Return structured, agent-friendly output
           pass
   ```

2. **Register Tool in Initializer**
   ```python
   # src/app/tools/__init__.py
   from .my_new_tool import MyNewTool
   
   def initialize_external_api_tools(config):
       tools = []
       
       # Add your tool
       if hasattr(config, 'MY_NEW_TOOL_API_KEY') and config.MY_NEW_TOOL_API_KEY:
           tools.append(MyNewTool(
               api_key=config.MY_NEW_TOOL_API_KEY,
               max_results=getattr(config, 'MY_NEW_TOOL_MAX_RESULTS', 10)
           ))
       
       return tools
   ```

3. **Add Configuration Options**
   ```python
   # src/config.py
   class Config:
       # Add tool configuration
       MY_NEW_TOOL_API_KEY = os.environ.get('MY_NEW_TOOL_API_KEY')
       MY_NEW_TOOL_MAX_RESULTS = int(os.environ.get('MY_NEW_TOOL_MAX_RESULTS', '10'))
   ```

4. **Write Tests**
   ```python
   # testing/code_testing/tool_tests/test_my_new_tool.py
   import pytest
   from unittest.mock import Mock, patch
   from src.app.tools.my_new_tool import MyNewTool
   
   class TestMyNewTool:
       
       @pytest.fixture
       def tool(self):
           return MyNewTool(api_key="test_key")
       
       def test_basic_functionality(self, tool):
           result = tool._run("test query")
           assert isinstance(result, str)
           assert len(result) > 0
       
       def test_error_handling(self, tool):
           with patch.object(tool, 'process_query', side_effect=Exception("Test error")):
               result = tool._run("test query")
               assert "Error in my_new_tool" in result
   ```

### Adding a New API Endpoint

1. **Create Router**
   ```python
   # src/app/routes/my_new_router.py
   from fastapi import APIRouter, HTTPException, Depends
   from pydantic import BaseModel
   from typing import Optional
   
   router = APIRouter()
   
   class MyRequest(BaseModel):
       parameter1: str
       parameter2: Optional[int] = None
   
   class MyResponse(BaseModel):
       result: str
       metadata: dict
   
   @router.post("/my-endpoint", response_model=MyResponse)
   async def my_endpoint(request: MyRequest):
       """
       Process request and return response.
       
       - **parameter1**: Description of parameter1
       - **parameter2**: Optional parameter description
       """
       try:
           # Process the request
           result = process_request(request)
           
           return MyResponse(
               result=result["data"],
               metadata=result["metadata"]
           )
       
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))
   
   def process_request(request: MyRequest) -> dict:
       """Business logic for the endpoint"""
       # Implement your endpoint logic
       return {
           "data": f"Processed: {request.parameter1}",
           "metadata": {"param2": request.parameter2}
       }
   ```

2. **Register Router**
   ```python
   # src/app/__init__.py
   from app.routes.my_new_router import router as my_new_router
   
   # In create_app function:
   app.include_router(my_new_router, tags=["my-feature"])
   ```

3. **Add Tests**
   ```python
   # testing/api_testing/test_my_new_endpoint.py
   import pytest
   import httpx
   
   @pytest.mark.asyncio
   async def test_my_endpoint():
       async with httpx.AsyncClient(base_url="http://localhost:8080") as client:
           response = await client.post("/my-endpoint", json={
               "parameter1": "test_value",
               "parameter2": 42
           })
           
           assert response.status_code == 200
           data = response.json()
           assert "result" in data
           assert "metadata" in data
   ```

### Adding a New Agent

1. **Create Agent Class**
   ```python
   # src/app/graphs/My_New_Agent_Graph.py
   from langgraph.graph import StateGraph, END, START
   from typing import List, Optional, Dict, Any, Annotated
   from langchain_core.messages import AnyMessage, add_messages
   from typing_extensions import TypedDict
   
   class MyNewAgentState(TypedDict):
       messages: Annotated[List[AnyMessage], add_messages]
       sender: Optional[str]
       # Add agent-specific state fields
   
   class MyNewAgent_ChatQABot:
       def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store):
           self.llm = llm
           self.config = config
           self.graphdb_vector_store = graphdb_vector_store
           self.chromadb_vector_store = chromadb_vector_store
           
           # Initialize agent-specific components
           self.tools = self._initialize_tools()
           self.graph = self._build_graph()
       
       def _initialize_tools(self):
           """Initialize tools specific to this agent"""
           # Return list of tools for this agent
           pass
       
       def _build_graph(self):
           """Build the LangGraph workflow"""
           workflow = StateGraph(MyNewAgentState)
           
           # Add nodes and edges
           workflow.add_node("agent", self._agent_node)
           workflow.add_edge(START, "agent")
           workflow.add_edge("agent", END)
           
           return workflow.compile()
       
       def _agent_node(self, state: MyNewAgentState):
           """Main agent logic"""
           # Implement agent behavior
           pass
       
       async def run(self, message: str, session_id: str):
           """Run the agent"""
           # Implement run logic
           pass
   ```

2. **Register Agent**
   ```python
   # src/config.py
   MY_NEW_AGENT_BOT_TYPE = os.environ.get('MY_NEW_AGENT_BOT_TYPE', 'My_New_Agent_Graph')
   
   # src/app/__init__.py
   from app.graphs.My_New_Agent_Graph import MyNewAgent_ChatQABot
   
   # In create_app function:
   if MY_NEW_AGENT_BOT_TYPE == "My_New_Agent_Graph":
       app.my_new_agent = MyNewAgent_ChatQABot(llm, config, graphdb_vector_store, chromadb_vector_store)
   ```

## 🐛 Bug Fixes

### Bug Report Process

1. **Search Existing Issues**: Check if the bug is already reported
2. **Create Detailed Issue**: Include reproduction steps, expected vs actual behavior
3. **Add Labels**: Use appropriate labels (bug, priority, component)
4. **Provide Context**: Environment, logs, screenshots if applicable

### Bug Fix Guidelines

```python
# ✅ Good: Clear fix with explanation
def calculate_pe_ratio(stock_price: float, earnings_per_share: float) -> float:
    """
    Calculate P/E ratio with proper error handling.
    
    Fixed: Division by zero error when EPS is 0 or negative.
    """
    if earnings_per_share <= 0:
        raise ValueError("Earnings per share must be positive")
    
    return stock_price / earnings_per_share

# ❌ Bad: Silent fix without documentation
def calculate_pe_ratio(stock_price: float, earnings_per_share: float) -> float:
    if earnings_per_share <= 0:
        return 0
    return stock_price / earnings_per_share
```

## 🧪 Testing Requirements

### Test Coverage Requirements

- **Unit Tests**: All new functions must have unit tests
- **Integration Tests**: New API endpoints require integration tests  
- **Coverage Threshold**: Maintain >80% test coverage
- **Performance Tests**: Critical paths should have performance tests

### Running Tests

```bash
# Run all tests
pytest testing/ -v

# Run specific test categories
pytest testing/api_testing/ -v          # API tests
pytest testing/code_testing/ -v        # Unit tests

# Run with coverage
pytest testing/ --cov=src --cov-report=html

# Run performance tests
pytest testing/performance_tests/ -v
```

### Test Writing Guidelines

```python
# ✅ Good: Descriptive test with proper setup and assertions
class TestFinancialCalculator:
    
    @pytest.fixture
    def calculator(self):
        return FinancialCalculator(config=test_config)
    
    @pytest.fixture
    def sample_data(self):
        return {
            "revenue": 1000000,
            "expenses": 800000,
            "shares_outstanding": 100000
        }
    
    def test_profit_margin_calculation(self, calculator, sample_data):
        """Test profit margin calculation with valid data"""
        
        # Act
        result = calculator.calculate_profit_margin(sample_data)
        
        # Assert
        expected_margin = (sample_data["revenue"] - sample_data["expenses"]) / sample_data["revenue"]
        assert abs(result - expected_margin) < 0.001
        assert 0 <= result <= 1
    
    def test_profit_margin_with_zero_revenue(self, calculator):
        """Test profit margin calculation with zero revenue"""
        
        invalid_data = {"revenue": 0, "expenses": 100}
        
        with pytest.raises(ValueError, match="Revenue must be greater than zero"):
            calculator.calculate_profit_margin(invalid_data)
```

## 📚 Documentation Requirements

### Code Documentation

All new code must include:

1. **Docstrings**: For all classes and functions
2. **Type Hints**: For all function parameters and returns
3. **Comments**: For complex logic
4. **README Updates**: If adding new features

### Documentation Style

```python
def process_financial_data(
    ticker: str, 
    metrics: List[str], 
    period: Optional[str] = "annual"
) -> Dict[str, Union[float, str]]:
    """
    Process financial data for a given ticker symbol.
    
    This function retrieves and processes financial metrics for analysis.
    It supports both annual and quarterly data periods.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
        metrics: List of metric names to calculate ['pe_ratio', 'debt_to_equity']
        period: Data period - 'annual' or 'quarterly' (default: 'annual')
    
    Returns:
        Dictionary containing calculated metrics with metric names as keys
        and calculated values as values. May include error messages for
        failed calculations.
    
    Raises:
        ValueError: If ticker is invalid or empty
        APIError: If external data source is unavailable
        
    Example:
        >>> result = process_financial_data('AAPL', ['pe_ratio', 'roe'])
        >>> print(result)
        {'pe_ratio': 28.5, 'roe': 0.15}
    """
```

## 🔍 Code Review Process

### Submitting for Review

1. **Self Review**: Review your own code first
2. **Run All Tests**: Ensure all tests pass
3. **Check Documentation**: Update docs if needed
4. **Create PR**: Use the PR template
5. **Request Reviewers**: Tag appropriate team members

### Review Checklist

**Code Quality**:
- [ ] Code follows style guidelines
- [ ] Functions are properly documented
- [ ] Error handling is appropriate
- [ ] No code smells or anti-patterns

**Testing**:
- [ ] New code has adequate test coverage
- [ ] All tests pass
- [ ] Edge cases are tested
- [ ] Performance implications considered

**Documentation**:
- [ ] Code is well-documented
- [ ] API documentation updated if needed
- [ ] README updated for new features

**Security**:
- [ ] No hardcoded secrets or credentials
- [ ] Input validation is present
- [ ] Security implications considered

## 🚀 Release Process

### Versioning Strategy

We use Semantic Versioning (SemVer):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible  
- **Patch** (0.0.X): Bug fixes, backward compatible

### Pre-Release Checklist

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] CHANGELOG is updated
- [ ] Version numbers are bumped
- [ ] Database migrations are tested
- [ ] Performance regressions checked

## 🆘 Getting Help

### Communication Channels

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Code Reviews**: For technical feedback on contributions

### Common Issues and Solutions

**Development Setup Issues**:
```bash
# Docker permission issues (Linux)
sudo usermod -a -G docker $USER
newgrp docker

# Python path issues
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Port already in use
sudo lsof -i :8080
kill -9 <PID>
```

**Testing Issues**:
```bash
# Database connection timeouts
docker compose restart neo4j

# Missing environment variables
cp .env.example .env.test
# Edit .env.test with test values
```

---

Thank you for contributing to Get-Deep! Your contributions help make this project better for everyone. If you have questions or need help, don't hesitate to reach out through the appropriate channels.
