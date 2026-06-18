# Architecture Overview

Get-Deep is a sophisticated AI-powered platform built with a modular, microservices-inspired architecture. The system leverages multiple specialized AI agents, graph databases, and modern web technologies to provide comprehensive data analysis and conversational capabilities.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Web     │    │   FastAPI       │    │   Neo4j Graph   │
│   Frontend      │◄──►│   Backend       │◄──►│   Database      │
│   (Port 3000)   │    │   (Port 8080)   │    │   (Port 7474)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         │
                    ┌─────────────────┐                 │
                    │   LangGraph     │                 │
                    │   Agent Engine  │                 │
                    └─────────────────┘                 │
                              │                         │
                              ▼                         │
                    ┌─────────────────┐                 │
                    │   Tool System   │                 │
                    │   (20+ Tools)   │◄────────────────┘
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   External APIs │
                    │   (OpenAI, etc) │
                    └─────────────────┘
```

## 🔧 Core Components

### 1. FastAPI Backend (`src/app/`)

The backbone of the system, providing:

- **RESTful API Endpoints**: Comprehensive API for all system interactions
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **CORS Support**: Cross-origin resource sharing for frontend integration
- **Async Processing**: Non-blocking request handling with asyncio
- **Session Management**: Persistent conversation tracking

**Key Files:**
- `src/app/__init__.py` - Application factory and configuration
- `src/run.py` - Application entry point and server configuration
- `src/config.py` - Centralized configuration management

### 2. Multi-Agent System (`src/app/graphs/`)

Four specialized AI agents built on LangGraph:

#### General Agent (`General_Agent_Graph.py`)
- **Purpose**: Multi-purpose conversational AI
- **Capabilities**: General knowledge, basic analysis, conversation management
- **Tools**: Web search, document processing, basic calculations

#### Deep Agent (`Deep_Agent_Graph.py`)
- **Purpose**: Advanced reasoning and complex problem-solving
- **Capabilities**: Deep analysis, multi-step reasoning, report generation
- **Tools**: All available tools plus advanced analytics

#### Update Agent (`Neo4j_Update_Agent_Graph.py`)
- **Purpose**: Database maintenance and updates
- **Capabilities**: Graph database modifications, data ingestion, schema updates
- **Tools**: Neo4j write operations, data validation, backup management

#### Report Generator (`Report_Generation_Agent_Graph.py`)
- **Purpose**: Specialized report creation and document generation
- **Capabilities**: PDF generation, data visualization, comprehensive reporting
- **Tools**: Chart generation, template systems, export capabilities

### 3. Tool System (`src/app/tools/`)

Extensible tool architecture with 20+ specialized tools:

#### Financial Analysis Tools
- **Alpha Vantage Integration**: Real-time market data
- **Investment Metrics Calculator**: Financial ratio calculations
- **Yahoo Finance Connector**: Alternative market data source

#### Data Processing Tools
- **Document Processors**: PDF, Word, Excel, PowerPoint extraction
- **Web Scrapers**: DuckDuckGo and Tavily search integration
- **Database Tools**: Neo4j Cypher query execution

#### Utility Tools
- **Python REPL**: Dynamic code execution
- **Bash Tool**: System command execution
- **Visualization Tools**: Chart and graph generation

### 4. Database Layer (`src/databases/`)

Multi-database architecture for different use cases:

#### Neo4j Graph Database
- **Purpose**: Knowledge graph storage and complex relationship queries
- **Configuration**: Clustered setup with APOC and GenAI plugins
- **Access**: REST API and Cypher query language

#### ChromaDB Vector Store
- **Purpose**: Semantic search and embedding storage
- **Use Cases**: Document similarity, context retrieval
- **Integration**: Configurable availability based on use case

#### SQLite Session Storage
- **Purpose**: Chat session persistence and checkpointing
- **Files**: 
  - `chat_sessions.db` - General chat sessions
  - `report_chat_sessions.db` - Report generation sessions
  - `update_neo4j_chat_sessions.db` - Database update sessions

### 5. Frontend Interface (`react-chatgpt_original/`)

Modern React-based web interface:

- **Technology Stack**: React 18, TypeScript, Vite
- **Features**: 
  - Real-time chat interface
  - Session management
  - File upload capabilities
  - Message history
  - Export functionality

## 🔄 Data Flow

### Request Processing Flow

1. **Frontend Request**: User interaction triggers API call
2. **API Routing**: FastAPI routes request to appropriate handler
3. **Agent Selection**: System selects appropriate AI agent based on request type
4. **Tool Execution**: Agent uses available tools to process request
5. **Database Operations**: Data stored/retrieved from Neo4j or ChromaDB
6. **Response Generation**: LLM generates response based on tool outputs
7. **Frontend Update**: Response sent back to frontend for display

### Session Management

```
User Session
├── Session ID (UUID)
├── Conversation History (Messages)
├── Agent Context (State)
├── Tool Outputs (Cached Results)
└── Checkpoint Data (LangGraph State)
```

## 🚀 Deployment Architecture

### Docker Compose Setup

```yaml
services:
  neo4j:           # Graph database
    - Port: 7474, 7687
    - Volumes: Persistent data storage
    - Plugins: APOC, GenAI
    
  chatbot:         # Main application
    - Port: 8080
    - Dependencies: Neo4j
    - Health checks: Enabled
    - Workers: 2 (configurable)
```

### Container Features

- **Multi-stage Build**: Optimized Docker image
- **Non-root User**: Security-first approach
- **Health Checks**: Automatic service monitoring
- **Signal Handling**: Graceful shutdown with tini

## 🔐 Security & Configuration

### Environment-based Configuration

- **Development**: Debug logging, reload enabled
- **Testing**: Isolated database, test fixtures
- **Production**: Optimized performance, secure defaults

### API Security

- **CORS Configuration**: Controlled cross-origin access
- **Input Validation**: Pydantic models for request validation
- **Error Handling**: Comprehensive error responses
- **Rate Limiting**: Configurable request throttling

## 📊 Monitoring & Observability

### Logging System

- **Structured Logging**: JSON format for analysis
- **Component Isolation**: Separate loggers for different components
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR
- **External Integration**: LangSmith tracing support

### Health Monitoring

- **Endpoint Health**: `/health` and `/ready` endpoints
- **Database Connectivity**: Neo4j connection monitoring
- **Service Dependencies**: Upstream service health checks

### Performance Metrics

- **Request Latency**: API response time tracking
- **Database Performance**: Query execution monitoring
- **Agent Efficiency**: Tool usage and response quality metrics

## 🔧 Extensibility Points

### Adding New Agents

1. Create agent class in `src/app/graphs/`
2. Implement required interfaces
3. Add configuration in `config.py`
4. Register in application factory

### Adding New Tools

1. Implement tool in `src/app/tools/`
2. Follow tool interface patterns
3. Add to tool initializer
4. Update agent configurations

### Database Extensions

1. Add database configuration
2. Implement connection logic
3. Create utility functions
4. Update health checks

---

This architecture provides a solid foundation for scalable, maintainable AI applications while ensuring flexibility for future enhancements and integrations.
