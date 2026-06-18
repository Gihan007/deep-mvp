# API Examples and Usage Guide

This guide provides practical examples of using the Get-Deep API across different use cases and agent types.

## 🚀 Basic Examples

### Health Check
```bash
curl -X GET http://localhost:8080/health
# Response: {"status": "ok"}
```

### Simple Chat
```bash
curl -X POST http://localhost:8080/general-chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the current stock price of Apple?",
    "session_id": "example-session"
  }'
```

**Response:**
```json
{
  "response": "Apple (AAPL) is currently trading at $185.42, up $2.31 (+1.26%) today...",
  "session_id": "example-session",
  "tool_outputs": [
    {
      "tool_name": "alphavantage_daily_stock_tool",
      "output": {"symbol": "AAPL", "price": 185.42, "change": 2.31}
    }
  ]
}
```

## 🧠 Deep Agent Examples

### Complex Analysis
```bash
curl -X POST http://localhost:8080/deep-chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze Tesla investment potential with specific recommendations",
    "session_id": "deep-analysis",
    "deep_thinking_mode": true
  }'
```

**Response:**
```json
{
  "response": "# Tesla Investment Analysis\n\n## Summary\nMODERATE BUY with 12-15% upside potential...\n\n## Key Metrics\n• P/E Ratio: 45.2x\n• Target Price: $275-285\n• Risk Level: Medium-High",
  "reasoning_steps": [
    "Financial data collection",
    "Competitive analysis", 
    "Risk assessment",
    "Valuation modeling"
  ],
  "analysis_metadata": {
    "confidence_score": 0.87,
    "data_sources": 5
  }
}
```

## 📊 Report Generation

### PDF Report
```bash
curl -X POST http://localhost:8080/report-generation \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Generate PDF financial report for Microsoft",
    "session_id": "report-session",
    "output_format": "pdf"
  }'
```

**Response:**
```json
{
  "response": "Generated 20-page comprehensive Microsoft financial analysis...",
  "report_data": {
    "pdf_base64": "JVBERi0xLjQKMSAwIG9iago...",
    "charts": [
      {
        "type": "line",
        "title": "Revenue Trend", 
        "data": {...}
      }
    ],
    "metadata": {
      "pages": 20,
      "file_size": "2.4MB"
    }
  }
}
```

## 🗄️ Database Operations

### Neo4j Query
```bash
curl -X GET "http://localhost:8080/neo4j-query?query=MATCH (c:Company {ticker: 'AAPL'}) RETURN c.name"
```

**Response:**
```json
{
  "results": [
    {"c.name": "Apple Inc."}
  ],
  "summary": {
    "query_time": "0.043s",
    "records_returned": 1
  }
}
```

### Data Injection
```bash
curl -X POST http://localhost:8080/data-inject \
  -H "Content-Type: application/json" \
  -d '{
    "data_source": "file",
    "content": "/path/to/filing.pdf",
    "data_type": "10k",
    "metadata": {
      "company": "Apple Inc.",
      "year": "2023"
    }
  }'
```

## 📈 Financial Metrics

### Company Metrics
```bash
curl -X GET "http://localhost:8080/special-metrics/AAPL?metrics=pe_ratio,roe&years=3"
```

**Response:**
```json
{
  "ticker": "AAPL",
  "metrics": {
    "pe_ratio": {
      "current": 28.5,
      "historical": [28.5, 27.2, 30.8],
      "sector_average": 24.1
    },
    "roe": {
      "current": 0.565,
      "trend": "improving"
    }
  }
}
```

## 🔧 Session Management

### List Sessions
```bash
curl -X GET "http://localhost:8080/sessions?limit=10"
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "session-123",
      "agent_type": "general",
      "created_at": "2024-01-01T00:00:00Z",
      "message_count": 15
    }
  ],
  "total": 1,
  "pagination": {
    "limit": 10,
    "offset": 0
  }
}
```

## 🚨 Error Handling

### Rate Limit Example
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "retry_after": 60
  }
}
```

### Validation Error
```json
{
  "status": "error", 
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "message",
      "issue": "Required field missing"
    }
  }
}
```

## 📱 Integration Examples

### Python Client
```python
import requests
import json

class GetDeepClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        
    def chat(self, message, agent_type="general", session_id=None):
        endpoint = f"{self.base_url}/{agent_type}-chat"
        data = {
            "message": message,
            "session_id": session_id or self.generate_session_id()
        }
        
        response = requests.post(endpoint, json=data)
        return response.json()
        
    def get_metrics(self, ticker, metrics_list):
        endpoint = f"{self.base_url}/special-metrics/{ticker}"
        params = {"metrics": ",".join(metrics_list)}
        
        response = requests.get(endpoint, params=params)
        return response.json()

# Usage
client = GetDeepClient()
result = client.chat("Analyze AAPL stock", agent_type="deep")
print(result["response"])
```

### JavaScript Client
```javascript
class GetDeepAPI {
    constructor(baseUrl = 'http://localhost:8080') {
        this.baseUrl = baseUrl;
    }
    
    async chat(message, agentType = 'general', sessionId = null) {
        const endpoint = `${this.baseUrl}/${agentType}-chat`;
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: message,
                session_id: sessionId || this.generateSessionId()
            })
        });
        
        return response.json();
    }
    
    async getMetrics(ticker, metricsList) {
        const params = new URLSearchParams({
            metrics: metricsList.join(',')
        });
        
        const response = await fetch(
            `${this.baseUrl}/special-metrics/${ticker}?${params}`
        );
        
        return response.json();
    }
}

// Usage
const api = new GetDeepAPI();
const result = await api.chat('What is Tesla worth?', 'deep');
console.log(result.response);
```

---

For complete API reference, see [API Endpoints Documentation](endpoints.md).
