# Configuration Guide

Get-Deep uses a comprehensive configuration system that supports multiple environments, external integrations, and fine-tuned performance settings. This guide covers all configuration options and best practices.

## 🔧 Configuration Architecture

### Configuration Hierarchy

```python
# Configuration precedence (highest to lowest)
1. Environment Variables (.env file or system environment)
2. Configuration Classes (config.py)
3. Default Values (hardcoded in config classes)
```

### Environment-Based Configuration

```python
# config.py structure
class Config:                    # Base configuration
class DevelopmentConfig(Config): # Development overrides  
class TestingConfig(Config):     # Testing overrides
class ProductionConfig(Config):  # Production overrides
```

## 🌍 Environment Variables

### Core Application Settings

```env
# Application Environment
APP_ENV=development              # Options: development, testing, production
DEBUG_ENABLE=true               # Enable debug mode (true/false)
LOG_LEVEL=DEBUG                 # Logging level: DEBUG, INFO, WARNING, ERROR

# Server Configuration
UVICORN_RELOAD=1                # Auto-reload on code changes (development)
UVICORN_WORKERS=2               # Number of worker processes
```

### AI Model Configuration

```env
# Primary LLM Configuration
CHAT_MODEL_TYPE=OPENAI          # Options: OPENAI, GOOGLE
CHAT_MODEL_NAME=gpt-4o          # Specific model name
EMBEDDINGS_MODEL_TYPE=OPENAI    # Embeddings provider
EMBEDDINGS_MODEL_NAME=text-embedding-ada-002

# Specialized Models
REASONING_MODEL=o3-deep-research          # Advanced reasoning model
BASIC_MODEL=gpt-4o                       # General purpose model
VL_MODEL=gpt-4o                          # Vision-language model

# Model API Configuration
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here      # If using Google models

# API Endpoints (optional, for custom deployments)
REASONING_BASE_URL=https://api.openai.com/v1
BASIC_BASE_URL=https://api.openai.com/v1
VL_BASE_URL=https://api.openai.com/v1
```

### Agent Configuration

```env
# Agent Type Selection
GENERAL_BOT_TYPE=General_Agent_Graph
DEEP_BOT_TYPE=Deep_Agent_Graph
UPDATE_GRAPH_BOT_TYPE=Neo4j_Update_Agent_Graph
DEDICATED_REPORT_GENERATOR_BOT_TYPE=Report_Generation_Agent_Graph

# Report Generation Models
REPORT_GENERATION_OPENAI_MODEL=gpt-4.1
REPORT_GENERATION_GOOGLE_MODEL=gemini-1.0-ultra

# Specialized Tool Models
TENK_DATA_EXTRACTOR_OPENAI_MODEL_NAME=gpt-4o
```

### Database Configuration

#### Neo4j Graph Database

```env
# Neo4j Connection
NEO4J_URI=bolt://localhost:7687  # Connection URI
NEO4J_USERNAME=neo4j            # Database username
NEO4J_PASSWORD=your_neo4j_password_here          # Database password

# Neo4j Index Configuration
NEO4J_INDEX_NAME=form_10k_chunks
NEO4J_NODE_LABEL=Chunk
NEO4J_TEXT_NODE_PROPERTY=text
NEO4J_EMBEDDING_NODE_PROPERTY=textEmbedding

# Neo4j Security
ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER=false  # Enable write operations via API

# Database Availability
GRAPH_DATA_BASE_AVAILABILITY=YES            # Enable Neo4j integration
```

#### ChromaDB Configuration

```env
# ChromaDB Settings
CHROMA_DATA_BASE_AVAILABILITY=NO            # Enable ChromaDB (YES/NO)
CHROMA_DB_PATH=databases/user_data          # Relative to BASE_DIR
CHROMA_COLLECTION_NAME=user_data

# Attachments ChromaDB (optional)
ATTACHMENTS_CHROMA_DB_PATH=databases/attachments_chroma_db
ATTACHMENTS_CHROMA_COLLECTION_NAME=attachments
```

#### Session Database Paths

```env
# SQLite Database Paths (relative to BASE_DIR)
SESSION_DATABASE_PATH=databases/chat_history/chat_sessions.db
SESSION_REPORT_DATABASE_PATH=databases/chat_history/report_chat_sessions.db
SESSION_UPDATE_NEO4J_DATABASE_PATH=databases/chat_history/update_neo4j_chat_sessions.db
```

### External API Configuration

#### Search and Research APIs

```env
# Tavily Search API
TAVILY_API_KEY=your_tavily_api_key
TAVILY_MAX_RESULTS=5            # Number of search results

# Browser Automation (optional)
CHROME_INSTANCE_PATH=/usr/bin/google-chrome  # Path to Chrome executable
```

#### Financial Data APIs

```env
# Alpha Vantage Configuration
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query

# Available news topics for Alpha Vantage
ALPHAVANTAGE_AVAILABLE_TOPICS=blockchain,earnings,financial_markets,mergers_and_acquisitions,ipo,technology
```

#### Market Data Configuration

```env
# Primary data source selection
SPECIAL_METRIC_CACHE_PRIMARY_SOURCE=yahoo   # Options: yahoo, alphavantage

# Yahoo Finance Configuration
SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS=10
SPECIAL_METRIC_OLD_CACHE_YAHOO_MAX_WORKERS=5

# Alpha Vantage Configuration  
SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS=1  # Rate limit consideration

# Cache Control
USE_ONLY_CACHE_NODES=True       # Use only cached data (true/false)
```

## 🏗️ Configuration Classes

### Base Configuration Class

```python
# src/config.py
class Config:
    # Automatically derived base directory
    BASE_DIR = Path(__file__).resolve().parent
    
    # Model configurations with environment fallbacks
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    
    # Database settings with defaults
    NEO4J_URI = os.environ.get('NEO4J_URI', "bolt://localhost:7687")
    NEO4J_USERNAME = os.environ.get('NEO4J_USERNAME', "neo4j")
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', "your_neo4j_password_here")
    
    # Utility method for directory creation
    @classmethod
    def initialize_directories(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(os.path.dirname(cls.SESSION_DATABASE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.SESSION_REPORT_DATABASE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.SESSION_UPDATE_NEO4J_DATABASE_PATH), exist_ok=True)
```

### Environment-Specific Configurations

```python
class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"
    # Development-specific overrides
    LOG_LEVEL = "DEBUG"
    UVICORN_RELOAD = True

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    ENV = "testing"
    # Use in-memory or test databases
    SESSION_DATABASE_PATH = ":memory:"

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    ENV = "production"
    # Production optimizations
    LOG_LEVEL = "INFO"
    UVICORN_WORKERS = 4
```

## 🔐 Security Configuration

### API Key Management

**Best Practices**:
```env
# ✅ Store in .env file (not committed to version control)
OPENAI_API_KEY=sk-proj-xxx...

# ✅ Use environment variables in production
export OPENAI_API_KEY="sk-proj-xxx..."

# ❌ Never hardcode in source code
OPENAI_API_KEY = "sk-proj-xxx..."  # DON'T DO THIS
```

**Docker Secrets** (for production):
```yaml
# docker-compose.yml
services:
  chatbot:
    secrets:
      - openai_key
      - neo4j_password
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_key

secrets:
  openai_key:
    file: ./secrets/openai_key.txt
  neo4j_password:
    file: ./secrets/neo4j_password.txt
```

### Database Security

```env
# Neo4j Security Settings (in Neo4j configuration)
NEO4J_dbms_security_procedures_unrestricted=apoc.*,genai.*
NEO4J_dbms_security_procedures_allowlist=apoc.*,genai.*

# Application-level security
ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER=false  # Restrict write access
```

## ⚡ Performance Configuration

### Application Performance

```env
# Server Workers
UVICORN_WORKERS=2               # Development
UVICORN_WORKERS=4               # Production

# Request Timeouts
REQUEST_TIMEOUT=300             # 5 minutes for complex operations
STREAMING_TIMEOUT=60            # 1 minute for streaming responses

# Memory Management
PYTHON_GC_THRESHOLD=700,10,10   # Garbage collection tuning
```

### Database Performance

#### Neo4j Memory Configuration

```env
# Neo4j Memory Settings (set in docker-compose.yml or neo4j.conf)
NEO4J_dbms_memory_heap_initial__size=512m
NEO4J_dbms_memory_heap_max__size=2G
NEO4J_dbms_memory_pagecache_size=1G

# Connection Pool
NEO4J_dbms_connector_bolt_thread_pool_min_size=5
NEO4J_dbms_connector_bolt_thread_pool_max_size=400
```

#### ChromaDB Performance

```env
# ChromaDB Configuration
CHROMA_COLLECTION_MAX_SIZE=1000000      # Maximum documents per collection
CHROMA_BATCH_SIZE=1000                  # Batch size for operations
```

### External API Rate Limiting

```env
# Alpha Vantage Rate Limits
ALPHA_VANTAGE_REQUESTS_PER_MINUTE=75    # API rate limit
ALPHA_VANTAGE_MAX_WORKERS=1             # Conservative parallel requests

# Tavily Rate Limits  
TAVILY_MAX_RESULTS=5                    # Limit results to control costs
TAVILY_REQUESTS_PER_MINUTE=100          # API rate limit
```

## 🔧 Configuration Validation

### Required Configuration Checker

```python
# src/config_validator.py
def validate_configuration(config):
    """Validate required configuration settings"""
    required_settings = [
        'OPENAI_API_KEY',
        'NEO4J_URI',
        'NEO4J_USERNAME', 
        'NEO4J_PASSWORD'
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not getattr(config, setting, None):
            missing_settings.append(setting)
    
    if missing_settings:
        raise ConfigurationError(f"Missing required settings: {missing_settings}")

def validate_database_connections(config):
    """Test database connectivity"""
    # Test Neo4j connection
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        driver.close()
    except Exception as e:
        raise DatabaseConnectionError(f"Neo4j connection failed: {e}")
    
    # Test ChromaDB if enabled
    if config.CHROMA_DATA_BASE_AVAILABILITY == "YES":
        try:
            client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
            client.heartbeat()
        except Exception as e:
            raise DatabaseConnectionError(f"ChromaDB connection failed: {e}")
```

## 🌐 Environment-Specific Examples

### Development Environment

```env
# .env.development
APP_ENV=development
DEBUG_ENABLE=true
LOG_LEVEL=DEBUG
UVICORN_RELOAD=1

# Local database connections
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here

# Development API keys (use test keys when available)
OPENAI_API_KEY=sk-dev-xxx...
TAVILY_API_KEY=tvly-dev-xxx...

# Reduced rate limits for development
TAVILY_MAX_RESULTS=3
ALPHA_VANTAGE_MAX_WORKERS=1

# Enable all databases for testing
GRAPH_DATA_BASE_AVAILABILITY=YES
CHROMA_DATA_BASE_AVAILABILITY=YES
```

### Production Environment

```env
# .env.production
APP_ENV=production
DEBUG_ENABLE=false
LOG_LEVEL=INFO

# Production database connections
NEO4J_URI=bolt://neo4j-production:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=${NEO4J_PRODUCTION_PASSWORD}

# Production API keys
OPENAI_API_KEY=${OPENAI_PRODUCTION_KEY}
TAVILY_API_KEY=${TAVILY_PRODUCTION_KEY}
ALPHA_VANTAGE_API_KEY=${ALPHAVANTAGE_PRODUCTION_KEY}

# Production performance settings
UVICORN_WORKERS=4
SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS=10
SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS=2

# Production database optimization
GRAPH_DATA_BASE_AVAILABILITY=YES
CHROMA_DATA_BASE_AVAILABILITY=NO  # Disabled for production efficiency
```

### Testing Environment

```env
# .env.testing
APP_ENV=testing
DEBUG_ENABLE=true
TESTING=true
LOG_LEVEL=DEBUG

# Test database (often in-memory or separate test DB)
NEO4J_URI=bolt://localhost:7688  # Different port for test instance
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=test_password

# Test API keys (use test/mock keys)
OPENAI_API_KEY=sk-test-xxx...

# Minimal external API calls during testing
USE_ONLY_CACHE_NODES=True
TAVILY_MAX_RESULTS=1
```

## 🔄 Configuration Management

### Dynamic Configuration Updates

```python
# Runtime configuration updates (where applicable)
def update_configuration(key: str, value: str):
    """Update configuration at runtime"""
    if key in UPDATEABLE_CONFIGS:
        setattr(current_config, key, value)
        # Trigger any necessary reinitialization
        reinitialize_components(key)

UPDATEABLE_CONFIGS = [
    'LOG_LEVEL',
    'TAVILY_MAX_RESULTS',
    'USE_ONLY_CACHE_NODES'
]
```

### Configuration Templates

**Template for New Environments**:
```bash
#!/bin/bash
# setup_environment.sh

ENV_NAME=${1:-development}
ENV_FILE=".env.${ENV_NAME}"

cat > $ENV_FILE << EOL
# Environment: $ENV_NAME
APP_ENV=$ENV_NAME

# Core API Keys (REQUIRED)
OPENAI_API_KEY=your_openai_key_here
TAVILY_API_KEY=your_tavily_key_here
ALPHA_VANTAGE_API_KEY=your_alphavantage_key_here

# Database Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
GRAPH_DATA_BASE_AVAILABILITY=YES
CHROMA_DATA_BASE_AVAILABILITY=NO

# Model Configuration
CHAT_MODEL_NAME=gpt-4o
EMBEDDINGS_MODEL_NAME=text-embedding-ada-002

# Performance Settings
UVICORN_WORKERS=2
TAVILY_MAX_RESULTS=5
EOL

echo "Environment file created: $ENV_FILE"
echo "Please edit $ENV_FILE and add your actual API keys"
```

## 🔍 Configuration Troubleshooting

### Common Issues

**Missing API Keys**:
```bash
# Check if environment variables are loaded
python -c "from config import get_config; print(get_config().OPENAI_API_KEY)"
```

**Database Connection Issues**:
```python
# Test database connections
from config import get_config
from neo4j import GraphDatabase

config = get_config()
driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD))
try:
    driver.verify_connectivity()
    print("Neo4j connection successful")
except Exception as e:
    print(f"Neo4j connection failed: {e}")
```

**Configuration Conflicts**:
```bash
# Check which configuration is being loaded
python -c "from config import get_config; c = get_config(); print(f'Environment: {c.ENV}, Debug: {c.DEBUG}')"
```

---

This comprehensive configuration guide ensures proper setup and optimization of Get-Deep across different environments and use cases, with security best practices and performance tuning guidelines.
