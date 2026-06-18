# Get-Deep: AI-Powered Multi-Agent Chatbot Platform

Get-Deep is a sophisticated AI-powered platform that leverages multiple specialized agents to provide comprehensive data analysis, research, and reporting capabilities. Built with FastAPI, LangChain/LangGraph, and Neo4j, it offers a robust foundation for intelligent conversations and data processing.

## 🚀 Key Features

- **Multi-Agent Architecture**: Four specialized AI agents for different use cases
- **Graph Database Integration**: Neo4j for knowledge graph storage and retrieval
- **Vector Database Support**: ChromaDB for semantic search capabilities
- **Financial Data Analysis**: Integrated tools for market data and financial metrics
- **Document Processing**: Support for PDF, Word, Excel, and PowerPoint files
- **Real-time Web Interface**: React-based frontend for seamless user interaction
- **Containerized Deployment**: Docker and Docker Compose for easy deployment
- **Extensible Tool System**: 20+ specialized tools for various tasks

## 🏗️ Architecture Overview

### Core Components

1. **FastAPI Backend** (`src/app/`): RESTful API server with health monitoring
2. **AI Agent Graphs** (`src/app/graphs/`): LangGraph-based conversational agents
3. **Tool System** (`src/app/tools/`): Specialized tools for data processing and analysis
4. **Database Layer** (`src/databases/`): Neo4j graph database and SQLite for sessions
5. **React Frontend** (`react-chatgpt_original/`): Modern web interface
6. **Utilities** (`src/app/utills/`): Helper functions and shared components

### Agent Types

- **General Agent**: Multi-purpose conversational AI for general queries
- **Deep Agent**: Advanced reasoning and complex problem-solving
- **Update Agent**: Neo4j database updates and maintenance
- **Report Generator**: Specialized in creating comprehensive reports

## 🛠️ Technology Stack

### Backend
- **Python 3.12**: Core runtime environment
- **FastAPI**: High-performance web framework
- **LangChain/LangGraph**: Agent orchestration and conversation flow
- **Neo4j**: Graph database for knowledge storage
- **ChromaDB**: Vector database for embeddings
- **SQLite**: Session and checkpoint storage

### Frontend
- **React 18**: Modern UI framework
- **TypeScript**: Type-safe JavaScript
- **Vite**: Build tool and development server
- **Axios**: HTTP client for API communication

### Infrastructure
- **Docker**: Containerization platform
- **Docker Compose**: Multi-service orchestration
- **Uvicorn**: ASGI server for Python applications

### AI/ML Libraries
- **OpenAI**: GPT models for language understanding
- **LangSmith**: Monitoring and debugging
- **Tiktoken**: Token counting and management
- **Sentence Transformers**: Embedding generation

## 📦 Installation & Setup

### Prerequisites
- Docker and Docker Compose
- Python 3.12 (for local development)
- Node.js 18+ (for frontend development)

### Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Get-Deep
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Start services**
   ```bash
   docker compose up -d
   ```

4. **Access the application**
   - API: http://localhost:8080
   - Neo4j Browser: http://localhost:7474
   - Frontend: Serve the React app separately or integrate as needed

### Local Development Setup

1. **Backend Setup**
   ```bash
   cd src/
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python run.py
   ```

2. **Frontend Setup**
   ```bash
   cd react-chatgpt_original/
   npm install
   npm run dev
   ```

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# AI Models
OPENAI_API_KEY=your_openai_key
CHAT_MODEL_NAME=gpt-4o
EMBEDDINGS_MODEL_NAME=text-embedding-ada-002

# Database Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
GRAPH_DATA_BASE_AVAILABILITY=YES
CHROMA_DATA_BASE_AVAILABILITY=NO

# External APIs
TAVILY_API_KEY=your_tavily_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key

# Agent Types
GENERAL_BOT_TYPE=General_Agent_Graph
DEEP_BOT_TYPE=Deep_Agent_Graph
UPDATE_GRAPH_BOT_TYPE=Neo4j_Update_Agent_Graph
```

## 🚀 Usage

### API Endpoints

#### Health Check
```bash
GET /health
GET /ready
```

#### Chat Endpoints
```bash
POST /general-chat          # General purpose conversations
POST /deep-chat             # Advanced reasoning tasks
POST /report-generation     # Generate comprehensive reports
POST /update-neo4j          # Database update operations
```

#### Data Management
```bash
POST /data-inject           # Inject data into graph database
GET /neo4j-query           # Query Neo4j database
POST /special-metrics      # Calculate financial metrics
```

### Frontend Interface

The React frontend provides:
- Real-time chat interface
- Message history and session management
- File upload capabilities
- Visualization of results
- Export functionality

## 📊 Tools & Capabilities

### Financial Analysis Tools
- **Alpha Vantage Integration**: Stock prices, earnings, market news
- **Yahoo Finance**: Alternative market data source
- **Investment Metrics Calculator**: Financial ratio calculations
- **Visualization Tools**: Chart and graph generation

### Data Processing Tools
- **Document Processing**: PDF, Word, Excel, PowerPoint extraction
- **Web Scraping**: DuckDuckGo and Tavily search integration
- **Database Queries**: Neo4j Cypher query execution
- **Python REPL**: Dynamic code execution

### Utility Tools
- **Bash Tool**: System command execution
- **Vector Search**: Semantic similarity search
- **Media Handler**: Image and audio processing
- **Report Generation**: PDF and markdown report creation

## 🗂️ Project Structure

```
Get-Deep/
├── src/                          # Backend source code
│   ├── app/                      # FastAPI application
│   │   ├── graphs/              # AI agent implementations
│   │   ├── routes/              # API endpoints
│   │   ├── tools/               # Specialized tools
│   │   ├── utills/              # Utility functions
│   │   ├── models/              # LLM model configurations
│   │   └── prompts/             # AI prompt templates
│   ├── databases/               # Database files and migrations
│   ├── config.py                # Configuration management
│   └── run.py                   # Application entry point
├── react-chatgpt_original/      # Frontend React application
├── scripts/                     # Utility scripts
├── testing/                     # Test files and API testing
├── docker-compose.yml           # Multi-service configuration
├── Dockerfile                   # Container build instructions
└── requirements.txt             # Python dependencies
```

## 🧪 Testing

The project includes comprehensive testing capabilities:

```bash
# API Testing
cd testing/api_testing/
# Use provided Jupyter notebooks for endpoint testing

# Manual Testing
cd testing/
# Explore curl_commands.ipynb for API examples
```

## 📈 Monitoring & Debugging

### Logging
- Comprehensive logging system with configurable levels
- LangSmith integration for conversation tracing
- Neo4j query monitoring

### Health Checks
- Docker health checks for all services
- API endpoint monitoring
- Database connectivity verification

## 🆘 Support

For support and questions:
- Review the testing examples in `testing/`
- Examine the configuration options in `config.py`


---

**Version**: 3.0  
**Last Updated**: 2024  
**Python Version**: 3.12.10  
**Docker Support**: Yes
