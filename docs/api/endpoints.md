# API Endpoints Reference

This document provides comprehensive documentation for all Get-Deep API endpoints. The API follows RESTful principles and returns JSON responses.

## 🌐 Base URL

- **Development**: `http://localhost:8080`
- **Production**: `http://<your-domain>:8080`

## 📋 Response Format

All API responses follow this standard format:

```json
{
  "status": "success|error",
  "data": <response_data>,
  "message": "Optional message",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 🏥 Health & Monitoring Endpoints

### GET /health
**Purpose**: Basic health check endpoint

```bash
curl -X GET http://localhost:8080/health
```

**Response:**
```json
{
  "status": "ok"
}
```

### GET /ready
**Purpose**: Readiness check for deployment health monitoring

```bash
curl -X GET http://localhost:8080/ready
```

**Response:**
```json
{
  "status": "ready"
}
```

### HEAD /health, HEAD /ready
**Purpose**: Support for HEAD requests (used by health check tools like wget --spider)

## 💬 Chat Endpoints

### POST /general-chat
**Purpose**: General purpose conversational AI interactions

**Request Body:**
```json
{
  "message": "Your question here",
  "session_id": "optional-session-id",
  "stream": false
}
```

**Response:**
```json
{
  "response": "AI generated response",
  "session_id": "session-identifier",
  "tool_outputs": [],
  "conversation_history": []
}
```

**Example:**
```bash
curl -X POST http://localhost:8080/general-chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the current stock price of AAPL?",
    "session_id": "user-session-123"
  }'
```

### POST /deep-chat
**Purpose**: Advanced reasoning and complex problem-solving

**Request Body:**
```json
{
  "message": "Complex analytical question",
  "session_id": "optional-session-id",
  "deep_thinking_mode": true,
  "stream": false
}
```

**Response:**
```json
{
  "response": "Detailed analytical response",
  "session_id": "session-identifier",
  "reasoning_steps": [],
  "tool_outputs": [],
  "analysis_metadata": {}
}
```

### POST /report-generation
**Purpose**: Generate comprehensive reports and documents

**Request Body:**
```json
{
  "message": "Report generation request",
  "session_id": "optional-session-id",
  "report_type": "financial|analysis|summary",
  "output_format": "pdf|markdown|html"
}
```

**Response:**
```json
{
  "response": "Report content",
  "session_id": "session-identifier",
  "report_data": {
    "pdf_base64": "base64-encoded-pdf",
    "charts": [],
    "metadata": {}
  }
}
```

### POST /update-neo4j
**Purpose**: Database update and maintenance operations

**Request Body:**
```json
{
  "message": "Database update request",
  "session_id": "optional-session-id",
  "operation_type": "update|insert|delete|maintenance"
}
```

## 🗄️ Database Endpoints

### POST /data-inject
**Purpose**: Inject data into the Neo4j graph database

**Request Body:**
```json
{
  "data_source": "file|url|text",
  "content": "Data content or file path",
  "data_type": "10k|financial|document",
  "metadata": {
    "company": "Company Name",
    "year": "2024",
    "source": "SEC Filing"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "nodes_created": 150,
  "relationships_created": 200,
  "processing_time": "45.2s",
  "data_id": "injection-id-123"
}
```

### GET /neo4j-query
**Purpose**: Query the Neo4j graph database with Cypher

**Query Parameters:**
- `query` (required): Cypher query string
- `params` (optional): JSON-encoded parameters

**Example:**
```bash
curl -X GET "http://localhost:8080/neo4j-query?query=MATCH (n:Company) RETURN n LIMIT 5"
```

**Response:**
```json
{
  "results": [
    {
      "n": {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "sector": "Technology"
      }
    }
  ],
  "summary": {
    "query_time": "0.12s",
    "records_returned": 5
  }
}
```

### POST /neo4j-query
**Purpose**: Execute complex Cypher queries with parameters

**Request Body:**
```json
{
  "query": "MATCH (c:Company {ticker: $ticker}) RETURN c",
  "parameters": {
    "ticker": "AAPL"
  },
  "read_only": true
}
```

## 📊 Financial Data Endpoints

### GET /special-metrics/{ticker}
**Purpose**: Get calculated financial metrics for a specific company

**Path Parameters:**
- `ticker`: Stock ticker symbol (e.g., AAPL, MSFT)

**Query Parameters:**
- `metrics`: Comma-separated list of metrics
- `years`: Number of years of historical data

**Example:**
```bash
curl -X GET "http://localhost:8080/special-metrics/AAPL?metrics=pe_ratio,debt_to_equity&years=5"
```

**Response:**
```json
{
  "ticker": "AAPL",
  "metrics": {
    "pe_ratio": {
      "current": 28.5,
      "historical": [25.2, 26.8, 30.1, 28.9, 28.5]
    },
    "debt_to_equity": {
      "current": 1.73,
      "historical": [1.45, 1.52, 1.67, 1.71, 1.73]
    }
  },
  "last_updated": "2024-01-01T00:00:00Z"
}
```

### POST /special-metrics/refresh
**Purpose**: Refresh financial metrics cache for multiple tickers

**Request Body:**
```json
{
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "source": "alphavantage|yahoo",
  "force_refresh": false
}
```

### GET /dynamic-table/{table_type}
**Purpose**: Get dynamically generated financial tables

**Path Parameters:**
- `table_type`: Type of table (rankings, comparisons, metrics)

**Available Tables:**
- `investment-factor-ranking`: Company ranking by investment factors
- `sector-analysis`: Sector-wise performance analysis
- `peer-comparison`: Peer company comparisons

## 📝 Session Management

### GET /sessions/{session_id}
**Purpose**: Retrieve session information and history

**Response:**
```json
{
  "session_id": "session-123",
  "created_at": "2024-01-01T00:00:00Z",
  "last_activity": "2024-01-01T01:00:00Z",
  "message_count": 15,
  "agent_type": "general",
  "messages": []
}
```

### DELETE /sessions/{session_id}
**Purpose**: Delete a specific session

### GET /sessions
**Purpose**: List all sessions for a user

**Query Parameters:**
- `limit`: Number of sessions to return (default: 50)
- `offset`: Offset for pagination (default: 0)
- `agent_type`: Filter by agent type

## 📈 KPI & Metrics Endpoints

### GET /kpi-metrics/overview
**Purpose**: Get system-wide KPI metrics

**Response:**
```json
{
  "system_metrics": {
    "total_sessions": 1250,
    "active_sessions": 45,
    "avg_response_time": "2.3s",
    "total_queries": 15800
  },
  "agent_metrics": {
    "general_agent": {
      "usage_percentage": 45.2,
      "avg_response_time": "1.8s"
    },
    "deep_agent": {
      "usage_percentage": 25.3,
      "avg_response_time": "4.1s"
    }
  }
}
```

### GET /kpi-metrics/financial
**Purpose**: Get financial data processing metrics

## 🔧 Central API Endpoint

### POST /central-api
**Purpose**: Unified endpoint for complex multi-step operations

**Request Body:**
```json
{
  "operation": "comprehensive_analysis",
  "parameters": {
    "ticker": "AAPL",
    "analysis_type": "full",
    "include_charts": true,
    "output_format": "pdf"
  },
  "session_id": "optional-session-id"
}
```

## ⚠️ Error Responses

### Standard Error Format

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "ticker",
      "issue": "Required field missing"
    }
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `AUTHENTICATION_ERROR` | 401 | Authentication required |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `DATABASE_ERROR` | 503 | Database connection issue |

## 🔐 Authentication

Currently, the API does not require authentication for development environments. In production deployments, implement:

- API key authentication
- JWT token validation
- Role-based access control (RBAC)

## 📊 Rate Limiting

Default rate limits (configurable):
- 100 requests per minute per IP
- 1000 requests per hour per session
- Special limits for computationally expensive endpoints

## 📱 WebSocket Endpoints

For real-time streaming responses:

### WS /stream/chat
**Purpose**: Real-time streaming chat responses

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8080/stream/chat');
```

---

For detailed examples and integration guides, see the [API Examples](examples.md) documentation.
