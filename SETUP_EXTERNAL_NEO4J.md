# Setup Instructions: External Neo4j Configuration

This document provides instructions for running the Get-Deep system with an external Neo4j cloud instance.

## Overview

The system has been modified to connect to your external Neo4j instance at `http://34.68.84.147:7474` instead of running a local Neo4j container.

## Changes Made

### 1. Docker Compose Modifications
- ✅ **Removed local Neo4j service** from `docker-compose.yml`
- ✅ **Removed Neo4j dependency** from chatbot service
- ✅ **Updated volume paths** from Windows to Linux paths
- ✅ **Simplified service architecture** for external database connection

### 2. Configuration Files
- ✅ **Created `.env.template`** with external Neo4j configuration
- ✅ **Updated volume mount path** to use correct Linux path
- ✅ **Created connection test script** (`test_neo4j_connection.py`)

## Setup Steps

### Step 1: Create Environment File
Copy the template and configure your settings:

```bash
cp .env.template .env
```

Edit `.env` file and update the following values:
```bash
# Neo4j Configuration - External Cloud Instance
NEO4J_URI=http://34.68.84.147:7474
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here

# Add your actual API keys
OPENAI_API_KEY=your_actual_openai_key_here
GOOGLE_API_KEY=your_actual_google_key_here
TAVILY_API_KEY=your_actual_tavily_key_here
ALPHA_VANTAGE_API_KEY=your_actual_alpha_vantage_key_here
```

### Step 2: Verify Neo4j Connection (Optional)
Install required packages and test connection:

```bash
pip install neo4j requests python-dotenv
python3 test_neo4j_connection.py
```

Expected output should show:
- ✅ Neo4j HTTP endpoint is accessible
- ✅ Neo4j driver connection successful
- ✅ Query test successful

### Step 3: Run the System
Start the application using Docker Compose:

```bash
docker compose up -d
```

### Step 4: Verify Application
Check that the application is running:

```bash
# Check container status
docker compose ps

# Check application logs
docker compose logs -f chatbot

# Test health endpoint
curl http://localhost:8080/health
```

## Connection Details

| Parameter | Value |
|-----------|-------|
| **Neo4j HTTP URI** | `http://34.68.84.147:7474` |
| **Neo4j Bolt URI** | `bolt://34.68.84.147:7687` |
| **Username** | `neo4j` |
| **Password** | `your_neo4j_password_here` |
| **Application Port** | `http://localhost:8080` |

## Neo4j Browser Access

You can access the Neo4j browser interface directly at:
- **URL**: `http://34.68.84.147:7474`
- **Username**: `neo4j`
- **Password**: `your_neo4j_password_here`

## Troubleshooting

### Connection Issues
If you encounter connection issues:

1. **Check network connectivity**:
   ```bash
   curl -I http://34.68.84.147:7474
   ```

2. **Verify Neo4j service is running**:
   ```bash
   telnet 34.68.84.147 7474
   ```

3. **Check application logs**:
   ```bash
   docker compose logs chatbot
   ```

### Environment Variables
Ensure all required environment variables are set in `.env`:
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `OPENAI_API_KEY`
- Other API keys as needed

### Docker Issues
If Docker issues occur:

```bash
# Restart services
docker compose down
docker compose up -d

# Rebuild if needed
docker compose down
docker compose up -d --build
```

## Security Notes

- **Firewall**: Ensure Neo4j ports (7474, 7687) are accessible from your local machine
- **Authentication**: The system uses basic authentication (neo4j/your_neo4j_password_here)
- **SSL**: Currently configured for HTTP connection (not HTTPS)

## File Structure Changes

```
/home/sajeepan/your_neo4j_password_here/Get-Deep/
├── .env                          # Your environment configuration
├── .env.template                 # Template with external Neo4j config
├── docker-compose.yml            # Modified to use external Neo4j
├── test_neo4j_connection.py      # Connection test script
└── SETUP_EXTERNAL_NEO4J.md      # This file
```

## Next Steps

1. ✅ **Configure `.env` file** with your actual API keys
2. ✅ **Test Neo4j connection** using the provided test script
3. ✅ **Start the application** with `docker compose up -d`
4. ✅ **Verify functionality** by testing the application endpoints
5. ✅ **Monitor logs** to ensure proper operation

## Support

If you encounter any issues:
1. Check the application logs: `docker compose logs -f`
2. Verify Neo4j connectivity using the test script
3. Ensure all environment variables are properly configured
4. Check that the external Neo4j instance is accessible and running
