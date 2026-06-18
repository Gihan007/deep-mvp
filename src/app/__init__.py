# path: src/app/__init__.py

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from config import get_config
import os
from contextlib import asynccontextmanager

def create_app():
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: initialize async streaming checkpointers once (needs event loop)
        for _bot_attr in ("general_chatbot","deep_chatbot","update_chatbot","dedicated_report_generator_chatbot",):
            bot = getattr(app, _bot_attr, None)
            if bot is None:
                continue
            setup = getattr(bot, "setup_async_streaming", None)
            if callable(setup):
                try:
                    await setup()
                except Exception as e:
                    print(f"[lifespan] Warning: async streaming setup failed for {_bot_attr}: {e}")

        yield

        # Shutdown: close async sqlite connections
        for _bot_attr in ("general_chatbot","deep_chatbot","update_chatbot","dedicated_report_generator_chatbot",):
            bot = getattr(app, _bot_attr, None)
            if bot is None:
                continue
            close = getattr(bot, "aclose", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    pass

    app = FastAPI(title="ChatQA Bot API", version="1.0.0", lifespan=lifespan)
    
    # Get configuration
    config = get_config()

    # --------------------
    # Lightweight health endpoints (used by Docker/Compose healthchecks)
    # --------------------
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Some healthcheck clients (and `wget --spider`) may send HEAD requests.
    # Explicitly support HEAD to avoid 405 Method Not Allowed.
    @app.head("/health")
    async def health_head():
        return Response(status_code=200)

    @app.get("/ready")
    async def ready():
        # Keep this lightweight; if you want DB readiness checks, we can add them here.
        return {"status": "ready"}

    @app.head("/ready")
    async def ready_head():
        return Response(status_code=200)

    # Ensure LangSmith env vars are set in the process BEFORE any LangChain/LangGraph imports/use.
    # def _truthy(v):
    #     return str(v).strip().lower() in ("1", "true", "yes", "y", "on")
    # Do not override if already provided by the environment/container
    # if "LANGSMITH_TRACING" not in os.environ:
    #     os.environ["LANGSMITH_TRACING"] = "true" if _truthy(getattr(config, "LANGSMITH_TRACING", "true")) else "false"
    # if getattr(config, "LANGSMITH_API_KEY", None) and "LANGSMITH_API_KEY" not in os.environ:
    #     os.environ["LANGSMITH_API_KEY"] = str(config.LANGSMITH_API_KEY)
    # if getattr(config, "LANGSMITH_PROJECT", None) and "LANGSMITH_PROJECT" not in os.environ:
    #     os.environ["LANGSMITH_PROJECT"] = str(config.LANGSMITH_PROJECT)


    # Import LangChain/LangGraph dependent modules only AFTER env vars are set so tracing hooks initialize correctly
    from app.models.lanchain_generalized_model_initializer import (
        LangChainGeneralizedChatModelInitializer,
        LangChainGeneralizedEmbeddingModelInitializer,
    )
    from app.graphs.Deep_Agnet_Graph import DAG_ChatQABot
    from app.graphs.General_Agent_Graph import GAG_ChatQABot
    from app.graphs.Neo4j_Update_Agent_Graph import NUAG_ChatQABot
    from app.graphs.Report_Generation_Agent_Graph import RGAG_ChatQABot
    # from app.graphs.Langmanus_Graph import LM_ChatQABot
    # from app.graphs.Custom_Update_Graph import CU_ChatQABot

    from app.utills.vector_store import VectorStoreBuilder
    from langchain_neo4j import Neo4jGraph


    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize models
    app.llm = LangChainGeneralizedChatModelInitializer(config).get_LLM()
    app.embeddings = LangChainGeneralizedEmbeddingModelInitializer(config).get_EMBEDDINGS()
    
    CHROMA_DATA_BASE_AVAILABILITY = config.CHROMA_DATA_BASE_AVAILABILITY
    GRAPH_DATA_BASE_AVAILABILITY = config.GRAPH_DATA_BASE_AVAILABILITY

    GENERAL_BOT_TYPE = config.GENERAL_BOT_TYPE
    DEEP_BOT_TYPE = config.DEEP_BOT_TYPE
    UPDATE_GRAPH_BOT_TYPE = config.UPDATE_GRAPH_BOT_TYPE
    DEDICATED_REPORT_GENERATOR_BOT_TYPE = config.DEDICATED_REPORT_GENERATOR_BOT_TYPE

    graphdb_vector_store = None
    chromadb_vector_store = None
    
    if GRAPH_DATA_BASE_AVAILABILITY == "YES":
        graphdb_vector_store = VectorStoreBuilder(app.embeddings, config).create_graphDB_vector_store()
    if CHROMA_DATA_BASE_AVAILABILITY == "YES":
        chromadb_vector_store = VectorStoreBuilder(app.embeddings, config).create_chroma_vector_store()


    # ------------------GENERAL_BOT----------------
    if GENERAL_BOT_TYPE == "General_Agent_Graph":
        app.general_chatbot = GAG_ChatQABot(llm=app.llm, config=config, graphdb_vector_store=graphdb_vector_store, chromadb_vector_store=chromadb_vector_store)
    else:
        raise ValueError(f"Invalid BOT_TYPE: {GENERAL_BOT_TYPE}")


    # ------------------DEEP_BOT----------------
    if DEEP_BOT_TYPE == "Deep_Agent_Graph":
        app.deep_chatbot = DAG_ChatQABot(llm=app.llm, config=config, graphdb_vector_store=graphdb_vector_store, chromadb_vector_store=chromadb_vector_store)
    else:
        raise ValueError(f"Invalid BOT_TYPE: {DEEP_BOT_TYPE}")


    # ------------------UPDATE_GRAPH_BOT----------------
    if UPDATE_GRAPH_BOT_TYPE == "Neo4j_Update_Agent_Graph":
        app.update_chatbot = NUAG_ChatQABot(llm=app.llm, config=config, graphdb_vector_store=graphdb_vector_store, chromadb_vector_store=chromadb_vector_store)
    else:
        raise ValueError(f"Invalid BOT_TYPE: {UPDATE_GRAPH_BOT_TYPE}")


    # ------------------REPORT_GENERATOR_BOT----------------
    if DEDICATED_REPORT_GENERATOR_BOT_TYPE == "Report_Generation_Agent_Graph":
        app.dedicated_report_generator_chatbot = RGAG_ChatQABot(config=config, graphdb_vector_store=graphdb_vector_store, chromadb_vector_store=chromadb_vector_store)
    else:
        raise ValueError(f"Invalid BOT_TYPE: {DEDICATED_REPORT_GENERATOR_BOT_TYPE}")


    # Include routers
    from app.routes.general_chatbot_router import router as general_chatbot_router
    from app.routes.deep_chatbot_router import router as deep_chatbot_router
    from app.routes.dedicated_report_generator_chatbot_router import router as dedicated_report_generator_chatbot_router
    from app.routes.data_injest_to_graph_db_router import router as data_injest_to_graph_db_router
    from app.routes.neo4j_query_router import router as neo4j_query_router
    from app.routes.neo4j_update_graph_router import router as neo4j_update_graph_router
    from app.routes.get_special_metric_data_router import router as get_special_metric_data_router
    from app.routes.dynamic_table_router import router as dynamic_table_router
    from app.routes.central_api_router import router as central_api_router
    from app.routes.session_router import router as session_router
    from app.routes.session_report_router import router as session_report_router
    from app.routes.session_update_neo4j_router import router as session_update_neo4j_router
    from app.routes.kpi_metric_router import router as kpi_metric_router


    app.include_router(general_chatbot_router, tags=["general-chatbot"])
    app.include_router(dedicated_report_generator_chatbot_router, tags=["dedicated_report_generator"])
    app.include_router(deep_chatbot_router, tags=["deepchatbot"])
    app.include_router(data_injest_to_graph_db_router, tags=["data-injestion-graph"])
    app.include_router(neo4j_query_router, tags=["graphdb-cypher"])
    app.include_router(neo4j_update_graph_router, tags=["graphdb-update"])
    app.include_router(get_special_metric_data_router, tags=["special-metrics-cal"])
    app.include_router(dynamic_table_router, tags=["dynamic-table"])
    app.include_router(central_api_router, tags=["central-api"])
    app.include_router(session_router, tags=["session"])
    app.include_router(session_report_router, tags=["session-report"])
    app.include_router(session_update_neo4j_router, tags=["session-udate-neo4j"])
    app.include_router(kpi_metric_router, tags=["kpi-metrics"])
   

    # Debug: Print out registered routes
    print("Registered routes:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"{route.path}: {route.methods}")

    return app
