import csv
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
#from langchain.text_splitter import RecursiveCharacterTextSplitter
import time
from openai import OpenAI
from datetime import datetime
import logging
import traceback
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts.chat import ChatPromptTemplate
#from langchain.callbacks import get_openai_callback
from langchain_community.callbacks import get_openai_callback
from neo4j import GraphDatabase
import json
import pandas as pd
import tiktoken
import json
import asyncio
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor
import logging
from config import get_config
config = get_config()
import re
import random



class Neo4jTenKChunkManager:
    """Manager class for Neo4j TenKChunk node operations with token tracking"""
    
    def __init__(self, ticker, year):
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.ticker = ticker
        self.year = year
        """Initialize Neo4j connection"""
        NEO4J_URI = config.NEO4J_URI
        NEO4J_USERNAME = config.NEO4J_USERNAME
        NEO4J_PASSWORD = config.NEO4J_PASSWORD
        OPENAI_API_KEY = config.OPENAI_API_KEY
        
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        self.llm = ChatOpenAI(temperature=1, model=config.TENK_DATA_EXTRACTOR_OPENAI_MODEL_NAME, openai_api_key=OPENAI_API_KEY)
        
        # Token usage tracking
        self.total_tokens_used = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        self.successful_requests = 0
        self.lock = asyncio.Lock()  # For thread-safe updates

        # Add to additional_instructions in LLMGraphTransformer
        additional_instructions = """
        
        CRITICAL REQUIREMENTS:
        1. For every node extracted, including node properties is MANDATORY and COMPULSORY
        2. Do NOT extract or create relationships between nodes
        3. Focus exclusively on identifying entities and their comprehensive properties

        Node Extraction Rules:
        - Extract ALL relevant nodes from the text
        - Each node MUST include detailed properties
        - Properties should capture all relevant information about the entity
        - Include quantitative data (percentages, amounts, dates, counts)
        - Include qualitative descriptions and context

        Node ID Guidelines:
        - IDs must be specific and descriptive (3-7 words)
        - Use the node's core concept and key distinguishing features
        - Front-load the most distinctive/important terms
        - Use Title Case format
        - Avoid overly generic terms alone (e.g., don't use just "Risks" or "Information")

        Node Property Guidelines:
        - Extract comprehensive properties for each node
        - Use clear, descriptive property names (e.g., 'revenue_percentage_2018', 'geographic_concentration')
        - Include all numerical values, percentages, dates
        - Include all descriptive details and contextual information
        - Properties must provide substantive information about the node

        Remember: 
        - ALWAYS include properties for every node
        - NEVER create relationships between nodes
        - Focus on extraction completeness and accuracy

        """

                
        # Initialize the graph transformer with 10-K specific parameters
        self.transformer = LLMGraphTransformer(
            llm=self.llm,
            allowed_nodes=self.get_allowed_nodes(),
            allowed_relationships=False,
            strict_mode=True,
            node_properties=True,
            relationship_properties=True,
            ignore_tool_usage=False,
            additional_instructions= additional_instructions
        )

    def get_allowed_nodes(self):
        """Return the list of allowed nodes for the transformer."""
        return [
            # Item 1: Business
            "Company history and development",
            "Description of business segments",
            "Products and services offered",
            "Markets and customers",
            "Competition and competitive position",
            "Sales and marketing strategies",
            "Raw materials and suppliers",
            "Intellectual property",
            "Seasonality of business",
            "Government regulations",
            "Number of employees",
            "Available information",
            "Business risks",
            "Financial risks",
            "Legal and regulatory risks",
            "Market risks",
            "Operational risks",
            "Cybersecurity risks",
            "Environmental risks",
            "Risks related to intellectual property",
            "International operation risks",
            "Competition risks",
            "Unresolved staff comments",
            "Cybersecurity risk management processes",
            "Board oversight of cybersecurity",
            "Material cybersecurity incidents",
            "Real estate owned or leased",
            "Manufacturing facilities",
            "Office locations",
            "Distribution centers",
            "Storage facilities",
            "Operational properties",
            "Pending lawsuits",
            "Government investigations",
            "Regulatory actions",
            "Environmental proceedings",
            "Patent disputes",
            "Safety violations",
            "Safety incidents",
            "Stock price history",
            "Trading volume",
            "Stock exchange",
            "Number of shareholders",
            "Dividend history",
            "Dividend policy",
            "Stock performance graph",
            "Unregistered securities",
            "Share repurchase programs",
            "Financial results overview",
            "Year-over-year comparisons",
            "Revenue analysis by segment",
            "Expense analysis",
            "Liquidity analysis",
            "Capital resources",
            "Contractual obligations",
            "Off-balance sheet arrangements",
            "Critical accounting policies",
            "Forward-looking statements",
            "Market risks discussion",
            "Impact of inflation",
            "Recent accounting pronouncements",
            "Interest rate risk",
            "Foreign currency exchange risk",
            "Commodity price risk",
            "Equity price risk",
            "Credit risk",
            "Sensitivity analysis",
            "Consolidated Balance Sheets",
            "Consolidated Income Statements",
            "Consolidated Comprehensive Income",
            "Consolidated Cash Flow Statements",
            "Consolidated Shareholders Equity",
            "Accounting policies",
            "Revenue recognition policies",
            "Business combinations",
            "Acquisitions",
            "Discontinued operations",
            "Earnings per share",
            "Inventory details",
            "Property plant and equipment",
            "Goodwill",
            "Intangible assets",
            "Debt details",
            "Leases",
            "Income taxes",
            "Employee benefit plans",
            "Pensions",
            "401k plans",
            "Stock-based compensation",
            "Commitments and contingencies",
            "Segment information",
            "Fair value measurements",
            "Derivatives",
            "Hedging activities",
            "Related party transactions",
            "Subsequent events",
            "Quarterly financial data",
            "Auditing firm changes",
            "Disagreements with auditors",
            "Internal controls assessment",
            "Auditor report on controls",
            "Changes in internal controls",
            "Disclosure controls",
            "Foreign audit inspection issues",
            "Director names and backgrounds",
            "Executive officer information",
            "Board committee composition",
            "Audit committee expert",
            "Code of ethics",
            "Shareholder nominations",
            "Director independence",
            "Family relationships",
            "Summary compensation table",
            "Plan-based awards",
            "Outstanding equity awards",
            "Option exercises",
            "Stock vested",
            "Pension benefits",
            "Non-qualified deferred compensation",
            "Employment contracts",
            "Severance agreements",
            "Change-in-control agreements",
            "Compensation discussion and analysis",
            "Compensation committee report",
            "CEO pay ratio",
            "Pay versus performance",
            "Principal shareholders",
            "Director ownership",
            "Executive ownership",
            "Equity compensation plan info",
            "Securities authorized for issuance",
            "Related party transactions",
            "Business dealings with executives",
            "Director independence determination",
            "Audit fees",
            "Audit-related fees",
            "Tax fees",
            "Other fees",
            "Pre-approval policies",
            "Articles of Incorporation",
            "Bylaws",
            "Rights of security holders",
            "Material contracts",
            "Employment agreements",
            "Compensation plans",
            "Credit agreements",
            "Debt instruments",
            "Subsidiaries list",
            "Auditor consent letter",
            "Power of attorney",
            "CEO CFO certifications",
            "Code of ethics document",
            "Financial statement schedules",
            "Form 10-K summary",
        ]

    def split_csv_by_tokens(self, csv_path, col_name=None, max_tokens=10000, encoding_name="cl100k_base"):
        """Split a CSV (single column) OR TXT (line-per-row) into token-bounded chunks.

        Backward compatible:
        - If input is a .csv file, behavior stays the same: read first column and treat
          each cell as one "row".
        - If input is a .txt file, each line is treated as one "row".
        """

        path_str = str(csv_path)
        ext = os.path.splitext(path_str)[1].lower()

        print("Starting splitting input into chunks ....")

        # Build an iterable of row texts
        if ext == ".txt":
            # Each non-empty line = row
            with open(path_str, "r", encoding="utf-8", errors="ignore") as f:
                values = [ln.strip() for ln in f.read().splitlines()]
            values = [v for v in values if v != ""]
        else:
            # Default: CSV
            df = pd.read_csv(path_str)
            if col_name is None:
                col_name = df.columns[0]
            values = [str(v) for v in df[col_name].tolist()]

        encoding = tiktoken.get_encoding(encoding_name)
        chunks = []
        current_chunk = []
        current_tokens = 0

        for text in values:
            token_count = len(encoding.encode(text))

            if current_tokens + token_count > max_tokens and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                print(f"Chunk created with {current_tokens} tokens")
                current_tokens = 0

            current_chunk.append(text)
            current_tokens += token_count

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        print("Splitting into chunks Completed !")
        return chunks



    # @traceable(name="unstructured.process_chunk", metadata={"component": "data_ingestor", "stage": "process_chunk"})
    def _process_chunk_sync(self, chunk):
        """
        Synchronous function to process a chunk with token tracking.
        This runs in a thread pool to properly capture callback data.
        """
        doc = Document(page_content=chunk)
        
        with get_openai_callback() as cb:
            graph_document = self.transformer.convert_to_graph_documents([doc])[0]
            
            # Return both the graph document and token stats
            return {
                'graph_document': graph_document,
                'total_tokens': cb.total_tokens,
                'prompt_tokens': cb.prompt_tokens,
                'completion_tokens': cb.completion_tokens,
                'total_cost': cb.total_cost,
                'successful_requests': cb.successful_requests
            }



    # @traceable(name="unstructured.convert_to_graph_documents", metadata={"component": "data_ingestor"})
    async def convert_to_graph_documents(self, chunks, max_concurrent=20, max_retries=3, backoff_base=1.0, backoff_factor=2.0):
        """
        Convert text chunks to graph documents asynchronously with concurrency control and token tracking.
        
        Args:
            chunks: List of text chunks to process
            max_concurrent: Maximum number of concurrent processing operations (default: 20)
        
        Returns:
            List of graph documents
        """
        print(f"⏳ Starting async conversion of {len(chunks)} chunks to Graph Documents (max {max_concurrent} concurrent)...")
        start_time = time.time()

        async def process_chunk(chunk, index):
            """Process a single chunk with token tracking and return the graph document, with retries."""
            attempt = 1
            while attempt <= max_retries:
                try:
                    loop = asyncio.get_event_loop()
                    
                    # Run the synchronous processing in thread pool executor
                    result = await loop.run_in_executor(None, self._process_chunk_sync, chunk)
                    
                    # Update token usage (thread-safe)
                    async with self.lock:
                        self.total_tokens_used += result['total_tokens']
                        self.total_prompt_tokens += result['prompt_tokens']
                        self.total_completion_tokens += result['completion_tokens']
                        self.total_cost += result['total_cost']
                        self.successful_requests += result['successful_requests']
                    
                    retry_note = f" (after {attempt} attempt{'s' if attempt > 1 else ''})" if attempt > 1 else ""
                    print(f"✓ Processed chunk {index + 1}/{len(chunks)}{retry_note} | "
                          f"Tokens: {result['total_tokens']} "
                          f"(prompt: {result['prompt_tokens']}, completion: {result['completion_tokens']}) | "
                          f"Cost: ${result['total_cost']:.6f}")
                    
                    return result['graph_document']
                except Exception as e:
                    if attempt < max_retries:
                        wait = backoff_base * (backoff_factor ** (attempt - 1))
                        jitter = wait * (0.1 * random.random())
                        total_wait = wait + jitter
                        print(f"⚠️ Retry {attempt}/{max_retries - 1} failed for chunk {index + 1}: {str(e)}. Retrying in {total_wait:.2f}s...")
                        await asyncio.sleep(total_wait)
                        attempt += 1
                        continue
                    else:
                        print(f"✗ Error processing chunk {index + 1} after {max_retries} attempts: {str(e)}")
                        return None

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(chunk, index):
            """Process chunk with semaphore control."""
            async with semaphore:
                return await process_chunk(chunk, index)

        # Create tasks for all chunks
        tasks = []
        for idx, chunk in enumerate(chunks):
            task = process_with_semaphore(chunk, idx)
            tasks.append(task)

        # Execute all tasks concurrently (with semaphore limiting)
        graph_documents = await asyncio.gather(*tasks)

        # Filter out any None results from errors
        graph_documents = [doc for doc in graph_documents if doc is not None]

        end_time = time.time()
        elapsed_time = end_time - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        print("\n" + "=" * 70)
        print("📊 TOKEN USAGE SUMMARY")
        print("=" * 70)
        print(f"Total Tokens Used:        {self.total_tokens_used:,}")
        print(f"  ├─ Prompt Tokens:       {self.total_prompt_tokens:,}")
        print(f"  └─ Completion Tokens:   {self.total_completion_tokens:,}")
        print(f"Total Cost (USD):         ${self.total_cost:.6f}")
        print(f"Successful API Requests:  {self.successful_requests}")
        print(f"Chunks Processed:         {len(graph_documents)}/{len(chunks)}")
        print(f"Processing Time:          {minutes} min {seconds} sec")
        if graph_documents:
            print(f"Avg Tokens per Chunk:     {self.total_tokens_used / len(graph_documents):.1f}")
            print(f"Avg Cost per Chunk:       ${self.total_cost / len(graph_documents):.6f}")
        print("=" * 70 + "\n")
        
        return graph_documents




    def get_token_usage_stats(self):
        """
        Get current token usage statistics.
        
        Returns:
            dict: Token usage statistics
        """
        return {
            "total_tokens": self.total_tokens_used,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "successful_requests": self.successful_requests
        }

    def reset_token_stats(self):
        """Reset token usage statistics."""
        self.total_tokens_used = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        self.successful_requests = 0


    def save_graph_output(self, graph_documents: List, output_dir: str = None):
        """Save graph documents into clean, structured text files in temp directory"""
        print(f"Starting saving graph_documents ...")
        if output_dir is None:
            import tempfile
            base_temp_dir = tempfile.gettempdir()
            output_dir = os.path.join(base_temp_dir, "get_deep_graph_details", self.ticker, self.year)
        else:
            output_dir = f"{output_dir}/{self.ticker}/{self.year}"
        os.makedirs(output_dir, exist_ok=True)
        
        for idx, gdoc in enumerate(graph_documents, start=1):
            file_path = os.path.join(output_dir, f"chunk_{idx}.txt")

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"==== GRAPH DOCUMENT {idx} ====\n\n")

                    # NODES SECTION
                    f.write("🟩 NODES:\n")
                    if hasattr(gdoc, "nodes") and gdoc.nodes:
                        for n_idx, node in enumerate(gdoc.nodes, start=1):
                            f.write(f"\n-- Node {n_idx} --\n")
                            f.write(f"ID: {node.id}\n")
                            f.write(f"Type: {node.type}\n")

                            if hasattr(node, "properties") and node.properties:
                                f.write("Properties:\n")
                                for k, v in node.properties.items():
                                    f.write(f"  - {k}: {v}\n")
                            else:
                                f.write("Properties: None\n")
                    else:
                        f.write("No nodes found.\n")

                    f.write("\n" + "=" * 60 + "\n")

                    # RELATIONSHIPS SECTION
                    f.write("\n🟦 RELATIONSHIPS:\n")
                    if hasattr(gdoc, "relationships") and gdoc.relationships:
                        for r_idx, rel in enumerate(gdoc.relationships, start=1):
                            f.write(f"\n-- Relationship {r_idx} --\n")
                            f.write(f"Source: {rel.source_id}\n")
                            f.write(f"Target: {rel.target_id}\n")
                            f.write(f"Type: {rel.type}\n")

                            if hasattr(rel, "properties") and rel.properties:
                                f.write("Properties:\n")
                                for k, v in rel.properties.items():
                                    f.write(f"  - {k}: {v}\n")
                            else:
                                f.write("Properties: None\n")
                    else:
                        f.write("No relationships found.\n")

                    f.write("\n" + "=" * 60 + "\n")

                    # SOURCE SECTION
                    f.write("\n📄 SOURCE CONTENT:\n")
                    if hasattr(gdoc, "source") and hasattr(gdoc.source, "page_content"):
                        f.write(f"{gdoc.source.page_content.strip()}\n")
                    else:
                        f.write("No source content found.\n")

                #print(f"✓ Saved structured graph to {file_path}")
                print(f"graph documents saving is completed !")

            except Exception as e:
                print(f"✗ Error saving {file_path}: {e}")

    def create_constraints_and_indexes(self, kg):
        """Create necessary constraints and indexes"""
        print("Creating constraints and indexes...")

        # Create uniqueness constraint for chunks
        kg.query("""
        CREATE CONSTRAINT unique_chunk IF NOT EXISTS 
            FOR (c:Chunk) REQUIRE c.chunkId IS UNIQUE
        """)

        # Create vector index for text embeddings
        kg.query("""
        CREATE VECTOR INDEX `form_10k_chunks` IF NOT EXISTS
            FOR (c:Chunk) ON (c.textEmbedding) 
            OPTIONS { indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'    
            }}
        """)

        print("Constraints and indexes created successfully")

    
    def restructuring_graph_documents(self, graph_documents, ticker, year):
        """
        Convert LangChain graph_documents into a single Restructured_Graph_Documents dictionary.
        
        Args:
            graph_documents (list): List of graph documents from LLMGraphTransformer.
            ticker (str): Ticker of the company.
            year (int): Year to include in the document.

        Returns:
            dict: Restructured graph documents dictionary with nodes grouped by type.
            
        """
        print("Starting Restructuring Graph Documents...")
        
        Restructured_Graph_Documents = {"ticker": ticker, "year": year}
        
        for gdoc in graph_documents:
            for node in gdoc.nodes:
                node_type = node.type
                # Initialize list for this node type if not exists
                if node_type not in Restructured_Graph_Documents:
                    Restructured_Graph_Documents[node_type] = []
                
                # Create node entry with node_id and properties
                node_entry = {
                    "node_id": node.id,  # ADD THIS: Include node ID
                    "properties": node.properties if hasattr(node, "properties") and node.properties else {}
                }
                
                Restructured_Graph_Documents[node_type].append(node_entry)
        
        print("Restructuring Graph Documents is Completed!")
        return Restructured_Graph_Documents




    # @traceable(name="neo4j.create_or_extend_tenk_chunk", metadata={"component": "data_ingestor"})
    def create_or_extend_tenk_chunk(self, Restrctured_Graph_Documents):
        """
        Create or merge a TenKChunk node in Neo4j.
        If a node with the same ticker AND year exists, append new attributes to existing ones.
        Otherwise, create a new node.
        All properties are stored directly on the node (not in a 'data' JSON field).
        
        Args:
            Restrctured_Graph_Documents (dict): Dictionary containing TenKChunk node data
            
        Returns:
            dict: Result information including whether node was created or merged
        """
        print("Starting Creating TenKChunk nodes...")
        ticker = Restrctured_Graph_Documents.get("ticker")
        year = Restrctured_Graph_Documents.get("year")
        
        if not ticker:
            raise ValueError("ticker is required in tenk_chunk_data")
        if not year:
            raise ValueError("year is required in tenk_chunk_data")

        with self.driver.session() as session:
            
            #print("starting ...")
            # Check if node exists with BOTH ticker AND year
            check_query = """
            MATCH (chunk:TenKChunk {ticker: $ticker, year: $year})
            RETURN chunk
            """
            result = session.run(check_query, ticker=ticker, year=year)
            existing_node = result.single()

            if existing_node:
                
                # for now not to inject duplicates 
                print("node already exist ...")
                return True
                # Node exists - merge new properties
                existing_data = dict(existing_node["chunk"])
                current_data = existing_data.copy()
                
                # Merge new keys with existing ones
                for key, value in Restrctured_Graph_Documents.items():
                    if key in ["ticker", "year"]:
                        continue  # skip these base properties
                    
                    if key in current_data:
                        # If both are lists, extend the existing list
                        if isinstance(current_data[key], str) and isinstance(value, list):
                            data_list = json.loads(current_data[key])
                            data_list.extend(value)
                            current_data[key] = json.dumps(data_list)
                            #print("in here extending ..")
                        else:
                            pass
                            #print("diferat ..")
                    else:
                        # New property, add it
                        current_data[key] = value
                        #print("in New property, add it ..")

                # Build SET clause dynamically for all properties
                set_clauses = []
                params = {"ticker": ticker, "year": year}
                
                for key, value in current_data.items():
                    if key not in ["ticker", "year"]:
                        # Convert lists/dicts to JSON strings for storage
                        if isinstance(value, (list, dict)):
                            param_key = f"prop_{key.replace(' ', '_').replace('-', '_')}"
                            params[param_key] = json.dumps(value)
                            set_clauses.append(f"chunk.`{key}` = ${param_key}")
                        else:
                            param_key = f"prop_{key.replace(' ', '_').replace('-', '_')}"
                            params[param_key] = value
                            set_clauses.append(f"chunk.`{key}` = ${param_key}")
                
                set_clauses.append("chunk.updatedAt = datetime()")
                set_clause_str = ", ".join(set_clauses)
                
                update_query = f"""
                MATCH (chunk:TenKChunk {{ticker: $ticker, year: $year}})
                SET {set_clause_str}
                RETURN chunk, 'merged' as action
                """
                result = session.run(update_query, **params)
                
            else:
                #print("creating new ...")
                # Node doesn't exist - create new one with all properties
                params = {"ticker": ticker, "year": year}
                set_clauses = ["chunk.ticker = $ticker", "chunk.year = $year"]
                
                for key, value in Restrctured_Graph_Documents.items():
                    if key not in ["ticker", "year"]:
                        # Convert lists/dicts to JSON strings for storage
                        if isinstance(value, (list, dict)):
                            param_key = f"prop_{key.replace(' ', '_').replace('-', '_')}"
                            params[param_key] = json.dumps(value)
                            set_clauses.append(f"chunk.`{key}` = ${param_key}")
                        else:
                            param_key = f"prop_{key.replace(' ', '_').replace('-', '_')}"
                            params[param_key] = value
                            set_clauses.append(f"chunk.`{key}` = ${param_key}")
                
                set_clauses.append("chunk.createdAt = datetime()")
                set_clauses.append("chunk.updatedAt = datetime()")
                set_clause_str = ", ".join(set_clauses)
                
                create_query = f"""
                CREATE (chunk:TenKChunk)
                SET {set_clause_str}
                RETURN chunk, 'created' as action
                """
                result = session.run(create_query, **params)

            record = result.single()
            if record:
                print("TenKChunk Nodes Creation is Completed !")
                return {
                    "success": True,
                    "action": record["action"],
                    "ticker": ticker,
                    "year": year,
                    "node": dict(record["chunk"])
                }
            
            return {"success": False}
    
    # @traceable(name="neo4j.create_company_tenk_relationship", metadata={"component": "data_ingestor"})
    def create_company_tenk_relationship(self, ticker, year=None):
        """
        Create HAS_TENK_DATA relationship from Company node to TenKChunk node(s).
        
        Args:
            ticker (str): ticker the company (must match both Company.ticker and TenKChunk.ticker)
            year (int, optional): Specific year. If None, creates relationships for all years.
            
        Returns:
            dict: Result information including number of relationships created
        """
        print("Creating Company vs TenKChunk relationships ...")
        with self.driver.session() as session:

            query = """
            MATCH (c:Company {ticker: $ticker})
            MATCH (t:TenKChunk {ticker: $ticker, year: $year})
            MERGE (c)-[r:HAS_TENK_DATA]->(t)
            SET r.createdAt = CASE WHEN r.createdAt IS NULL THEN datetime() ELSE r.createdAt END
            SET r.updatedAt = datetime()
            RETURN count(r) as relationshipsCreated
            """
            result = session.run(query, ticker=ticker, year=year)
            record = result.single()
            if record:
                print("Company vs TenKChunk relationships creation completed !")
                return {
                    "success": True,
                    "ticker": ticker,
                    "year": year,
                    "relationshipsCreated": record["relationshipsCreated"]
                }
            return {
                "success": False,
                "message": "No matching Company or TenKChunk nodes found"
            }
    
    
    def tenk_chunk_exists(self):
        """Check if a TenKChunk exists for the manager's ticker and year."""
        with self.driver.session() as session:
            query = """
            MATCH (chunk:TenKChunk {ticker: $ticker, year: $year})
            RETURN count(chunk) > 0 as exists
            """
            result = session.run(query, ticker=self.ticker, year=self.year)
            record = result.single()
            return bool(record and record["exists"])


    def number_of_properties_except_ticker_and_year(self):
        """Return the number of properties in TenKChunk node except ticker and year."""
        with self.driver.session() as session:
            query = """
            MATCH (chunk:TenKChunk {ticker: $ticker, year: $year})
            WITH [k IN keys(chunk) WHERE k <> 'ticker' AND k <> 'year'] AS filtered_keys
            RETURN size(filtered_keys) AS property_count
            """
            result = session.run(query, ticker=self.ticker, year=self.year)
            record = result.single()
            return record["property_count"] if record else 0
    

    def delete_chunk(self):
        """Delete the TenKChunk node with the given ticker and year."""
        with self.driver.session() as session:
            query = """
            MATCH (chunk:TenKChunk {ticker: $ticker, year: $year})
            DETACH DELETE chunk
            RETURN true AS deleted
            """
            result = session.run(query,ticker=self.ticker,year=self.year)
            record = result.single()
            return bool(record and record["deleted"])


    def ensure_year_integer(self):
        """Ensure existing TenKChunk.year is stored as integer for this manager's ticker/year."""
        with self.driver.session() as session:
            query = """
            MATCH (t:TenKChunk {ticker: $ticker})
            WHERE toString(t.year) = $year_str OR t.year = $year_int
            SET t.year = toInteger(t.year)
            RETURN count(t) AS updated
            """
            session.run(query, ticker=self.ticker, year_str=str(self.year), year_int=self.year)

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()




# @traceable(name="unstructured.tenK_data_injestor", metadata={"component": "data_ingestor"})
async def tenK_data_injestor(file_path):

    response = {
        "status": "success",
        "message": "",
        "error": None,
        "http_status": 200,
        "token_stats": {}
    }
        
    """
    Async version of the 10-K data injector with token usage tracking.
    Validates ticker and year before processing.
    """
    filename = os.path.splitext(os.path.basename(file_path))[0]
    parts = filename.split("_")
    
    # Basic validation: expecting format like "TICKER_YEAR"
    if len(parts) < 2:
        logging.error(f"Invalid filename format for {file_path}. Expected 'TICKER_YEAR'.")
        response["status"] = "error"
        response["message"] = f"Invalid filename format. Expected 'TICKER_YEAR'."
        response["error"] = "Invalid filename format"
        response["http_status"] = 400
        return response

    ticker, year_str = parts[0], parts[1]

    # ✅ Validate ticker (only uppercase letters, any length)
    if not re.match(r"^[A-Z]+$", ticker):
        logging.error(f"Invalid ticker '{ticker}' in filename {file_path}.")
        response["status"] = "error"
        response["message"] = f"Invalid ticker '{ticker}'. Must contain only uppercase letters."
        response["error"] = "Invalid ticker format"
        response["http_status"] = 400
        return response

    # Validate year (4 digits, reasonable range)
    if not (year_str.isdigit() and 1900 <= int(year_str) <= 2100):
        logging.error(f"Invalid year '{year_str}' in filename {file_path}.")
        response["status"] = "error"
        response["message"] = f"Invalid year '{year_str}'. Must be a 4-digit year between 1900-2100."
        response["error"] = "Invalid year format"
        response["http_status"] = 400
        return response

    year = int(year_str)
    neo4j_manager = Neo4jTenKChunkManager(ticker, year)
    # Ensure any existing TenKChunk nodes for this ticker/year use integer type for `year`
    neo4j_manager.ensure_year_integer()

    # Pre-check: if TenKChunk exists for this ticker and year, skip ingestion
    try:
        if neo4j_manager.tenk_chunk_exists():

            number_of_properties_except_ticker_and_year = neo4j_manager.number_of_properties_except_ticker_and_year()
            if number_of_properties_except_ticker_and_year <= 6:
                deleted = neo4j_manager.delete_chunk()
            else:
                logging.info(f"TenKChunk already exists for ticker={ticker}, year={year}; skipping ingestion.")
                response["status"] = "success"
                response["message"] = f"TenKChunk already exists for {ticker} {year}. Skipping ingestion."
                response["token_stats"] = neo4j_manager.get_token_usage_stats()
                response["http_status"] = 200
                neo4j_manager.close()
                return response
        

    except Exception as e:
        logging.warning(f"Pre-check for existing TenKChunk failed: {e}. Proceeding with ingestion.")
        response["status"] = "error"
        response["message"] = f"Pre-check for existing TenKChunk failed for {ticker} {year}."
        response["error"] = str(e)
        response["http_status"] = 500


    try:
        chunks = neo4j_manager.split_csv_by_tokens(file_path, max_tokens=2000)
        graph_documents = await neo4j_manager.convert_to_graph_documents(chunks, max_concurrent=20)
        
        # ✅ Get final token stats
        token_stats = neo4j_manager.get_token_usage_stats()
        print(f"\n🎯 Final Token Statistics:")
        print(f"   Total Cost: ${token_stats['total_cost_usd']}")
        print(f"   Total Tokens: {token_stats['total_tokens']:,}")
        
        neo4j_manager.save_graph_output(graph_documents)
        Restrctured_Graph_Documents = neo4j_manager.restructuring_graph_documents(graph_documents, ticker, year)
        neo4j_manager.create_or_extend_tenk_chunk(Restrctured_Graph_Documents)
        # Relationship creation moved to a dedicated function:
        # call create_company_tenk_relationship_for(ticker, year) after ingestion when needed.
        
        response["status"] = "success"
        response["message"] = f"Successfully ingested 10-K data for {ticker} {year}."
        response["token_stats"] = token_stats
        response["http_status"] = 200

    except Exception as e:
        logging.error(f"Error processing Unstructured data file {file_path}: {e}")
        response["status"] = "error"
        response["message"] = f"Failed to process 10-K data for {ticker} {year}."
        response["error"] = str(e)
        response["http_status"] = 500
    finally:
        neo4j_manager.close()

    return response
    



###################
###################



def create_all_company_tenk_relationships():
    """
    Create HAS_TENK_DATA relationships between ALL Company and TenKChunk nodes
    where tickers match. No arguments required.
    
    Returns:
        dict: {"success": bool, "relationshipsCreated": int} on success,
              or {"success": False, "message": str} on error.
    """
    try:
        NEO4J_URI = config.NEO4J_URI
        NEO4J_USERNAME = config.NEO4J_USERNAME
        NEO4J_PASSWORD = config.NEO4J_PASSWORD

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session() as session:
            query = """
            MATCH (c:Company), (t:TenKChunk)
            WHERE t.ticker = c.ticker
            MERGE (c)-[r:HAS_TENK_DATA]->(t)
            SET r.createdAt = CASE WHEN r.createdAt IS NULL THEN datetime() ELSE r.createdAt END,
                r.updatedAt = datetime()
            RETURN count(r) AS relationshipsCreated
            """
            record = session.run(query).single()
            created = int(record["relationshipsCreated"]) if record else 0
            print(f"Company vs TenKChunk relationships creation completed for all: {created}")
            return {"success": True, "relationshipsCreated": created}
    except Exception as e:
        logging.error(f"Error creating HAS_TENK_DATA for all companies: {e}")
        return {"success": False, "message": str(e)}
    finally:
        try:
            driver.close()
        except Exception:
            pass



if __name__ == "__main__":

    file_path = "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/TGT/TGT_2025_10K_granular_extract.csv"
    file_path = "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/BJ/BJ_2019_10K_granular_extract.csv"
    file_path = "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/DLTR/DLTR_2013_10K_granular_extract.csv"
    file_path = "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/WMT/WMT_2020_10K_granular_extract.csv"
    file_path = "/Users/dimuth/Documents/chat_bot/Get-Deep/data/unstructured/COST/COST_2018_10K_granular_extract.csv"

    # Run the async function
    asyncio.run(tenK_data_injestor(file_path))
