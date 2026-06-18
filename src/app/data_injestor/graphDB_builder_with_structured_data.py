import os
import json
import logging
import tempfile
import traceback
from typing import List

# Third-party imports
import pandas as pd
import numpy as np
from fastapi import UploadFile
from neo4j.exceptions import ServiceUnavailable, AuthError
from fastapi import HTTPException


# Local application imports
from config import get_config
config = get_config()


# company_details
required_columns_c = [
    'ticker',
    'companyName',
    'website',
    'founded',
    'country',
    'state',
    'marketCapGroup',
    'ipoDate',
    'exchange',
    'isSPAC',
    'fyEnd',
    'sicCode',
    'cusipNumber',
    'cikCode',
    'isinNumber'
]


# company_industry_mapping
required_columns_ci = [
    'companyId',
    'industryId' 
       
]

# company_competitors
required_columns_cc = [
    'companyId',
    'companyName'
]

# industry_sector_mapping
required_columns_is =[
    'industryId',
    'industryName', 
    'sectorName', 
    'sectorId'
]

# industry_statistics
required_columns_i = [
    'countOfCompanies',
    'industryId' , 
    'industryName'
]

# sector_statistics
required_columns_s = [
    'countOfIndustries',
    'sectorId',
    'sectorName'
]




# Optional Neo4j imports (install with: pip install neo4j)
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("Neo4j driver not available. Using NetworkX only.")


class GraphDatabaseBuilder:
    def __init__(self, neo4j_uri=None, neo4j_user=None, neo4j_password=None):
        """
        Initialize the Graph Database Builder

        Args:
            neo4j_uri: Neo4j database URI (optional)
            neo4j_user: Neo4j username (optional) 
            neo4j_password: Neo4j password (optional)
        """
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Initialize Neo4j driver if credentials provided
        self.neo4j_driver = None
        if neo4j_uri and neo4j_user and neo4j_password and NEO4J_AVAILABLE:
            try:
                self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
                self.logger.info("Connected to Neo4j database")
            except Exception as e:
                self.logger.error(f"Failed to connect to Neo4j: {e}")

        # Data storage as dictionaries
        self.data = {}

    
    def load_csv_data(self, csv_key, file_path):
        """
        Load data from a single CSV file and store it in the data dictionary.
        Handles multiple encoding types automatically.

        Args:
            csv_key (str): Logical name of the data (e.g. 'company_industry_mapping')
            file_path (str): Path to the CSV file
        """
        self.logger.info(f"Loading CSV file for '{csv_key}' from {file_path}...")

        # Try multiple encodings in order of likelihood
        encodings = ['utf-8', 'latin-1', 'windows-1252', 'iso-8859-1', 'cp1252']
        
        df = None
        successful_encoding = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                successful_encoding = encoding
                self.logger.info(f"Successfully loaded '{csv_key}' using {encoding} encoding")
                break
            except PermissionError as e:
                # When the OS blocks access to the file (e.g., locked or protected)
                logging.error(f"Permission denied while accessing '{file_path}': {e}")
                return {
                    "status": "error",
                    "error": f"Permission denied while accessing file '{file_path}'",
                    "http_status": 500  # backend error
                }
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                self.logger.warning(f"File not found: {file_path}. Skipping '{csv_key}'.")
                return
            except pd.errors.EmptyDataError:
                self.logger.warning(f"File is empty: {file_path}. Skipping '{csv_key}'.")
                return
            except Exception as e:
                if encoding == encodings[-1]:  # Last encoding attempt
                    self.logger.error(f"Failed to load '{csv_key}' from {file_path}: {e}")
                    return
                continue
        
        if df is None:
            self.logger.error(f"Could not decode '{csv_key}' with any known encoding")
            return
        
        try:
            df = self.clean_dataframe(df)
            self.data[csv_key] = df.to_dict('records')
            self.logger.info(f"Loaded {len(self.data[csv_key])} records for '{csv_key}'")
        except Exception as e:
            self.logger.error(f"Failed to process '{csv_key}': {e}")



    def clean_dataframe(self, df):
        """Clean dataframe column names and handle common issues"""
        # Clean column names
        df.columns = df.columns.str.strip()
        # Replace NaN with None for better JSON serialization
        df = df.where(pd.notnull(df), None)

        return df
    


    def build_graph_from_dicts(self):
        """Build the graph database from dictionary data"""
        self.logger.info("Building graph from dictionary data...")

        # Create nodes and collect all unique entities
        companies = {}             # KEYS = company_id
        industries = {}            # KEYS = industry_id 
        sectors = {}               # KEYS = sector_id
  

        # ------------------------------Create Company nodes ------------------------------
        self.logger.info("Creating Company nodes...")

        # From company-industry mapping (CSV-1)
        if 'company_industry_mapping' in self.data:
            for record in self.data['company_industry_mapping']:
                self.validate_record_fields(record, ['companyId','ticker','companyName'], 'company_industry_mapping')
                company_id = record.get('companyId')
                if self.is_valid_id(company_id):
                    companies[company_id] = {
                        'companyId': company_id,
                        'ticker': record.get('ticker'),
                        'companyName': record.get('companyName'),
                        'label': 'Company'
                    }


        # Enrich companies with detailed data (CSV-5)
        if 'company_details' in self.data:
            for record in self.data['company_details']:
                company_id = record.get('companyId')
                if self.is_valid_id(company_id):
                    if company_id not in companies:
                        companies[company_id] = {'companyId': company_id, 'label': 'Company'}

                    # Update with all company details
                    founded_val = record.get('founded')
                    companies[company_id].update({
                        'ticker': record.get('ticker'),
                        'companyName': record.get('companyName'),
                        'website': record.get('website'),
                        'founded': int(founded_val) if founded_val is not None and not (isinstance(founded_val, float) and np.isnan(founded_val)) else None,
                        'country': record.get('country'),
                        'state': record.get('state'),
                        'marketCapGroup': record.get('marketCapGroup'),
                        'ipoDate': record.get('ipoDate'),
                        'exchange': record.get('exchange'),
                        'isSPAC': record.get('isSPAC'),
                        'fyEnd': record.get('fyEnd'),
                        'sicCode': str(record.get('sicCode')) if record.get('sicCode') is not None else None,
                        'cusipNumber': record.get('cusipNumber'),
                        'cikCode': str(record.get('cikCode')) if record.get('cikCode') is not None else None,
                        'isinNumber': record.get('isinNumber')
                    })


        # Add companies from competitors data (CSV-2)
        if 'company_competitors' in self.data:
            for record in self.data['company_competitors']:
                # Add main company
                company_id = record.get('companyId')
                if self.is_valid_id(company_id) and company_id not in companies:
                    companies[company_id] = {
                        'companyId': company_id,
                        'companyName': record.get('companyName'),
                        'label': 'Company'
                    }

                # Add competitor company
                competitor_id = record.get('competitorId')
                if self.is_valid_id(competitor_id) and competitor_id not in companies:
                    companies[competitor_id] = {
                        'companyId': competitor_id,
                        'companyName': record.get('competitorName'),
                        'label': 'Company'
                    }

        #---------------------------------------- Create Industry nodes-------------------------------------------
        self.logger.info("Creating Industry nodes...")

        # From company-industry mapping (CSV-1)
        if 'company_industry_mapping' in self.data:
            for record in self.data['company_industry_mapping']:
                industry_id = record.get('industryId')
                if self.is_valid_id(industry_id):
                    industries[industry_id] = {
                        'industryId': industry_id,
                        'industryName': record.get('industryName'),
                        'label': 'Industry'
                    }

        # From industry-sector mapping (CSV-3)
        if 'industry_sector_mapping' in self.data:
            for record in self.data['industry_sector_mapping']:
                industry_id = record.get('industryId')
                if self.is_valid_id(industry_id):
                    if industry_id not in industries:
                        industries[industry_id] = {'industryId': industry_id, 'label': 'Industry'}
                    industries[industry_id].update({
                        'industryName': record.get('industryName')
                    })

        # Enrich with industry statistics (CSV-6)
        if 'industry_statistics' in self.data:
            for record in self.data['industry_statistics']:
                industry_id = record.get('industryId')
                if self.is_valid_id(industry_id):
                    if industry_id not in industries:
                        industries[industry_id] = {'industryId': industry_id, 'label': 'Industry'}
                    industries[industry_id].update({
                        'industryName': record.get('industryName'),
                        'countOfCompanies': record.get('countOfCompanies')
                    })


        #----------------------------------------------- Create Sector nodes-------------------------------------------
        self.logger.info("Creating Sector nodes...")

        # From industry-sector mapping (CSV-3)
        if 'industry_sector_mapping' in self.data:
            for record in self.data['industry_sector_mapping']:
                sector_id = record.get('sectorId')
                if self.is_valid_id(sector_id):
                    sectors[sector_id] = {
                        'sectorId': sector_id,
                        'sectorName': record.get('sectorName'),
                        'label': 'Sector'
                    }
        # Enrich with sector statistics (CSV-8)
        if 'sector_statistics' in self.data:
            for record in self.data['sector_statistics']:
                sector_id = record.get('sectorId')
                if self.is_valid_id(sector_id):
                    if sector_id not in sectors:
                        sectors[sector_id] = {'sectorId': sector_id, 'label': 'Sector'}
                    sectors[sector_id].update({
                        'sectorName': record.get('sectorName'),
                        'countOfIndustries': record.get('countOfIndustries')
                    })
        
        # Store processed data for export
        self.processed_data = {
            'companies': companies,
            'industries': industries,
            'sectors': sectors,
        }


    def sync_to_neo4j(self):
        """Sync all data to Neo4j using optimized batch operations (incremental, no reset)."""
        try:
            if not self.neo4j_driver:
                raise ConnectionError("Neo4j driver not initialized or unavailable")

            self.logger.info("Syncing data to Neo4j (incremental update, no reset)...")

            self.create_neo4j_nodes_batch()
            self.create_neo4j_relationships_batch()

            self.logger.info("Neo4j sync completed successfully!")

        except (ConnectionError, ServiceUnavailable, AuthError) as conn_err:
            self.logger.error(f"Neo4j connection error: {conn_err}")
            raise HTTPException(status_code=500, detail=f"Database connection failed: {conn_err}")

        except Exception as e:
            self.logger.error(f"Unexpected backend error during Neo4j sync: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")




    def create_neo4j_nodes_batch(self):
        """Create nodes in Neo4j database using batch operations"""
        if not self.neo4j_driver:
            self.logger.warning("Neo4j driver not available")
            return

        with self.neo4j_driver.session() as session:

            # ---------------  Batch create Company nodes ------------------------
            self.logger.info("Creating Company nodes in Neo4j (batch)...")
            company_batch = []
            for company_id, company_data in self.processed_data['companies'].items():
                if self.is_valid_id(company_id):
                    cleaned_properties = self.clean_properties_for_neo4j(company_data)
                    company_batch.append({'companyId': company_id,'properties': cleaned_properties})

            if company_batch:
                query = """
                UNWIND $batch AS item
                MERGE (c:Company {companyId: item.companyId})
                SET c += item.properties
                """
                session.run(query, batch=company_batch)



            # ---------------------  Batch create Industry nodes -------------------
            self.logger.info("Creating Industry nodes in Neo4j (batch)...")
            industry_batch = []
            for industry_id, industry_data in self.processed_data['industries'].items():
                if self.is_valid_id(industry_id):
                    cleaned_properties = self.clean_properties_for_neo4j(industry_data)
                    industry_batch.append({
                        'industryId': industry_id,
                        'properties': cleaned_properties
                    })

            if industry_batch:
                query = """
                UNWIND $batch AS item
                MERGE (i:Industry {industryId: item.industryId})
                SET i += item.properties
                """
                session.run(query, batch=industry_batch)



            # ---------------- Batch create Sector nodes ------------------
            self.logger.info("Creating Sector nodes in Neo4j (batch)...")
            sector_batch = []
            for sector_id, sector_data in self.processed_data['sectors'].items():
                if self.is_valid_id(sector_id):
                    cleaned_properties = self.clean_properties_for_neo4j(sector_data)
                    sector_batch.append({
                        'sectorId': sector_id,
                        'properties': cleaned_properties
                    })

            if sector_batch:
                query = """
                UNWIND $batch AS item
                MERGE (s:Sector {sectorId: item.sectorId})
                SET s += item.properties
                """
                session.run(query, batch=sector_batch)


            


    def is_valid_id(self, value):
        """Check if a value is a valid ID (not None, NaN, or empty string)"""
        if value is None:
            return False
        if pd.isna(value):
            return False
        if isinstance(value, str) and value.strip() == '':
            return False
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return False
        return True



    def clean_properties_for_neo4j(self, properties):
        cleaned = {}
        for key, value in properties.items():
            if value is None:
                continue
            if isinstance(value, dict):
                cleaned[key] = json.dumps(value, ensure_ascii=False)
            elif not (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
                if isinstance(value, np.integer):
                    cleaned[key] = int(value)
                elif isinstance(value, np.floating):
                    cleaned[key] = float(value)
                elif isinstance(value, np.bool_):
                    cleaned[key] = bool(value)
                else:
                    cleaned[key] = value
        return cleaned

        
    def validate_record_fields(self, record, required_fields, source_name):
        """Validate that a record has required fields"""
        for field in required_fields:
            if field not in record:
                self.logger.warning(f"Missing field '{field}' in {source_name} record")

    
    def create_neo4j_relationships_batch(self):
        """Create relationships in Neo4j database using batch operations"""
        if not self.neo4j_driver:
            self.logger.warning("Neo4j driver not available")
            return

        with self.neo4j_driver.session() as session:
            
            # Create indexes for better performance
            self.logger.info("Creating indexes for better performance...")
            try:
                session.run("CREATE INDEX company_id_index IF NOT EXISTS FOR (c:Company) ON (c.companyId)")
                session.run("CREATE INDEX industry_id_index IF NOT EXISTS FOR (i:Industry) ON (i.industryId)")
                session.run("CREATE INDEX sector_id_index IF NOT EXISTS FOR (s:Sector) ON (s.sectorId)")

            except Exception as e:
                self.logger.warning(f"Failed to create indexes: {e}")
                # Older Neo4j versions
                session.run("CREATE INDEX ON :Company(companyId)")
                session.run("CREATE INDEX ON :Industry(industryId)")
                session.run("CREATE INDEX ON :Sector(sectorId)")



            # Batch create Company BELONG_TO Industry relationships
            self.logger.info("Creating Company BELONG_TO Industry relationships (batch)...")
            if 'company_industry_mapping' in self.data:
                batch = []
                for record in self.data['company_industry_mapping']:
                    company_id = record.get('companyId')
                    industry_id = record.get('industryId')
                    if self.is_valid_id(company_id) and self.is_valid_id(industry_id):
                        batch.append({'companyId': company_id,'industryId': industry_id})

                if batch:
                    query = """
                    UNWIND $batch AS item
                    MATCH (c:Company {companyId: item.companyId})
                    MATCH (i:Industry {industryId: item.industryId})
                    MERGE (c)-[:BELONG_TO]->(i)
                    """
                    session.run(query, batch=batch)



            # Optimized batch create Company COMPETE_WITH Company relationships
            self.logger.info("Creating Company COMPETE_WITH Company relationships (optimized batch)...")
            if 'company_competitors' in self.data:
                # Collect all unique competitor pairs
                competitor_pairs = set()
                for record in self.data['company_competitors']:
                    company_id = record.get('companyId')
                    competitor_id = record.get('competitorId')
                    if self.is_valid_id(company_id) and self.is_valid_id(competitor_id):
                        # Add both directions as a sorted tuple to avoid duplicates
                        pair = tuple(sorted([company_id, competitor_id]))
                        competitor_pairs.add(pair)

                # Convert to batch format
                batch = [{'company1': pair[0], 'company2': pair[1]} for pair in competitor_pairs]
                if batch:
                    # Process in chunks to avoid memory issues
                    chunk_size = 500
                    total_pairs = len(batch)
                    for i in range(0, total_pairs, chunk_size):
                        chunk = batch[i:i+chunk_size]
                        # Create bidirectional relationships in one query
                        query = """
                        UNWIND $batch AS item
                        MATCH (c1:Company {companyId: item.company1})
                        MATCH (c2:Company {companyId: item.company2})
                        MERGE (c1)-[:COMPETE_WITH]-(c2)
                        """
                        session.run(query, batch=chunk)
                        self.logger.info(f"Created competitor relationships {i} to {min(i+chunk_size, total_pairs)} of {total_pairs}")



            # Batch create Industry BELONG_TO Sector relationships
            self.logger.info("Creating Industry BELONG_TO Sector relationships (batch)...")
            if 'industry_sector_mapping' in self.data:
                batch = []
                for record in self.data['industry_sector_mapping']:
                    industry_id = record.get('industryId')
                    sector_id = record.get('sectorId')

                    if self.is_valid_id(industry_id) and self.is_valid_id(sector_id):
                        batch.append({
                            'industryId': industry_id,
                            'sectorId': sector_id
                        })

                if batch:
                    query = """
                    UNWIND $batch AS item
                    MATCH (i:Industry {industryId: item.industryId})
                    MATCH (s:Sector {sectorId: item.sectorId})
                    MERGE (i)-[:BELONG_TO]->(s)
                    """
                    session.run(query, batch=batch)
    



    def close(self):
        """Close database connections"""
        if self.neo4j_driver:
            self.neo4j_driver.close()

def read_csv_safely(file_path):
    encodings_to_try = ["utf-8", "utf-8-sig", "latin1", "windows-1252"]
    
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode CSV file with common encodings.")



def process_structured_csv_files(files: List[UploadFile], keys: List[str]):
    overall_response = {
        "status": "success",
        "message": {"success_files": [], "error_files": []},
        "error": None,
        "http_status": 200
    }

    # ✅ Validate user input first
    if len(files) != len(keys):
        overall_response["status"] = "error"
        overall_response["error"] = "Number of files and keys do not match"
        overall_response["http_status"] = 400
        return overall_response

    for idx, file in enumerate(files):
        result = None
        safe_filename = file.filename.replace(" ", "_")
        if not safe_filename.lower().endswith(".csv"):
            overall_response["message"]["error_files"].append({"file_name": safe_filename, "msg": "Invalid file type"})
            overall_response["status"] = "warning"
            overall_response["http_status"] = 400
            continue

        try:
            # NOTE: This is a sync function. We read from the underlying file object.
            # FastAPI will run sync endpoints in a threadpool, so blocking I/O here is OK.
            try:
                file.file.seek(0)
            except Exception:
                pass
            content = file.file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(content)
                temp_path = tmp.name

            result = store_structured_company_industry_sector_data(temp_path, keys[idx], original_filename=safe_filename)
            os.remove(temp_path)

            if result["status"] == "success":
                overall_response["message"]["success_files"].extend(result["message"]["success_files"])
            else:
                overall_response["message"]["error_files"].extend(result["message"]["error_files"])
                overall_response["status"] = result["status"]
                overall_response["error"] = result["error"]
                overall_response["http_status"] = 400  # treat as backend error

        except Exception as e:
            logging.error(f"Traceback:\n{traceback.format_exc()}")
            overall_response["status"] = "error"
            overall_response["message"]["error_files"].append({"file_name": safe_filename, "msg": str(e)})
            overall_response["error"] = str(e)
            if isinstance(result, dict) and result.get("http_status", 500) == 500:
                overall_response["http_status"] = 500
            else:
                overall_response["http_status"] = 400

    return overall_response




def store_structured_company_industry_sector_data(file_path, csv_key=None, original_filename=None):

    """Process a single structured CSV file and sync to Neo4j, returning structured status JSON."""
    response = {
        "status": "success",
        "message": {
            "success_files": [],
            "error_files": []
        },
        "error": None
    }

    try:
        builder = GraphDatabaseBuilder(
            neo4j_uri=config.NEO4J_URI,
            neo4j_user=config.NEO4J_USERNAME,
            neo4j_password=config.NEO4J_PASSWORD
        )
    except Exception as e:
        msg = f"Internal Server Error: Failed to initialize Neo4j builder: {e}"
        response["status"] = "error"
        response["error"] = str(e)
        response["message"]["error_files"].append({"file_name": os.path.basename(file_path), "msg": msg})
        response["http_status"] = 500 
        return response  # early return with 500-style info

    try:
        short_key_to_logical = {
            'ci': 'company_industry_mapping',
            'cc': 'company_competitors',
            'is': 'industry_sector_mapping',
            'c': 'company_details',
            'i': 'industry_statistics',
            's': 'sector_statistics'
        }

        required_columns_map = {
            'company_industry_mapping': required_columns_ci,
            'company_competitors': required_columns_cc,
            'industry_sector_mapping': required_columns_is,
            'company_details': required_columns_c,
            'industry_statistics': required_columns_i,
            'sector_statistics': required_columns_s
        }

        filename = original_filename or os.path.basename(file_path)
        key = short_key_to_logical.get(csv_key)
        if not key:
            msg = f"Unknown structured file key: {csv_key} for file: {filename}"
            response["status"] = "error"
            response["message"]["error_files"].append({"file_name": filename, "msg": msg})
            response["error"] = msg
            return response

        # ✅ Validate columns
        df_sample = read_csv_safely(file_path)
        actual_cols = [c.strip() for c in df_sample.columns]
        required_cols = required_columns_map.get(key, [])
        missing = [c for c in required_cols if c not in actual_cols]

        if missing:
            msg = f"Missing required columns: {missing}"
            response["status"] = "warning"
            response["message"]["error_files"].append({"file_name": filename, "msg": msg})
            response["error"] = msg
            return response

        # ✅ Sync to Neo4j
        builder.load_csv_data(key, file_path)
        builder.build_graph_from_dicts()
        builder.sync_to_neo4j()
        response["message"]["success_files"].append({"file_name": filename, "msg": f"Successfully processed file: {filename}"})

    except Exception as e:
        msg = f"Error processing file {file_path}: {e}"
        response["status"] = "error"
        response["message"]["error_files"].append({"file_name": os.path.basename(file_path), "msg": msg})
        response["error"] = str(e)

    finally:
        builder.close()

    return response




"""

#######################################################################################################
######################### company_industry_sector_data ################################################
#######################################################################################################


1 - -------------------------------------- company_industry_mapping. -------------------------
| companyId | ticker | companyName               | industryId | industryName                  |
|-----------|--------|---------------------------|------------|--------------------------------|
| 1         | AAPL   | Apple Inc.                | 33         | Consumer Electronics          |
| 2         | MSFT   | Microsoft Corporation     | 129        | Software - Infrastructure     |
| 3         | NVDA   | NVIDIA Corporation        | 125        | Semiconductors                |
| 4         | AMZN   | Amazon.com, Inc.          | 75         | Internet Retail               |
| 5         | GOOG   | Alphabet Inc.             | 74         | Internet Content & Information |
| 6         | GOOGL  | Alphabet Inc.             | 74         | Internet Content & Information |


2 ---------------------------- IndustryBELONG_TOSector --------------------------------------
| companyId | ticker | companyName             | industryId | industryName                   |
|-----------|--------|-------------------------|------------|--------------------------------|
| 1         | AAPL   | Apple Inc.              | 33         | Consumer Electronics           |
| 2         | MSFT   | Microsoft Corporation   | 129        | Software - Infrastructure      |
| 3         | NVDA   | NVIDIA Corporation      | 125        | Semiconductors                 |
| 4         | AMZN   | Amazon.com, Inc.        | 75         | Internet Retail                |
| 5         | GOOG   | Alphabet Inc.           | 74         | Internet Content & Information |
| 6         | GOOGL  | Alphabet Inc.           | 74         | Internet Content & Information |



3-----------------------------------  CompanyCOMPETES_WITHCompany -------------------------------
| companyId | companyName          | competitorId | competitorName                                  |
|-----------|----------------------|--------------|------------------------------------------------|
| 643       | Omnicom Group Inc.   | 858          | The Interpublic Group of Companies, Inc.       |
| 643       | Omnicom Group Inc.   | 945          | WPP plc                                        |
| 643       | Omnicom Group Inc.   | 1950         | Criteo S.A.                                    |
| 643       | Omnicom Group Inc.   | 2045         | Ziff Davis, Inc.                               |
| 643       | Omnicom Group Inc.   | 2057         | Stagwell Inc.                                  |
| 643       | Omnicom Group Inc.   | 2120         | Magnite, Inc.                                  |
| 643       | Omnicom Group Inc.   | 2138         | LZ Technology Holdings Limited                 |



4- -----------------------------------------------------------   NodesCompany ------------------------------------
| companyId | ticker | companyName             | website                                         | founded | country       | state       | marketCapGroup | ipoDate   | exchange | isSPAC | fyEnd     | sicCode | cusipNumber | cikCode | isinNumber     |
|-----------|--------|-------------------------|-------------------------------------------------|---------|--------------|-------------|----------------|-----------|----------|--------|-----------|---------|-------------|---------|----------------|
| 1         | AAPL   | Apple Inc.              | https://www.apple.com                           | 1977    | United States | California  | Mega-Cap       | 12/12/80  | NASDAQ   | No     | September | 3571    | 37833100    | 320193  | US0378331005   |
| 2         | MSFT   | Microsoft Corporation   | https://www.microsoft.com                       | 1975    | United States | Washington  | Mega-Cap       | 3/13/86   | NASDAQ   | No     | June      | 7372    | 594918104   | 789019  | US5949181045   |
| 3         | NVDA   | NVIDIA Corporation      | https://www.nvidia.com                          | 1993    | United States | California  | Mega-Cap       | 1/22/99   | NASDAQ   | No     | January   | 3674    | 67066G104   | 1045810 | US67066G1040   |
| 4         | AMZN   | Amazon.com, Inc.        | https://www.amazon.com                          | 1994    | United States | Washington  | Mega-Cap       | 5/15/97   | NASDAQ   | No     | December  | 5961    | 23135106    | 1018724 | US0231351067   |
| 5         | GOOG   | Alphabet Inc.           | https://abc.xyz                                 | 1998    | United States | California  | Mega-Cap       | 8/19/04   | NASDAQ   | No     | December  | 7370    | 02079K107   | 1652044 | US02079K1079   |
| 6         | GOOGL  | Alphabet Inc.           | https://www.abc.xyz                             | 1998    | United States | California  | Mega-Cap       | 8/19/04   | NASDAQ   | No     | December  | 7370    | 02079K305   | 1652044 | US02079K3059   |
| 7         | META   | Meta Platforms, Inc.    | https://investor.fb.com/home/default.aspx       | 2004    | United States | California  | Mega-Cap       | 5/18/12   | NASDAQ   | No     | December  | 7370    | 30303M102   | 1326801 | US30303M1027   |


5- ------------------- NodesIndustry. --------------------
| industryId | industryName                 | countOfCompanies |
|------------|------------------------------|------------------|
| 1          | Advertising Agencies         | 41               |
| 2          | Aerospace & Defense          | 73               |
| 3          | Agricultural Inputs          | 15               |
| 4          | Airlines                     | 19               |
| 5          | Airports & Air Services      | 9                |
| 6          | Aluminum                     | 4                |
| 7          | Apparel Manufacturing        | 26               |



6 ------------------ NodesSector ---------------
| sectorId | sectorName                                | countOfIndustries |
|----------|-------------------------------------------|-------------------|
| 1        | Communication Services                    | 7                 |
| 2        | Consumer Discretionary                    | 23                |
| 3        | Consumer Staples                          | 12                |
| 4        | Energy                                    | 8                 |
| 5        | Real Estate Investment Trusts (REITs)     | 1                 |
| 6        | Financials                                | 18                |
| 7        | Healthcare                                | 11                |
| 8        | Industrials                               | 25                |


7- -----------------  NodesMetric -----------------
| metricId | metricName                 | metricBelongTo | metricBelongToCompanyId | for1Y2006 | for1Y2007 | for1Y2008 |
|----------|-----------------------------|----------------|--------------------------|-----------|-----------|-----------|
| 1        | Revenue                     | CAT            | 78                       |           |           |           |
| 2        | CostOfGoodsAndServices      | CAT            | 78                       |           |           |           |
| 3        | SellingGeneralAdministrative| CAT            | 78                       |           |           |           |
| 4        | ResearchAndDevelopment      | CAT            | 78                       |           |           |           |
| 5        | OperatingMargin             | CAT            | 78                       |           |           |           |
| 6        | Interest                    | CAT            | 78                       |           |           |           |
| 7        | Taxes                       | CAT            | 78                       |           |           |           |
| 8        | NetIncome                   | CAT            | 78                       |           |           |           |


8 ----------------  MetricDRIVEN_BYMetric. -------------------------
| Metric          | DEPENDS_ON                  | Equation   |
|-----------------|-----------------------------|------------|
| OperatingMargin | Revenue                     | Add        |
| OperatingMargin | CostOfGoodsAndServices      | Substract  |
| OperatingMargin | SellingGeneralAdministrative| Substract  |
| OperatingMargin | ResearchAndDevelopment      | Substract  |
| NetIncome       | OperatingMargin             | Add        |
| NetIncome       | Interest                    | Substract  |
| NetIncome       | Taxes                       | Substract  |



##############################################################################################################################
######################################## Metrics Data for perticuilar ticker #################################################
##############################################################################################################################


1- matric_data(WMT_MasterFinancials.csv) for ticker -WMT :
# | Metric                             | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011       | 2012       | 2013       | 2014       | 2015       | 2016       | 2017       | 2018       | 2019       | 2020        | 2021        | 2022        | 2023        | 2024        | 2025        | 2026        | 2027        | 2028        | 2029        | 2030        | 2031        | 2032        | 2033        | 2034        | 2035        | Last1Y_AVG   | Last2Y_AVG   | Last3Y_AVG   | Last4Y_AVG   | Last5Y_AVG   | Last10Y_AVG  | Last15Y_AVG  | Last1Y_CAGR  | Last2Y_CAGR  | Last3Y_CAGR  | Last4Y_CAGR  | Last5Y_CAGR  | Last10Y_CAGR | Last15Y_CAGR | TableName        |
# |------------------------------------|------|------|------|------|------|------|------------|------------|------------|------------|------------|------------|------------|------------|------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|--------------|--------------|--------------|--------------|--------------|---------------|---------------|---------------|---------------|---------------|---------------|---------------|---------------|---------------|------------------|
# | RevenueGrowthRate                  |      |      |      |      |      |      |            |            |            |            |            |            |            |            |            | 1.409665    | 16.97642    | 8.018688    | 15.88657    | 3.383476    | 10.47542    | 10.02815    | 9.580879    | 9.13361     | 8.686342    | 8.239074    | 7.791805    | 7.344537    | 6.897268    | 6.45        | 6.002732    | 3.383476     | 9.635024     | 9.096246     | 11.06629     | 9.134965     | 9.134965     | 9.134965     | -0.787023    | -0.350424    | -0.415875    | 0.244692     |             |             |             | IncomeStatement  |
# | Revenue                            |      |      |      |      |      |      |            |            |            |            |            |            |            |            |            | 1.2350537E+10 | 1.2754589E+10 | 1.3007347E+10 | 1.3190707E+10 | 1.5430017E+10 | 1.6667302E+10 | 1.9315165E+10 | 1.9968689E+10 | 2.2060492E+10 | 2.4272751E+10 | 2.6598294E+10 | 2.9027678E+10 | 3.1549122E+10 | 3.4148477E+10 | 3.680926E+10 | 3.9512729E+10 | 4.223803E+10  | 4.4962381E+10  | 4.7661352E+10  | 1.9968689E+10  | 1.9641927E+10  | 1.8650385E+10  | 1.7845293E+10  | 1.6914376E+10  | 1.5335544E+10  | 1.5335544E+10  | 0.033835      | 0.094566      | 0.089752      | 0.109227      | 0.089512      |               | IncomeStatement  |
# | CostOfRevenue                      |      |      |      |      |      |      |            |            |            |            |            |            |            |            |            | 1.0223017E+10 | 1.0513492E+10 | 1.0646452E+10 | 1.0763926E+10 | 1.2451061E+10 | 1.3588612E+10 | 1.5883677E+10 | 1.6326129E+10 | 1.7991169E+10 | 1.979535E+10 | 2.1691919E+10 | 2.3673174E+10 | 2.5729507E+10 | 2.784938E+10 | 3.001935E+10 | 3.2224132E+10 | 3.444672E+10 | 3.666853E+10 | 3.8869643E+10 | 1.6326129E+10 | 1.6104903E+10 | 1.526614E+10 | 1.456237E+10 | 1.380268E+10 | 1.254955E+10 | 1.254955E+10 | 0.027856      | 0.09611       | 0.094525      | 0.109758      | 0.08927       |               | IncomeStatement  |
# | GrossMargin                        | 0    | 0    | 0    | 0    | 0    | 0    | 0          | 0          | 0          | 0          | 0          | 0          | 2.12752E+09 | 2.241097E+09 | 2.360895E+09 | 2.426781E+09  | 2.978956E+09  | 3.07869E+09   | 3.431488E+09  | 3.64256E+09  | 4.069322E+09  | 4.4774E+09   | 4.906375E+09  | 5.354504E+09  | 5.819614E+09  | 6.299097E+09  | 6.78991E+09   | 7.288597E+09  | 7.791311E+09  | 8.293851E+09  | 8.791709E+09  | 3.64256E+09   | 3.537024E+09   | 3.384246E+09   | 3.282924E+09   | 3.111695E+09   | 2.228799E+09   | 1.485866E+09   | 0.06151       | 0.087728      | 0.069336      | 0.106863      | 0.090601      |               | IncomeStatement  |
# | SellingGeneralAndAdministration    |      |      |      |      |      |      | 7.87382E+08 | 8.6083E+08  | 9.33836E+08 |            |            |            |            | 1.908752E+09 | 2.017821E+09 | 2.051324E+09  | 1.90383E+09   | 2.156655E+09  | 2.254765E+09  | 2.448769E+09  | 2.567013E+09  | 2.925124E+09  | 3.21846E+09   | 3.526816E+09  | 3.848942E+09  | 4.183274E+09  | 4.527937E+09  | 4.880745E+09  | 5.239214E+09  | 5.600576E+09  | 5.961813E+09  | 6.319685E+09  | 2.567013E+09  | 2.507891E+09  | 2.423516E+09  | 2.356801E+09  | 2.266206E+09  | 2.163616E+09  | 1.910359E+09  | 0.048287      | 0.066997      | 0.05978       | 0.077581      | 0.045873      |               | 0.081972         | IncomeStatement  |
# | Depreciation                       |      |      |      |      |      |      |            |            |            |            |            |            |            |            |            | 1.556E+08    | 1.701E+08    | 1.917E+08    | 2.198E+08    | 2.555E+08    | 3.44776E+08  | 3.64924E+08  | 3.90243E+08  | 4.20093E+08  | 4.53935E+08  | 4.91295E+08  | 5.31742E+08  | 5.74868E+08  | 6.20271E+08  | 6.6755E+08   | 7.16291E+08  | 2.555E+08    | 2.3765E+08    | 2.22333E+08    | 2.09275E+08    | 1.9854E+08    | 1.9854E+08    | 1.9854E+08    | 0.16242       | 0.154475      | 0.145237      | 0.131997      |               |               | IncomeStatement  |
# | OperatingIncome                    |      |      |      |      |      |      | 2.25504E+08 | 2.27639E+08 | 2.0813E+08  |            |            |            |            | 2.16019E+08 | 2.20272E+08 | 3.03453E+08  | 3.52199E+08  | 6.42392E+08  | 6.17323E+08  | 7.37986E+08  | 8.00419E+08  | 7.99423E+08  | 8.94017E+08  | 9.89316E+08  | 1.08547E+09  | 1.1824E+09   | 1.27986E+09  | 1.37742E+09  | 1.47452E+09  | 1.57046E+09  | 1.66449E+09  | 1.75573E+09  | 8.00419E+08  | 7.69203E+08   | 7.18576E+08   | 6.9953E+08    | 6.30064E+08    | 4.86258E+08    | 4.32583E+08    | 0.084599      | 0.138682      | 0.076066      | 0.227813      | 0.214074      |               | 0.088122         | IncomeStatement  |
# | InterestExpense                    |      |      |      |      |      |      |            |            |            |            |            |            | 1.43351E+08 | 1.96724E+08 | 1.64535E+08 | 1.0823E+08   | 8.4385E+07   | 5.9444E+07   | 4.7462E+07   | 6.4527E+07   | 5.22257E+07  |             |             |             |             |             |             |             |             |             |             |             | 6.4527E+07   | 5.59945E+07   | 5.71443E+07   | 6.39545E+07   |


* which year  onwards have the predicted data started? 2025 onwards



2- Multiples (WMT_MultiplesTable.csv) for ticker -WMT :
# | Name                                   | Type         | Value         |
# |----------------------------------------|--------------|----------------|
# | EnterpriseValue_Fundamental            | Numerator    | 4.17013E+11    |
# | MarketCap_Fundamental                  | Numerator    | 3.52745E+11    |
# | EnterpriseValue_Current                | Numerator    | Call_API       |
# | MarketCap_Current                      | Numerator    | Call_API       |
# | GrossMargin_Last1Y_AVG                 | Denominator  | 1.57983E+11    |
# | OperatingIncome_Last1Y_AVG             | Denominator  | 27012000000    |
# | PretaxIncome_Last1Y_AVG                | Denominator  | 21848000000    |
# | NetIncome_Last1Y_AVG                   | Denominator  | 15511000000    |
# | Revenue_Last1Y_AVG                     | Denominator  | 6.48125E+11    |
# | EBITAAdjusted_Last1Y_AVG               | Denominator  | 28175541488    |
# | EBITDAAdjusted_Last1Y_AVG              | Denominator  | 41148541488    |
# | NetOperatingProfitAfterTaxes_Last1Y_AVG| Denominator  | 22597541488    |
# | GrossMargin_Last2Y_AVG                 | Denominator  | 1.52776E+11    |
# | OperatingIncome_Last2Y_AVG             | Denominator  | 23720000000    |
# | PretaxIncome_Last2Y_AVG                | Denominator  | 19432000000    |
# | NetIncome_Last2Y_AVG                   | Denominator  | 13595500000    |





3 - ValuationSummary (WMT_ValuationSummary.csv) for ticker -WMT :
# | Name                               | Value             |
# |------------------------------------|--------------------|
# | NOPATGrowthRateInPerpetuity        | 0.04               |
# | ReturnOnNewInvestedCapital         | 0.35               |
# | WeightedAverageCostofCapital       | 0.08               |
# | PresentValueOf2025FCF              | 40867291135        |
# | PresentValueOf2026FCF              | 44294040111        |
# | PresentValueOf2027FCF              | 43752110131        |
# | PresentValueOf2028FCF              | 43170877587        |
# | PresentValueOf2029FCF              | 42563691407        |
# | PresentValueOf2030FCF              | 41941208750        |
# | PresentValueOf2031FCF              | 41311902615        |
# | PresentValueOf2032FCF              | 40682475470        |
# | PresentValueOf2033FCF              | 40058196224        |
# | PresentValueOf2034FCF              | 39443174663        |
# | PresentValueOfOperations           | 4.18085E+11        |
# | ExcessCash                         | -3095500000        |
# | ForeignTaxCreditCarryForward       | 2024000000         |
# | EnterpriseValue                    | 4.17013E+11        |
# | Debt                               | -39579000000       |
# | OperatingLeaseLiabilities          | -12943000000       |
# | VariableLeaseLiabilities           | -5237335748        |
# | FinanceLeaseLiabilities            | -6509000000        |
# | EquityValue                        | 3.52745E+11        |








# ------  Nodes. -----------
1. COMPANY NODES (Label: "Company"):
   - companyId, ticker, companyName, website, founded, country, state, marketCapGroup, ipoDate, exchange, isSPAC, fyEnd, sicCode, cusipNumber, cikCode, isinNumber
2. INDUSTRY NODES (Label: "Industry"):
   - industryId, industryName, countOfCompanies
3. SECTOR NODES (Label: "Sector"):
   - sectorId, sectorName, countOfIndustries
3. METRIC NODES (Label: "Metric"):
   - ticker, metricName , financial_data_json , statementType
3. TENKCHUNK NODES (Label: "TenKChunk"):
   - ticker, year , ....(Revenue)

# ---------Relationships -----------
1. (Company)-[:BELONG_TO]->(Industry)
2. (Industry)-[:BELONG_TO]->(Sector)  
3. (Company)-[:HAS_METRIC]->(Metric)
4. (Company)-[:COMPETE_WITH]-(Company)
5. (Company)-[:HAS_TENK_DATA]-(TenKChunk)


"""
