# Database Architecture

Get-Deep employs a multi-database architecture designed to handle different types of data and use cases efficiently. The system integrates graph databases, vector stores, and relational databases to provide comprehensive data management capabilities.

## 🗄️ Database Overview

| Database | Technology | Purpose | Port | Data Types |
|----------|------------|---------|------|------------|
| Neo4j | Graph Database | Knowledge graphs, relationships | 7474/7687 | Companies, metrics, relationships |
| ChromaDB | Vector Store | Embeddings, semantic search | N/A | Document embeddings, vectors |
| SQLite | Relational | Session management, checkpoints | N/A | Chat history, user sessions |

## 📊 Neo4j Graph Database

### Configuration and Setup

**Docker Configuration** (`docker-compose.yml`):
```yaml
services:
  neo4j:
    image: neo4j:5.23-community
    container_name: neo4j-DataStore
    ports:
      - "7474:7474"  # HTTP interface
      - "7687:7687"  # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/your_neo4j_password_here
      - NEO4J_PLUGINS=["apoc", "genai"]
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
```

**Connection Configuration**:
```python
# Neo4j connection settings
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j" 
NEO4J_PASSWORD = "your_neo4j_password_here"
NEO4J_INDEX_NAME = 'form_10k_chunks'
NEO4J_NODE_LABEL = 'Chunk'
NEO4J_TEXT_NODE_PROPERTY = 'text'
NEO4J_EMBEDDING_NODE_PROPERTY = 'textEmbedding'
```

### Schema Design

#### Core Node Types

**Company Nodes**:
```cypher
CREATE (c:Company {
  name: "Apple Inc.",
  ticker: "AAPL",
  sector: "Technology",
  industry: "Consumer Electronics",
  market_cap: 3000000000000,
  founded: 1976,
  headquarters: "Cupertino, CA"
})
```

**Metric Nodes**:
```cypher
CREATE (m:Metric {
  name: "revenue",
  value: 365817000000,
  period: "2023",
  quarter: "Q4",
  unit: "USD",
  metric_type: "financial"
})
```

**Document Chunks** (for 10-K filings):
```cypher
CREATE (d:Chunk {
  text: "Management Discussion and Analysis content...",
  source: "10-K",
  company: "AAPL",
  year: "2023",
  section: "MD&A",
  chunk_id: "chunk_001",
  textEmbedding: [0.123, 0.456, ...] // Vector embedding
})
```

#### Relationship Types

**Company-Metric Relationships**:
```cypher
// Company has metric
(c:Company)-[:HAS_METRIC]->(m:Metric)

// Metric comparisons
(m1:Metric)-[:COMPARED_TO]->(m2:Metric)

// Temporal relationships
(m1:Metric)-[:FOLLOWS]->(m2:Metric)
```

**Industry Relationships**:
```cypher
// Industry classification
(c:Company)-[:BELONGS_TO]->(s:Sector)-[:CONTAINS]->(i:Industry)

// Peer relationships
(c1:Company)-[:PEER_OF]->(c2:Company)
```

### Indexes and Constraints

**Performance Indexes**:
```cypher
-- Company ticker index (unique)
CREATE CONSTRAINT company_ticker_unique FOR (c:Company) REQUIRE c.ticker IS UNIQUE;

-- Text search index
CREATE FULLTEXT INDEX company_search FOR (c:Company) ON EACH [c.name, c.description];

-- Vector index for embeddings
CREATE VECTOR INDEX chunk_embeddings FOR (d:Chunk) ON (d.textEmbedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

-- Metric indexes for fast queries
CREATE INDEX metric_name FOR (m:Metric) ON (m.name);
CREATE INDEX metric_period FOR (m:Metric) ON (m.period);
```

### Data Ingestion Patterns

**Financial Data Ingestion**:
```cypher
-- Merge company (create if not exists)
MERGE (c:Company {ticker: $ticker})
SET c.name = $name,
    c.sector = $sector,
    c.updated_at = datetime()

-- Create/update metrics
MERGE (c)-[:HAS_METRIC]->(m:Metric {name: $metric_name, period: $period})
SET m.value = $value,
    m.unit = $unit,
    m.updated_at = datetime()
```

**Document Chunk Ingestion**:
```cypher
-- Create document chunks with embeddings
CREATE (d:Chunk {
  text: $text,
  source: $source,
  company: $company,
  chunk_id: $chunk_id,
  textEmbedding: $embedding
})

-- Link to company
MATCH (c:Company {ticker: $company})
CREATE (c)-[:HAS_DOCUMENT]->(d)
```

### Query Patterns

**Financial Analysis Queries**:
```cypher
-- Get company metrics for analysis
MATCH (c:Company {ticker: "AAPL"})-[:HAS_METRIC]->(m:Metric)
WHERE m.period = "2023"
RETURN c.name, m.name, m.value, m.unit
ORDER BY m.name;

-- Peer comparison
MATCH (c1:Company {ticker: "AAPL"})-[:PEER_OF]->(c2:Company)
MATCH (c1)-[:HAS_METRIC]->(m1:Metric {name: "revenue"})
MATCH (c2)-[:HAS_METRIC]->(m2:Metric {name: "revenue"})
WHERE m1.period = m2.period
RETURN c1.name, m1.value, c2.name, m2.value
ORDER BY m1.value DESC;
```

**Semantic Search Queries**:
```cypher
-- Vector similarity search
CALL db.index.vector.queryNodes('chunk_embeddings', 10, $query_embedding)
YIELD node, score
MATCH (c:Company)-[:HAS_DOCUMENT]->(node)
RETURN c.name, node.text, score
ORDER BY score DESC;
```

## 🔍 ChromaDB Vector Store

### Configuration

**Setup and Initialization**:
```python
# ChromaDB configuration
CHROMA_DB_PATH = "databases/user_data"
CHROMA_COLLECTION_NAME = "user_data"
ATTACHMENTS_CHROMA_DB_PATH = "databases/attachments_chroma_db"
```

**Collection Management**:
```python
class VectorStoreBuilder:
    def create_chroma_vector_store(self):
        return Chroma(
            persist_directory=self.config.CHROMA_DB_PATH,
            embedding_function=self.embeddings,
            collection_name=self.config.CHROMA_COLLECTION_NAME
        )
```

### Data Structure

**Document Storage Format**:
```python
{
  "ids": ["doc_001", "doc_002"],
  "documents": ["Document content 1", "Document content 2"],
  "metadatas": [
    {
      "source": "uploaded_file.pdf",
      "page": 1,
      "timestamp": "2024-01-01T00:00:00Z",
      "user_id": "user_123"
    }
  ],
  "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]]
}
```

### Query Operations

**Similarity Search**:
```python
# Search for similar documents
results = vectorstore.similarity_search(
    query="financial performance metrics",
    k=10,
    filter={"source": "10k_filing"}
)
```

**Metadata Filtering**:
```python
# Filter by metadata
results = vectorstore.similarity_search(
    query="revenue growth",
    k=5,
    filter={
        "company": "AAPL",
        "year": "2023"
    }
)
```

## 💾 SQLite Session Management

### Database Structure

**Chat Sessions Table** (`chat_sessions.db`):
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    agent_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    role TEXT CHECK(role IN ('human', 'ai', 'system')),
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);
```

**Report Sessions Table** (`report_chat_sessions.db`):
```sql
CREATE TABLE report_sessions (
    session_id TEXT PRIMARY KEY,
    report_type TEXT,
    output_format TEXT,
    status TEXT CHECK(status IN ('pending', 'processing', 'completed', 'error')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    report_data BLOB
);
```

**Neo4j Update Sessions** (`update_neo4j_chat_sessions.db`):
```sql
CREATE TABLE update_sessions (
    session_id TEXT PRIMARY KEY,
    operation_type TEXT,
    affected_nodes INTEGER DEFAULT 0,
    affected_relationships INTEGER DEFAULT 0,
    rollback_data TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Session Management Operations

**Session Creation**:
```python
def create_session(user_id: str, agent_type: str) -> str:
    session_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, agent_type)
        VALUES (?, ?, ?)
    """, (session_id, user_id, agent_type))
    return session_id
```

**Message Storage**:
```python
def store_message(session_id: str, role: str, content: str, metadata: dict = None):
    message_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO messages (message_id, session_id, role, content, metadata)
        VALUES (?, ?, ?, ?, ?)
    """, (message_id, session_id, role, content, json.dumps(metadata)))
```

## 🔄 Data Synchronization

### Cross-Database Consistency

**Neo4j to ChromaDB Sync**:
```python
async def sync_documents_to_chroma():
    """Sync document chunks from Neo4j to ChromaDB for vector search"""
    
    # Query Neo4j for document chunks
    cypher_query = """
    MATCH (d:Chunk)
    RETURN d.chunk_id, d.text, d.source, d.company, d.textEmbedding
    """
    
    # Insert into ChromaDB
    for record in neo4j_results:
        chroma_collection.add(
            ids=[record['d.chunk_id']],
            documents=[record['d.text']],
            metadatas=[{
                'source': record['d.source'],
                'company': record['d.company']
            }],
            embeddings=[record['d.textEmbedding']]
        )
```

### Data Backup and Recovery

**Automated Backup Strategy**:
```python
# Neo4j backup
def backup_neo4j():
    subprocess.run([
        'neo4j-admin', 'dump',
        '--database=neo4j',
        '--to=/backups/neo4j-backup.dump'
    ])

# ChromaDB backup
def backup_chroma():
    shutil.copytree(
        CHROMA_DB_PATH,
        f"/backups/chroma-{datetime.now().isoformat()}"
    )

# SQLite backup
def backup_sqlite():
    for db_path in [SESSION_DATABASE_PATH, SESSION_REPORT_DATABASE_PATH]:
        shutil.copy2(db_path, f"/backups/{os.path.basename(db_path)}.backup")
```

## 📈 Performance Optimization

### Neo4j Optimization

**Memory Configuration**:
```properties
# neo4j.conf optimizations
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G
dbms.default_database=neo4j
```

**Query Optimization**:
```cypher
-- Use indexes for filtering
MATCH (c:Company)
WHERE c.ticker = "AAPL"  -- Uses unique constraint index
RETURN c;

-- Efficient relationship traversal
MATCH (c:Company {ticker: "AAPL"})-[:HAS_METRIC]->(m:Metric)
WHERE m.name IN ["revenue", "profit"]  -- Index on m.name
RETURN m;
```

### ChromaDB Optimization

**Collection Settings**:
```python
chroma_client.create_collection(
    name="optimized_collection",
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:M": 16
    }
)
```

### SQLite Optimization

**Performance Settings**:
```sql
-- Optimize SQLite for read-heavy workloads
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = memory;
```

## 🔧 Database Maintenance

### Regular Maintenance Tasks

**Neo4j Maintenance**:
```cypher
-- Update statistics
CALL db.stats.retrieve('GRAPH COUNTS');

-- Cleanup orphaned nodes
MATCH (n) WHERE NOT (n)--() DELETE n;

-- Index maintenance
CALL db.indexes();
```

**ChromaDB Maintenance**:
```python
# Compact collections
collection.compact()

# Remove old documents
collection.delete(where={"timestamp": {"$lt": cutoff_date}})
```

**SQLite Maintenance**:
```sql
-- Vacuum databases
VACUUM;

-- Analyze query patterns
ANALYZE;

-- Cleanup old sessions
DELETE FROM sessions WHERE last_activity < date('now', '-30 days');
```

### Monitoring and Alerts

**Health Check Queries**:
```python
def check_database_health():
    health_status = {}
    
    # Neo4j health
    try:
        result = neo4j_driver.execute_query("RETURN 1 as test")
        health_status['neo4j'] = 'healthy'
    except Exception as e:
        health_status['neo4j'] = f'error: {str(e)}'
    
    # ChromaDB health
    try:
        collection_count = chroma_client.count_collections()
        health_status['chromadb'] = f'healthy ({collection_count} collections)'
    except Exception as e:
        health_status['chromadb'] = f'error: {str(e)}'
    
    # SQLite health
    try:
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        health_status['sqlite'] = f'healthy ({session_count} sessions)'
    except Exception as e:
        health_status['sqlite'] = f'error: {str(e)}'
    
    return health_status
```

## 🚀 Scaling Considerations

### Horizontal Scaling Options

**Neo4j Clustering**:
```yaml
# Future: Neo4j Cluster setup
neo4j-core-1:
  image: neo4j:5.23-enterprise
  environment:
    - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
    - NEO4J_dbms_mode=CORE
    - NEO4J_causal__clustering_initial__discovery__members=neo4j-core-1:5000,neo4j-core-2:5000,neo4j-core-3:5000
```

**Read Replicas**:
```python
# Read-only connections for query distribution
read_driver = GraphDatabase.driver(
    "bolt://neo4j-read-replica:7687",
    auth=("neo4j", "password")
)
```

### Sharding Strategies

**Company-based Sharding**:
```python
def get_database_shard(ticker: str) -> str:
    """Route companies to different database shards"""
    hash_value = hash(ticker) % 3
    return f"neo4j-shard-{hash_value}"
```

---

This multi-database architecture provides Get-Deep with the flexibility to handle diverse data types and access patterns while maintaining performance and consistency across the entire system.
