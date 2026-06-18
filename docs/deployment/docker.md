# Docker Deployment Guide

Get-Deep is designed for seamless deployment using Docker and Docker Compose. This guide covers production deployment, development setup, and container management.

## 🐳 Container Architecture

The application uses a multi-container architecture with separate services for different components:

```
┌─────────────────┐    ┌─────────────────┐
│   Neo4j Graph   │    │   Get-Deep      │
│   Database      │◄──►│   Application   │
│   (Port 7474)   │    │   (Port 8080)   │
└─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

### System Requirements

**Minimum Requirements**:
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM
- 20GB disk space

**Recommended Requirements**:
- Docker Engine 24.0+
- Docker Compose 2.20+
- 8GB RAM
- 50GB disk space
- SSD storage for database

### Platform Support

- ✅ **Linux** (Ubuntu 20.04+, CentOS 8+, RHEL 8+)
- ✅ **macOS** (Intel and Apple Silicon)
- ✅ **Windows** (Windows 10/11 with WSL2)

## 🚀 Quick Start Deployment

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd Get-Deep

# Create environment file
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` file with your settings:

```env
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
ALPHA_VANTAGE_API_KEY=your_alphavantage_key_here

# Database Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
GRAPH_DATA_BASE_AVAILABILITY=YES
CHROMA_DATA_BASE_AVAILABILITY=NO

# Application Configuration
APP_ENV=production
CHAT_MODEL_NAME=gpt-4o
EMBEDDINGS_MODEL_NAME=text-embedding-ada-002
```

### 3. Deploy Services

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f
```

### 4. Verify Deployment

```bash
# Test API health
curl http://localhost:8080/health

# Test Neo4j connection
curl http://localhost:7474

# View application logs
docker compose logs chatbot
```

## 🔧 Docker Compose Configuration

### Complete docker-compose.yml

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.23-community
    container_name: neo4j-DataStore
    restart: unless-stopped
    ports:
      - "7474:7474"  # HTTP interface
      - "7687:7687"  # Bolt protocol
    networks:
      - my_network
    volumes:
      # Choose appropriate volume mapping for your OS
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_conf:/conf
      - neo4j_plugins:/plugins
      - neo4j_import:/import
    environment:
      - NEO4J_AUTH=neo4j/your_neo4j_password_here
      - NEO4J_PLUGINS=["apoc", "genai"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,genai.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*,genai.*
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
      - NEO4J_dbms_default__listen__address=0.0.0.0
      - NEO4J_server_config_strict__validation_enabled=false
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s

  chatbot:
    image: dimuthsenz/getdeep:v3
    container_name: deep
    restart: unless-stopped
    init: true
    ports:
      - "8080:8080"
    networks:
      - my_network
    volumes:
      - ./.env:/home/GetDeep/src/.env:ro
    depends_on:
      neo4j:
        condition: service_healthy
    environment:
      - APP_ENV=production
    command: ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--app-dir", "src"]
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    stop_grace_period: 30s

volumes:
  neo4j_data:
    driver: local
  neo4j_logs:
    driver: local
  neo4j_conf:
    driver: local
  neo4j_plugins:
    driver: local
  neo4j_import:
    driver: local

networks:
  my_network:
    driver: bridge
```

### Platform-Specific Volume Configurations

#### Linux/Server Deployment
```yaml
volumes:
  - /opt/neo4j/data:/data
  - /opt/neo4j/logs:/logs
  - /opt/neo4j/conf:/conf
  - /opt/neo4j/plugins:/plugins
  - /opt/neo4j/import:/import
```

#### macOS Development
```yaml
volumes:
  - ~/Documents/get-deep/neo4j_data:/data
  - ~/Documents/get-deep/neo4j_logs:/logs
  - ~/Documents/get-deep/neo4j_conf:/conf
  - ~/Documents/get-deep/neo4j_plugins:/plugins
  - ~/Documents/get-deep/neo4j_import:/import
```

#### Windows Development
```yaml
volumes:
  - C:/Users/YourUsername/Documents/neo4j_data:/data
  - C:/Users/YourUsername/Documents/neo4j_logs:/logs
  - C:/Users/YourUsername/Documents/neo4j_conf:/conf
  - C:/Users/YourUsername/Documents/neo4j_plugins:/plugins
  - C:/Users/YourUsername/Documents/neo4j_import:/import
```

## 🏗️ Custom Docker Build

### Building the Application Image

```bash
# Build the image
docker build -t getdeep:local .

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.12 -t getdeep:python312 .

# Build for production with optimizations
docker build --target production -t getdeep:prod .
```

### Multi-Stage Dockerfile Analysis

```dockerfile
# Stage 1: Base system setup
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Stage 2: Python and system dependencies
RUN apt-get update && \
    apt-get install -y python3.12 python3.12-venv python3.12-dev \
    build-essential libffi-dev libssl-dev git wget curl iputils-ping net-tools nano openssl tini

# Stage 3: Python environment and dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Stage 4: Cythonization for performance
ENV DELETE_APP_PY=true
RUN python cythonizing_repo.py

# Stage 5: Security and runtime
RUN useradd -m -u 10001 appuser && \
    chown -R appuser:appuser /home/GetDeep /opt/venv
USER appuser

# Stage 6: Runtime configuration
EXPOSE 8080
ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--app-dir", "src"]
```

### Build Optimizations

**Development Build**:
```bash
# Disable Cythonization for faster builds
docker build --build-arg SKIP_CYTHON=true -t getdeep:dev .
```

**Production Build with Multi-Stage**:
```dockerfile
# Multi-stage build for smaller production image
FROM ubuntu:24.04 as builder
# ... build dependencies and compilation

FROM ubuntu:24.04 as runtime
# ... copy only runtime artifacts
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /home/GetDeep /home/GetDeep
```

## 🌐 Production Deployment

### Reverse Proxy Setup

#### Nginx Configuration

```nginx
# /etc/nginx/sites-available/getdeep
upstream getdeep_backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/private.key;

    # API endpoints
    location / {
        proxy_pass http://getdeep_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for streaming
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Neo4j Browser (optional, for development)
    location /neo4j/ {
        proxy_pass http://127.0.0.1:7474/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Traefik Configuration (Alternative)

```yaml
# docker-compose.prod.yml
services:
  traefik:
    image: traefik:v3.0
    command:
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.letsencrypt.acme.email=your-email@domain.com
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - letsencrypt_data:/letsencrypt

  chatbot:
    # ... existing configuration
    labels:
      - traefik.enable=true
      - traefik.http.routers.getdeep.rule=Host(`your-domain.com`)
      - traefik.http.routers.getdeep.tls.certresolver=letsencrypt
      - traefik.http.services.getdeep.loadbalancer.server.port=8080
```

### Environment-Specific Configurations

#### Production Environment
```yaml
# docker-compose.prod.yml
services:
  chatbot:
    environment:
      - APP_ENV=production
      - DEBUG_ENABLE=false
      - LOG_LEVEL=INFO
      - UVICORN_WORKERS=4
    deploy:
      resources:
        limits:
          memory: 6g
          cpus: '2.0'
        reservations:
          memory: 4g
          cpus: '1.0'
```

#### Staging Environment
```yaml
# docker-compose.staging.yml
services:
  chatbot:
    environment:
      - APP_ENV=staging
      - DEBUG_ENABLE=true
      - LOG_LEVEL=DEBUG
      - UVICORN_RELOAD=false
```

## 📊 Monitoring and Logging

### Container Health Monitoring

```bash
# Check container health
docker compose ps
docker inspect deep --format='{{.State.Health.Status}}'

# Monitor resource usage
docker stats

# View real-time logs
docker compose logs -f --tail=100 chatbot
docker compose logs -f --tail=100 neo4j
```

### Log Management

#### Centralized Logging with ELK Stack

```yaml
# docker-compose.logging.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    ports:
      - "5601:5601"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.10.0

  chatbot:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
        labels: "service=getdeep"
```

### Application Metrics

```python
# Add to your application for metrics collection
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('getdeep_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('getdeep_request_duration_seconds', 'Request latency')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_LATENCY.observe(time.time() - start_time)
    
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

## 🚨 Troubleshooting

### Common Issues and Solutions

#### Container Won't Start
```bash
# Check container logs
docker compose logs chatbot

# Check resource constraints
docker system df
docker system prune

# Verify port availability
netstat -tulpn | grep :8080
```

#### Database Connection Issues
```bash
# Test Neo4j connectivity
docker exec neo4j-DataStore cypher-shell -u neo4j -p your_neo4j_password_here "RETURN 1"

# Check Neo4j logs
docker compose logs neo4j

# Reset Neo4j data (WARNING: destructive)
docker compose down
docker volume rm getdeep_neo4j_data
docker compose up -d
```

#### Performance Issues
```bash
# Monitor container resources
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Increase memory limits
# Edit docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 8g
```

#### API Response Timeouts
```python
# Increase timeout settings in config.py
UVICORN_TIMEOUT_KEEP_ALIVE = 65
REQUEST_TIMEOUT = 300

# Or in docker-compose.yml:
command: ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8080", "--timeout-keep-alive", "65"]
```

### Health Check Scripts

```bash
#!/bin/bash
# health-check.sh

echo "Checking Get-Deep deployment health..."

# API Health
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
if [ $API_STATUS -eq 200 ]; then
    echo "✅ API is healthy"
else
    echo "❌ API is unhealthy (HTTP $API_STATUS)"
fi

# Neo4j Health
NEO4J_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:7474)
if [ $NEO4J_STATUS -eq 200 ]; then
    echo "✅ Neo4j is healthy"
else
    echo "❌ Neo4j is unhealthy (HTTP $NEO4J_STATUS)"
fi

# Container Status
CHATBOT_RUNNING=$(docker ps --filter "name=deep" --filter "status=running" -q)
if [ ! -z "$CHATBOT_RUNNING" ]; then
    echo "✅ Chatbot container is running"
else
    echo "❌ Chatbot container is not running"
fi
```

## 🔄 Updates and Maintenance

### Application Updates

```bash
# Pull latest images
docker compose pull

# Update with zero downtime
docker compose up -d --no-deps chatbot

# Rollback if needed
docker tag dimuthsenz/getdeep:v3 dimuthsenz/getdeep:backup
docker compose down
docker compose up -d
```

### Database Backups

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups/$(date +%Y-%m-%d)"
mkdir -p $BACKUP_DIR

# Neo4j backup
docker exec neo4j-DataStore neo4j-admin database dump --to-path=/backups neo4j
docker cp neo4j-DataStore:/backups/neo4j.dump $BACKUP_DIR/

# SQLite backups
docker cp deep:/home/GetDeep/src/databases $BACKUP_DIR/sqlite_dbs

echo "Backup completed: $BACKUP_DIR"
```

### Scheduled Maintenance

```bash
# Add to crontab for regular maintenance
# m h dom mon dow command
0 2 * * 0 /path/to/maintenance.sh  # Weekly maintenance at 2 AM Sunday

# maintenance.sh
#!/bin/bash
docker system prune -f
docker compose restart neo4j
docker compose logs --tail=100 > /var/log/getdeep/weekly-$(date +%Y-%m-%d).log
```

---

This comprehensive Docker deployment guide ensures reliable, scalable, and maintainable deployment of the Get-Deep platform across different environments and use cases.
