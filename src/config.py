import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

class Config:
    BASE_DIR = Path(__file__).resolve().parent

    # --------------------- Model / API Keys -----------------------------
    # OpenAI
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')


    REPORT_GENERATION_OPENAI_MODEL = os.environ.get('REPORT_GENERATION_OPENAI_MODEL', 'gpt-4.1')
    REPORT_GENERATION_GOOGLE_MODEL = os.environ.get('REPORT_GENERATION_GOOGLE_MODEL', 'gemini-1.0-ultra')


    # LLM Settings
    CHAT_MODEL_TYPE = os.environ.get('CHAT_MODEL_TYPE', 'OPENAI')
    CHAT_MODEL_NAME = os.environ.get('CHAT_MODEL_NAME', 'gpt-4o')
    EMBEDDINGS_MODEL_TYPE = os.environ.get('EMBEDDINGS_MODEL_TYPE', 'OPENAI')
    EMBEDDINGS_MODEL_NAME = os.environ.get('EMBEDDINGS_MODEL_NAME', 'text-embedding-ada-002')

    TENK_DATA_EXTRACTOR_OPENAI_MODEL_NAME = os.environ.get('TENK_DATA_EXTRACTOR_OPENAI_MODEL_NAME', 'gpt-4o')

    # --------------------- Langmanus-compatible LLM config ----------------------
    # Reasoning LLM (DeepSeek or similar; used when deep_thinking_mode is enabled)
    REASONING_MODEL = os.environ.get('REASONING_MODEL', 'o3-deep-research')
    REASONING_BASE_URL = os.environ.get('REASONING_BASE_URL')
    REASONING_API_KEY = os.environ.get('OPENAI_API_KEY')
    # Basic LLM (default general-purpose model)
    BASIC_MODEL = os.environ.get('BASIC_MODEL', 'gpt-4o')
    BASIC_BASE_URL = os.environ.get('BASIC_BASE_URL')
    BASIC_API_KEY = os.environ.get('OPENAI_API_KEY')
    # Vision-language LLM (used by browser tool, etc.)
    VL_MODEL = os.environ.get('VL_MODEL', 'gpt-4o')
    VL_BASE_URL = os.environ.get('VL_BASE_URL')
    VL_API_KEY = os.environ.get('OPENAI_API_KEY')


    # --------------------------------- Database Availability ----------------------------
    CHROMA_DATA_BASE_AVAILABILITY = os.environ.get('CHROMA_DATA_BASE_AVAILABILITY', 'NO')   # Options: YES / NO
    GRAPH_DATA_BASE_AVAILABILITY = os.environ.get('GRAPH_DATA_BASE_AVAILABILITY', 'YES')    # Options: YES / NO

    
    # ------------------------------- Neo4j (GRAPH_DB) Settings --------------------------------
    NEO4J_URI = os.environ.get('NEO4J_URI', "")
    NEO4J_USERNAME = os.environ.get('NEO4J_USERNAME', "neo4j")
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', "")
    NEO4J_INDEX_NAME = os.environ.get('NEO4J_INDEX_NAME', 'form_10k_chunks')
    NEO4J_NODE_LABEL = os.environ.get('NEO4J_NODE_LABEL', 'Chunk')
    NEO4J_TEXT_NODE_PROPERTY = os.environ.get('NEO4J_TEXT_NODE_PROPERTY', 'text')
    NEO4J_EMBEDDING_NODE_PROPERTY = os.environ.get('NEO4J_EMBEDDING_NODE_PROPERTY', 'textEmbedding')
    # Enable writes to Neo4j API endpoint when set truthy (e.g., "true")
    ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER = os.environ.get('ALLOW_NEO4J_WRITE_NEO4J_QUERY_ROUTER', 'false')

    # ------------------------------- Chroma DB Settings --------------------------------
    CHROMA_DB_PATH = os.environ.get('CHROMA_DB_PATH', os.path.join(BASE_DIR, 'databases', 'user_data'))
    CHROMA_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION_NAME', "user_data")


    # ------------------------------- API Keys --------------------------------
    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
    TAVILY_MAX_RESULTS = int(os.environ.get('TAVILY_MAX_RESULTS', '5'))

    # Chrome instance (optional, for browser-use)
    CHROME_INSTANCE_PATH = os.environ.get('CHROME_INSTANCE_PATH')

    # AlphaVantage configuration
    ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')
    ALPHA_VANTAGE_BASE_URL = os.environ.get('ALPHA_VANTAGE_BASE_URL', 'https://www.alphavantage.co/query')
    AVAILABLE_TOPICS = os.environ.get('ALPHAVANTAGE_AVAILABLE_TOPICS','blockchain,earnings,financial_markets,mergers_and_acquisitions,ipo,technology').split(',')

    # ------------------------------- Special Metric Cache source selection -------------------------------
    # Primary market-data source for:
    #   POST /api/special_metrics/refresh_special_metric_cache_all
    # Allowed: alphavantage | yahoo
    # Default requested: yahoo
    SPECIAL_METRIC_CACHE_PRIMARY_SOURCE = os.environ.get('SPECIAL_METRIC_CACHE_PRIMARY_SOURCE', 'yahoo')
    # Only used when primary source is yahoo
    SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS = int(os.environ.get('SPECIAL_METRIC_CACHE_YAHOO_MAX_WORKERS', '10'))
    # Only used when primary source is alphavantage
    # NOTE: default is 1 (sequential) to reduce rate-limit risk; can be increased if needed.
    SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS = int(os.environ.get('SPECIAL_METRIC_CACHE_ALPHAVANTAGE_MAX_WORKERS', '1'))

    # OLD market cache refresh (yfinance) workers:
    #   POST /api/special_metrics/refresh_StockPrices_SharesOutstanding_MetricOldCache
    SPECIAL_METRIC_OLD_CACHE_YAHOO_MAX_WORKERS = int(os.environ.get('SPECIAL_METRIC_OLD_CACHE_YAHOO_MAX_WORKERS', '5'))
    # Toggle: when truthy, do not call Alpha Vantage APIs; only use cached nodes
    # Note: name kept as requested (UES_ONLY_CASHE_NODES)
    USE_ONLY_CACHE_NODES = os.environ.get('USE_ONLY_CACHE_NODES', 'True')

    # ------------------------------- Logging --------------------------------
    DEBUG_ENABLE = os.environ.get('DEBUG_ENABLE', 'false').lower() in ('1', 'true', 'yes', 'on')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG' if DEBUG_ENABLE else 'INFO')

    # ------------------------------- chatbot_type -------------------------------
    GENERAL_BOT_TYPE = os.environ.get('GENERAL_BOT_TYPE', 'General_Agent_Graph')
    DEEP_BOT_TYPE = os.environ.get('DEEP_BOT_TYPE', 'Deep_Agent_Graph')
    UPDATE_GRAPH_BOT_TYPE = os.environ.get('UPDATE_GRAPH_BOT_TYPE', 'Neo4j_Update_Agent_Graph')
    DEDICATED_REPORT_GENERATOR_BOT_TYPE = os.environ.get('DEDICATED_REPORT_GENERATOR_BOT_TYPE', 'Report_Generation_Agent_Graph')


    # ------------------------------- Team members (Langmanus) --------------------
    TEAM_MEMBERS = [
        "coder_agent",
        "researcher_agent",
        "visualization_agent",
        "reporter_agent",
    ]


    # -------------------------------- File Paths ------------------------------------
    SESSION_DATABASE_PATH = os.getenv('SESSION_DATABASE_PATH', os.path.join(BASE_DIR, 'databases/chat_history', 'chat_sessions.db'))
    SESSION_REPORT_DATABASE_PATH = os.getenv('SESSION_REPORT_DATABASE_PATH', os.path.join(BASE_DIR, 'databases/chat_history', 'report_chat_sessions.db'))
    SESSION_UPDATE_NEO4J_DATABASE_PATH = os.getenv('SESSION_UPDATE_NEO4J_DATABASE_PATH', os.path.join(BASE_DIR, 'databases/chat_history', 'update_neo4j_chat_sessions.db'))

    # ------------------------------- Attachments --------------------------------
    ATTACHMENTS_CHROMA_DB_PATH = os.environ.get('ATTACHMENTS_CHROMA_DB_PATH',os.path.join(BASE_DIR, 'databases', 'attachments_chroma_db'))
    ATTACHMENTS_CHROMA_COLLECTION_NAME = os.environ.get('ATTACHMENTS_CHROMA_COLLECTION_NAME')

    # ------------------------------- Utility Methods --------------------------------
    @classmethod
    def initialize_directories(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(os.path.dirname(cls.SESSION_DATABASE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.SESSION_REPORT_DATABASE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.SESSION_UPDATE_NEO4J_DATABASE_PATH), exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    ENV = "testing"

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    ENV = "production"

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    env_name = os.environ.get('APP_ENV', 'default')  # ✅ replaced FLASK_CONFIG with APP_ENV
    config_obj = config.get(env_name, DevelopmentConfig)
    config_obj.initialize_directories()
    return config_obj
