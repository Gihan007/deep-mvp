# Agent System Architecture

Get-Deep employs a sophisticated multi-agent architecture where each agent is specialized for specific types of tasks and conversations. Built on LangGraph, each agent maintains conversation state, uses specialized tools, and follows distinct behavioral patterns.

## 🤖 Agent Overview

The system includes four primary agents, each with unique capabilities and specializations:

| Agent | Purpose | Primary Use Cases | Key Tools |
|-------|---------|-------------------|-----------|
| General Agent | Multi-purpose conversations | Q&A, basic analysis, general chat | Web search, document processing |
| Deep Agent | Advanced reasoning | Complex analysis, multi-step problems | All tools + advanced analytics |
| Update Agent | Database maintenance | Data ingestion, schema updates | Neo4j write operations |
| Report Generator | Document creation | PDF reports, visualizations | Chart generation, templates |

## 🔧 Agent Implementation Details

### 1. General Agent (`General_Agent_Graph.py`)

**Class**: `GAG_ChatQABot`

#### Purpose and Capabilities
- General-purpose conversational AI for everyday interactions
- Handles basic questions, simple analysis, and information retrieval
- Designed for quick responses and broad knowledge coverage

#### Architecture
```python
class GAG_GraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    sender: Optional[str]

class GAG_ChatQABot:
    def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store)
    # Uses supervisor-based routing with multiple worker nodes
```

#### Key Features
- **Supervisor Pattern**: Uses LangGraph supervisor to route between specialized worker nodes
- **Tool Integration**: Access to web search, document processing, and basic analytics
- **Session Management**: Persistent conversation tracking with SQLite checkpointer
- **Streaming Support**: Real-time response streaming capabilities

#### Available Tools
- Web search (DuckDuckGo, Tavily)
- Document processing (PDF, Word, Excel)
- Basic calculations and analysis
- Neo4j read-only queries
- Vector search capabilities

#### Configuration
```python
GENERAL_BOT_TYPE = "General_Agent_Graph"  # Set in config.py
```

### 2. Deep Agent (`Deep_Agnet_Graph.py`)

**Class**: `DAG_ChatQABot`

#### Purpose and Capabilities
- Advanced reasoning and complex problem-solving
- Multi-step analysis and deep research capabilities
- Comprehensive report generation with supporting evidence

#### Architecture
```python
class DAG_ChatQABot:
    def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store)
    # Uses Langmanus graph builder for team-based collaboration
    # Supports multiple specialized team members
```

#### Key Features
- **Team-Based Architecture**: Multiple specialized agents working collaboratively
- **Deep Thinking Mode**: Enhanced reasoning capabilities for complex problems
- **Comprehensive Tool Access**: All available tools plus advanced analytics
- **PDF Report Generation**: Automatic report creation with visualizations
- **Context Management**: Enhanced conversation context and memory

#### Team Members
- `coder_agent`: Programming and technical analysis
- `researcher_agent`: Information gathering and research
- `visualization_agent`: Chart and graph creation
- `reporter_agent`: Document and report generation

#### Advanced Capabilities
```python
# Deep thinking mode activation
{
    "message": "Complex analytical question",
    "deep_thinking_mode": True,
    "session_id": "session-id"
}
```

### 3. Update Agent (`Neo4j_Update_Agent_Graph.py`)

**Class**: `NUAG_ChatQABot`

#### Purpose and Capabilities
- Specialized in Neo4j database operations and maintenance
- Data ingestion and graph structure updates
- Schema management and data validation

#### Architecture
```python
class NUAG_ChatQABot:
    def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store)
    # Focused on database write operations
    # Enhanced security for data modification tasks
```

#### Key Features
- **Write Operations**: Full Neo4j database modification capabilities
- **Data Validation**: Ensures data integrity during updates
- **Batch Processing**: Efficient handling of large data imports
- **Schema Evolution**: Manages database schema changes
- **Backup Integration**: Coordinates with backup systems

#### Specialized Tools
- Neo4j write operations
- Data validation tools
- Schema management utilities
- Batch processing tools
- Database maintenance functions

#### Security Features
```python
ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER = 'false'  # Configurable write access
```

### 4. Report Generator (`Report_Generation_Agent_Graph.py`)

**Class**: `RGAG_ChatQABot`

#### Purpose and Capabilities
- Specialized in creating comprehensive reports and documents
- Advanced visualization and chart generation
- Multiple output formats (PDF, HTML, Markdown)

#### Architecture
```python
class RGAG_ChatQABot:
    def __init__(self, config, graphdb_vector_store, chromadb_vector_store)
    # Specialized for document generation
    # Enhanced visualization capabilities
```

#### Key Features
- **Multi-Format Output**: PDF, HTML, Markdown report generation
- **Advanced Visualizations**: Charts, graphs, and interactive elements
- **Template System**: Customizable report templates
- **Data Integration**: Pulls data from multiple sources
- **Export Capabilities**: Various export formats and delivery options

#### Report Types
- Financial analysis reports
- Company performance summaries
- Market research documents
- Technical analysis reports
- Custom analytical reports

## 🔄 Agent State Management

### Conversation State Schema

Each agent maintains conversation state using LangGraph's state management:

```python
# Common state structure across agents
class GraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    sender: Optional[str]
    # Agent-specific additional state fields
```

### Session Persistence

**SQLite Checkpointer**: Each agent uses persistent SQLite storage for conversation history:

```python
# Session database paths (configurable)
SESSION_DATABASE_PATH = 'databases/chat_history/chat_sessions.db'
SESSION_REPORT_DATABASE_PATH = 'databases/chat_history/report_chat_sessions.db' 
SESSION_UPDATE_NEO4J_DATABASE_PATH = 'databases/chat_history/update_neo4j_chat_sessions.db'
```

### Async Streaming Support

All agents support real-time streaming responses:

```python
async def setup_async_streaming(self):
    """Initialize async streaming checkpointers"""
    
async def stream(self, message, session_id, config_override=None):
    """Stream responses in real-time"""
```

## 🛠️ Agent Configuration

### Model Configuration

Each agent can be configured with different LLM models:

```python
# Base model configuration
CHAT_MODEL_TYPE = 'OPENAI'
CHAT_MODEL_NAME = 'gpt-4o'

# Specialized models for specific agents
REASONING_MODEL = 'o3-deep-research'  # For deep agent
REPORT_GENERATION_OPENAI_MODEL = 'gpt-4.1'  # For report generator
```

### Tool Access Control

Tools are selectively available to agents based on their purpose:

```python
# General Agent - Basic tools
tools = [
    'web_search', 'document_processor', 'basic_calculator'
]

# Deep Agent - All tools
tools = initialize_all_tools(config, vector_stores)

# Update Agent - Database tools only
tools = [
    'neo4j_write', 'data_validator', 'schema_manager'
]
```

### Performance Tuning

Each agent can be fine-tuned for performance:

```python
# Async configuration
UVICORN_WORKERS = 2  # Worker processes
STREAMING_BATCH_SIZE = 50  # Response streaming batch size

# Memory management  
NEO4J_dbms_memory_heap_max__size = '2G'
CHROMA_COLLECTION_SIZE_LIMIT = 1000000
```

## 🔀 Agent Routing Logic

### Automatic Agent Selection

The system can automatically route requests to appropriate agents:

```python
def route_to_agent(request_type, complexity_score, user_intent):
    if request_type == "database_update":
        return "update_agent"
    elif complexity_score > 0.8:
        return "deep_agent" 
    elif "report" in user_intent:
        return "report_generator"
    else:
        return "general_agent"
```

### Manual Agent Selection

Users can explicitly choose agents via API endpoints:

```bash
POST /general-chat      # General Agent
POST /deep-chat         # Deep Agent  
POST /update-neo4j      # Update Agent
POST /report-generation # Report Generator
```

## 📊 Agent Performance Metrics

### Response Time Targets

| Agent | Average Response Time | Complex Query Time |
|-------|----------------------|-------------------|
| General Agent | < 2 seconds | < 5 seconds |
| Deep Agent | < 5 seconds | < 30 seconds |
| Update Agent | < 3 seconds | < 15 seconds |
| Report Generator | < 10 seconds | < 60 seconds |

### Resource Usage

```python
# Memory allocation per agent
GENERAL_AGENT_MEMORY_LIMIT = "1GB"
DEEP_AGENT_MEMORY_LIMIT = "2GB" 
UPDATE_AGENT_MEMORY_LIMIT = "1.5GB"
REPORT_AGENT_MEMORY_LIMIT = "2GB"
```

## 🔧 Extending the Agent System

### Adding New Agents

1. **Create Agent Class**:
```python
class NewAgentBot:
    def __init__(self, llm, config, vector_stores):
        # Initialize agent-specific components
        pass
        
    async def run(self, message, session_id):
        # Implement agent logic
        pass
```

2. **Register in Application**:
```python
# In src/app/__init__.py
if NEW_AGENT_TYPE == "New_Agent_Graph":
    app.new_agent = NewAgentBot(llm, config, vector_stores)
```

3. **Add API Endpoints**:
```python
# Create new router in src/app/routes/
@router.post("/new-agent-chat")
async def new_agent_endpoint(request: ChatRequest):
    return await app.new_agent.run(request.message, request.session_id)
```

### Customizing Existing Agents

1. **Tool Customization**: Modify tool initialization for specific agents
2. **Prompt Templates**: Update prompts in `src/app/prompts/`
3. **State Management**: Extend state schemas for additional context
4. **Performance Tuning**: Adjust configuration parameters

---

This multi-agent architecture provides flexibility, specialization, and scalability for diverse AI-powered applications while maintaining consistent interfaces and state management across all agents.
