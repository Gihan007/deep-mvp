# File: graphs/LangGraph_Supervisor_Graph.py



import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import base64
from datetime import datetime

from app.prompts.prompts_deep import Deep_Agent_Instructions_Prompt
from langchain_core.prompts import PromptTemplate
from app.prompts.markdown import get_prompt_template
# Import the tool initialization system
from app.tools import initialize_all_tools
from typing import List, Optional, Dict, Any, Annotated
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from app.utills.media_content_handdler import MediaContentMixin
import traceback
import re
import os
from app.utills.source_details_coillector_utills import images_to_base64, extract_images_from_source_details, strip_unmatched_fig_placeholders
from app.utills.tool_output_collector import reset_tool_outputs, get_tool_outputs
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from app.utills.message_utils import safe_get_text_from_message

# Optional dependency: the app should not crash at import-time if Gemini support
# # isn't installed in a given Docker image.
# try:
#     from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# except Exception:  # ImportError (or any packaging-related issue)
#     ChatGoogleGenerativeAI = None  # type: ignore
#     GoogleGenerativeAIEmbeddings = None  # type: ignore

from app.utills.logging_config import configure_graph_logging
configure_graph_logging(__name__)
import logging
logger = logging.getLogger(__name__)
for _neo_logger_name in ("neo4j", "neo4j.io", "neo4j.pool"):
    logging.getLogger(_neo_logger_name).setLevel(logging.WARNING)

from app.prompts.deep_report_prompts import deep_report_generating_agent_human_prompt
from app.utills.markdown_pdf_base64_converter import create_pdf_from_markdown





class RGAG_ChatQABot:

    def __init__(self, config, graphdb_vector_store, chromadb_vector_store):

        
        self.openai_model_name = config.REPORT_GENERATION_OPENAI_MODEL
        self.google_model_name = config.REPORT_GENERATION_GOOGLE_MODEL


        self.llm = ChatOpenAI(model=self.openai_model_name, api_key=config.OPENAI_API_KEY)
        #self.llm = ChatGoogleGenerativeAI(model=self.google_model_name,google_api_key=config.GOOGLE_API_KEY)

        self.graphdb_vector_store = graphdb_vector_store
        self.chromadb_vector_store = chromadb_vector_store
        self.config = config

        self.db_path = self.config.SESSION_REPORT_DATABASE_PATH

        # Initialize all tools
        self.tools = initialize_all_tools(graphdb_vector_store, chromadb_vector_store , self.llm, config)
        self._organize_tools()
        self.chat_qa_bot_sql = self.create_graph()

    def _save_workflow_diagram(self, app):
        """Save the workflow diagram as PNG to temp directory."""
        try:
            import tempfile
            import os
            
            image_bytes = app.get_graph().draw_mermaid_png()
            temp_dir = tempfile.gettempdir()
            diagram_path = os.path.join(temp_dir, "langgraph_supervisor_mermaid.png")
            
            with open(diagram_path, "wb") as f:
                f.write(image_bytes)
            print(f"Supervisor workflow diagram saved to {diagram_path}")
        except Exception as e:
            print(f"Could not save workflow diagram: {e}")



    def _rebuild_graphs_with_current_time(self):
        """
        Recreate the ReAct agent graph with CURRENT_TIME computed at call time.
        Ensures timezone-aware timestamp.
        """
        def _fmt_md(name: str, extra: str = "") -> str:
            tmpl = PromptTemplate(input_variables=["CURRENT_TIME"], template=get_prompt_template(name))
            sys_str = tmpl.format(CURRENT_TIME=datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S %z"))
            return sys_str + extra

        # NOTE: create_react_agent returns a CompiledStateGraph.
        # We pass the system prompt via `prompt=` and attach the SqliteSaver checkpointer
        # so conversation history is persisted per `thread_id`.

        # Enable OpenAI parallel tool calls (model may emit multiple tool_calls in one turn).
        # ToolNode (used internally by create_react_agent) will then execute those tool calls
        # concurrently.
        model = self._maybe_enable_parallel_tool_calls(self.llm)
        graph_sql = create_react_agent(
            model=model,
            tools=self.all_tool,
            prompt=_fmt_md("deep_agent_report_generator"),
            checkpointer=self.sql_memory,
        )
        return graph_sql

    def _maybe_enable_parallel_tool_calls(self, model):
        """Try to enable parallel tool calls for OpenAI-compatible chat models.

        Notes:
        - This does NOT force parallelism by itself; it only allows the LLM to
          request multiple tool calls in a single assistant turn.
        - LangGraph's ToolNode will execute multiple requested tool calls in parallel.
        - For non-OpenAI models, we leave the model unchanged.
        """
        try:
            if isinstance(model, (ChatOpenAI, AzureChatOpenAI)):
                model_with_parerall_tool_calls = model.bind(parallel_tool_calls=True)
                #print("model_with_parerall_tool_calls OK")
                return model_with_parerall_tool_calls
        except Exception:
            #print("If binding fails for any reason, fall back safely.")
            # If binding fails for any reason, fall back safely.
            return model
        return model

    def _organize_tools(self):

        """Organize tools by category for different agents"""
        # Get tools by name for easy access
        tool_dict = {tool.name: tool for tool in self.tools}

        self.all_tool = []
        # Report generator: keep the toolset small and consistent with
        # `prompts/md/deep_agent_report_generator.md`.
        if 'investment_factor_ranking_table_tool' in tool_dict:
            self.all_tool.append(tool_dict['investment_factor_ranking_table_tool'])
        if 'graph_db_cypher_query_tool' in tool_dict:
            self.all_tool.append(tool_dict['graph_db_cypher_query_tool'])
        if 'duckduckgo_search_tool' in tool_dict:
            self.all_tool.append(tool_dict['duckduckgo_search_tool'])
        if 'visualization_tool' in tool_dict:
            self.all_tool.append(tool_dict['visualization_tool'])
        if 'alphavantage_comprehensive_tool' in tool_dict:
            self.all_tool.append(tool_dict['alphavantage_comprehensive_tool'])
        if 'python_repl_tool' in tool_dict:
            self.all_tool.append(tool_dict['python_repl_tool'])

        
    def _create_checkpointer(self, db_path: str):
        """Create a proper SQLite checkpointer instance."""
        try:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            self.conn = conn
            print(f"SQLite checkpointer created successfully: {db_path}")
            return checkpointer

        except Exception as e:
            print(f"Failed to create SQLite checkpointer: {e}")
            print("Falling back to MemorySaver")
            return MemorySaver()


    async def _create_async_checkpointer(self, db_path: str):
        """Create an AsyncSqliteSaver for streaming (.astream).

        NOTE: requires `aiosqlite`.
        """
        try:
            import aiosqlite

            conn = await aiosqlite.connect(db_path)
            checkpointer = AsyncSqliteSaver(conn)
            self.async_conn = conn
            return checkpointer
        except Exception as e:
            raise RuntimeError(
                f"Failed to create AsyncSqliteSaver at '{db_path}'. "
                "Install aiosqlite and ensure the path is writable."
            ) from e


    async def setup_async_streaming(self) -> None:
        """Initialize AsyncSqliteSaver + build streaming deep agent once.

        This should be called from FastAPI startup/lifespan (recommended),
        because it requires a running asyncio event loop.
        """
        if getattr(self, "chat_qa_bot_async", None) is not None:
            return

        self.async_memory = await self._create_async_checkpointer(self.db_path)
        model = self._maybe_enable_parallel_tool_calls(self.llm)
        # create_react_agent returns a CompiledStateGraph; create it once for streaming
        self.chat_qa_bot_async = create_react_agent(
            model=model,
            tools=self.all_tool,
            prompt=PromptTemplate(
                input_variables=["CURRENT_TIME"],
                template=get_prompt_template("deep_agent_report_generator"),
            ).format(CURRENT_TIME=datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S %z")),
            checkpointer=self.async_memory,
        )

    
    async def aclose(self) -> None:
        """Close async sqlite connection if created."""
        conn = getattr(self, "async_conn", None)
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                pass
            self.async_conn = None


    def create_graph(self):

        # Initialize sync checkpointer once
        self.sql_memory = self._create_checkpointer(self.db_path)

        # Delegate to the unified builder that computes CURRENT_TIME at call-time
        graph_sql = self._rebuild_graphs_with_current_time()
        self._save_workflow_diagram(graph_sql)
        return graph_sql
    

    # @traceable(name="DA_ChatQABot.run", metadata={"component": "chatbot", "entrypoint": "run"})
    def run(self, input_data: dict) -> dict:

        instructions = input_data.get("instructions", None)
        session_id = input_data.get("session_id", "default")
        report_type = input_data.get("report_type", "custom_analysis")  # company_performance_and_investment_thesis, industry_deep_drive, custom_analysis
        time_horizon = input_data.get("time_horizon", "last 5 years")
        ticker = input_data.get("ticker")
        company_name = input_data.get("company_name")
        industry_name = input_data.get("industry_name")


        human_prompt = deep_report_generating_agent_human_prompt(report_type,time_horizon, ticker, company_name, industry_name, instructions)
        question = human_prompt['prompt']
        missing_data = human_prompt['missing_data']
        if missing_data:
            return {"answer": f"Missing data: {missing_data}", "session_id": session_id, "source_details": None, "output_images_data": None, "base64_images": None}

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")

        human_message = HumanMessage(content=question)
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}

        # create_react_agent expects `remaining_steps` in the state (limits tool/action loops).
        initial_state = {"messages": [human_message], "remaining_steps": 10}

        try:
            # Inject realtime CURRENT_TIME with negligible overhead
            now_str = datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S %z")
            time_msg = SystemMessage(content=f"CURRENT_TIME: {now_str}")
            initial_state["messages"] = [time_msg] + initial_state["messages"]
            # Run the graph - it will now maintain conversation history
            reset_tool_outputs()
            response = self.chat_qa_bot_sql.invoke(initial_state, config)
            messages = response["messages"]
            last_ai_index = None
            # for i in reversed(range(len(messages))):
            #     if isinstance(messages[i], AIMessage):
            #         last_ai_index = i
            #         break
            # last_ai_message = messages[last_ai_index] if last_ai_index is not None else None

            source_details = get_tool_outputs()
            images_data = extract_images_from_source_details(source_details)
            base64_images = images_to_base64(images_data)

            answer_text = ""
            if isinstance(messages, list) and messages:
                answer_text = safe_get_text_from_message(messages[-1])

            answer_text = answer_text.strip() or "I'm sorry, I couldn't generate a response to this question."
            # Remove fig placeholders that don't have a matching visualization_tool output
            answer_text = strip_unmatched_fig_placeholders(answer_text, images_data)
            # Produce a single-page (tall) PDF so *all* content fits into one PDF page.
            # Robust fallback: if single-page rendering fails, retry multi-page so the API
            # returns a response instead of 500.
            try:
                report_base64 = create_pdf_from_markdown(answer_text, base64_images=base64_images, single_page=True)
            except Exception:
                report_base64 = create_pdf_from_markdown(answer_text, base64_images=base64_images, single_page=False)

            print("-----------------")
            print("messages: ", messages)
            print("-----------------")
            print("source_details: ", source_details)
            print("-----------------")
            print("images_data: ", images_data)
            print("-----------------")
            print("last_ai_message: ", messages[-1])
            print("-----------------")
            print("answer: ", answer_text)
            print("-----------------")
       
            return {
                "answer": answer_text,
                "session_id": session_id,
                "source_details": source_details,
                "base64_images": base64_images,
                "report_base64": report_base64
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error in _add_media_content_to_messages:\n{tb_str}")
            raise



    # @traceable(name="DA_ChatQABot.stream", metadata={"component": "chatbot", "entrypoint": "stream"})
    async def stream(self, input_data: dict):

        instructions = input_data.get("instructions", None)
        session_id = input_data.get("session_id", "default")
        report_type = input_data.get("report_type", "custom_analysis")  # company_performance_and_investment_thesis, industry_deep_drive, custom_analysis
        time_horizon = input_data.get("time_horizon", "last 5 years")
        ticker = input_data.get("ticker")
        company_name = input_data.get("company_name")
        industry_name = input_data.get("industry_name")


        human_prompt = deep_report_generating_agent_human_prompt(report_type,time_horizon, ticker, company_name, industry_name, instructions)
        question = human_prompt['prompt']
        missing_data = human_prompt['missing_data']
        if missing_data:
            yield {
                "type": "done",
                "session_id": session_id,
                "answer": f"Missing data: {missing_data}",
                "source_details": None,
                "output_images_data": None,
                "base64_images": None
            }
            return

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")

        human_message = HumanMessage(content=question)
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        initial_state = {"messages": [human_message], "remaining_steps": 10}
        stream_messages = [human_message]

        try:

            # Inject realtime CURRENT_TIME with negligible overhead
            now_str = datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S %z")
            time_msg = SystemMessage(content=f"CURRENT_TIME: {now_str}")
            initial_state["messages"] = [time_msg] + initial_state["messages"]
            
            
            # Ensure async graph is ready (normally pre-initialized at FastAPI startup)
            if getattr(self, "chat_qa_bot_async", None) is None:
                await self.setup_async_streaming()

            reset_tool_outputs()
            final_text = ""

            async for token, metadata in self.chat_qa_bot_async.astream(initial_state, config, stream_mode="messages"):
                
                text = safe_get_text_from_message(token)

                # Identify node/agent if available
                node = None
                try:
                    node = metadata.get("langgraph_node") or metadata.get("node") or metadata.get("source")
                except Exception:
                    node = None

                # Track all message types for artifact extraction later
                try:
                    stream_messages.append(token)
                except Exception:
                    pass

                # Only stream AIMessage (assistant) outputs
                if not isinstance(token, AIMessage):
                    continue
                # Skip supervisor control messages (e.g., {"next": "..."} decisions)
                if node == "supervisor":
                    continue
                # Skip router/control JSON payloads such as {"next":"..."}
                try:
                    if text and re.fullmatch(r"\s*\{\s*\"next\"\s*:\s*\".*?\"\s*\}\s*", text):
                        continue
                except Exception:
                    pass
                # start streamming ...

                if text:
                    final_text += text

                    # Stream line-by-line so we can suppress ghost figure placeholders
                    # (placeholders emitted without an actual visualization_tool image).
                    if not hasattr(self, "_stream_buf"):
                        self._stream_buf = ""
                    self._stream_buf += text

                    while "\n" in self._stream_buf:
                        line, rest = self._stream_buf.split("\n", 1)
                        line = line + "\n"
                        self._stream_buf = rest

                        # If this is a figure placeholder line, only emit it if it matches an existing image.
                        if re.match(r"^\s*\[fig_description-.*?\]\s*$", line):
                            try:
                                sd = get_tool_outputs()
                                imgs = extract_images_from_source_details(sd)
                                filtered = strip_unmatched_fig_placeholders(line, imgs)
                                if filtered:
                                    yield {"type": "token", "agent": node, "role": "assistant", "content": filtered}
                            except Exception:
                                # If anything goes wrong, drop the placeholder to avoid ghost figures
                                pass
                        else:
                            yield {"type": "token", "agent": node, "role": "assistant", "content": line}



            # NOTE: We rely on the AsyncSqliteSaver-backed graph for persistence.
            # No manual update_state() here to avoid duplicating checkpoints/messages.

            # Collect source details and images from streamed messages
            try:
                source_details = get_tool_outputs()
            except Exception as _e1:
                source_details = []

            try:
                images_data = extract_images_from_source_details(source_details)
            except Exception as _e2:
                images_data = []

            try:
                base64_images = images_to_base64(images_data)
            except Exception as _e3:
                base64_images = []

            # Remove fig placeholders that don't have a matching visualization_tool output
            final_text = strip_unmatched_fig_placeholders(final_text, images_data)

            # Flush any remaining buffered stream text (and filter placeholders) before sending done.
            try:
                buf = getattr(self, "_stream_buf", "")
                if buf:
                    if re.match(r"^\s*\[fig_description-.*?\]\s*$", buf):
                        filtered = strip_unmatched_fig_placeholders(buf, images_data)
                        if filtered:
                            yield {"type": "token", "agent": node, "role": "assistant", "content": filtered}
                    else:
                        yield {"type": "token", "agent": node, "role": "assistant", "content": buf}
                self._stream_buf = ""
            except Exception:
                pass

            try:
                # Produce a single-page (tall) PDF so *all* content fits into one PDF page.
                report_base64 = create_pdf_from_markdown(final_text, base64_images=base64_images, single_page=True)
            except Exception:
                # Fallback to multi-page PDF (never fail streaming response due to PDF generation).
                try:
                    report_base64 = create_pdf_from_markdown(final_text, base64_images=base64_images, single_page=False)
                except Exception:
                    report_base64 = ""


            print("-----------------")
            print("stream_messages: ", stream_messages)
            print("-----------------")
            print("source_details: ", source_details)
            print("-----------------")
            print("images_data: ", images_data)
            print("-----------------")
            print("answer: ", final_text)
            print("-----------------")

            yield {
                "type": "done",
                "session_id": session_id,
                "answer": final_text,
                "source_details": source_details,
                "base64_images": base64_images,
                "report_base64": report_base64
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error in stream:\n{tb_str}")
            yield {"type": "error", "error": str(e), "session_id": session_id}