# File: graphs/LangGraph_Supervisor_Graph.py

# from langgraph_supervisor import create_supervisor
# from app.graphs.update_agent import UpdateGraphDBAgent
from langgraph.prebuilt import create_react_agent
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage, AIMessageChunk
import base64
from datetime import datetime

from app.prompts.prompts import  Supervisor_Prompt , General_QA_Agent_Prompt
from app.prompts.markdown import get_prompt_template
from langchain_core.prompts import PromptTemplate

# Import the tool initialization system
from app.tools import initialize_all_tools
from typing import List, Optional, Dict, Any, Annotated
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from app.utills.media_content_handdler import MediaContentMixin
import traceback
import re
from langgraph.prebuilt import ToolNode
from app.utills.tool_output_collector import reset_tool_outputs, get_tool_outputs
from app.utills.source_details_coillector_utills import images_to_base64, extract_images_from_source_details
from app.utills.custom_supervisor_graph_utills.langgraph_agents import AgentNode
from app.utills.custom_supervisor_graph_utills.langgraph_supervisor import SupervisorNode
from app.utills.custom_supervisor_graph_utills.langgraph_agent_router import AgentRouter
from app.utills.custom_supervisor_graph_utills.approval_checker import check_user_approval
from langgraph.graph import END, START, StateGraph
from langsmith import traceable
from app.utills.message_utils import safe_get_text_from_message

# ADD THIS: Define proper state schema for conversation tracking
class NUAG_GraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]  # This enables conversation history
    tool_calls: Annotated[Optional[List[ToolMessage]], add_messages]
    sender: Optional[str]
    user_approved_update: Optional[bool]  # Flag for user confirmation (yes/proceed/ok)
    user_rejected_update: Optional[bool]  # Flag for user rejection (no/cancel/stop)


class NUAG_ChatQABot:

    def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store):
        self.llm = llm
        self.graphdb_vector_store = graphdb_vector_store
        self.chromadb_vector_store = chromadb_vector_store
        self.config = config
        self.db_path = self.config.SESSION_UPDATE_NEO4J_DATABASE_PATH
        self.memory = self._create_checkpointer(self.db_path)

        # Initialize all tools
        self.tools = initialize_all_tools(graphdb_vector_store, chromadb_vector_store , llm, config)
        self._organize_tools()
        self.chat_qa_bot = self.create_graph()


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

    def _organize_tools(self):
        """Organize tools by category for different agents"""
        tool_dict = {tool.name: tool for tool in self.tools}

        self.update_graph_tools = []
        # Use ONLY the update tool - it handles both READ and WRITE
        if 'update_graph_based_on_user_q' in tool_dict:
            self.update_graph_tools.append(tool_dict["update_graph_based_on_user_q"])


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
        """Initialize AsyncSqliteSaver + compile async graph once.

        This should be called from FastAPI startup/lifespan (recommended),
        because it requires a running asyncio event loop.
        """
        if getattr(self, "chat_qa_bot_async", None) is not None:
            return
        self.async_memory = await self._create_async_checkpointer(self.db_path)
        self.chat_qa_bot_async = self._builder.compile(checkpointer=self.async_memory)


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
        """
        SIMPLIFIED ARCHITECTURE: Single agent with approval workflow
        Flow: START -> approval_checker -> update_agent -> END
        """

        # Wrapper to inject system prompt
        def update_agent_with_prompt(state):
            # Recompute system prompt with current time for every invocation
            tmpl = PromptTemplate(input_variables=["CURRENT_TIME"],template=get_prompt_template("graphdb_update_graph_agent"),)
            graphdb_update_graph_agent_prompt = tmpl.format(CURRENT_TIME=datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S %z"))
            # Prepend system message if not already present

            messages = state.get("messages", [])
            if not messages or not isinstance(messages[0], SystemMessage):
                state["messages"] = [SystemMessage(content=graphdb_update_graph_agent_prompt)] + messages
            return create_react_agent(self.llm, tools=self.update_graph_tools).invoke(state)

        # Build simple graph: approval_checker -> agent -> END
        builder = StateGraph(NUAG_GraphState)

        builder.add_edge(START, "approval_checker")
        builder.add_node("approval_checker", check_user_approval)
        builder.add_edge("approval_checker", "update_agent")
        builder.add_node("update_agent", update_agent_with_prompt)
        builder.add_edge("update_agent", END)
        
        # Keep builder so we can compile an async (AsyncSqliteSaver) graph lazily for streaming.
        self._builder = builder

        compiled_graph_sql = builder.compile(checkpointer=self.memory)
        self._save_workflow_diagram(compiled_graph_sql)
        return compiled_graph_sql



    @traceable(name="CU_ChatQABot.run",metadata={"component": "update_bot", "entrypoint": "run"})
    def run(self, input_data: dict) -> dict:

        question = input_data.get("question", "")
        session_id = input_data.get("session_id", "default")

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")
        print(f"Question: {question}")



        config = {"configurable": {"thread_id": session_id}}
        human_message = HumanMessage(content=question)

        initial_state = {"messages": [human_message], "remaining_steps": 10,}

        try:
            # Run the graph - it will now maintain conversation history
            reset_tool_outputs()
            response = self.chat_qa_bot.invoke(initial_state, config)
            messages = response["messages"]
            
            # Find last AIMessage (excluding system messages)
            last_ai_index = None
            for i in reversed(range(len(messages))):
                if isinstance(messages[i], AIMessage):
                    # Skip system messages
                    msg_name = getattr(messages[i], 'name', None)
                    if msg_name != 'system':
                        last_ai_index = i
                        break
            last_ai_message = messages[last_ai_index] if last_ai_index is not None else None



            answer = safe_get_text_from_message(last_ai_message)
            source_details = get_tool_outputs()

            print("-----------------")
            print("messages: ", messages)
            print("-----------------")
            print("source_details: ", source_details)
            print("-----------------")
            print("last_ai_message: ", last_ai_message)
            print("-----------------")
            print("answer: ", answer)
            print("-----------------")


            return {
                "answer": answer,
                "session_id": session_id,
                "source_details": source_details,
                "source": source_details
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error in _add_media_content_to_messages:\n{tb_str}")
            raise



    @traceable(name="CU_ChatQABot.stream",metadata={"component": "update_bot", "entrypoint": "stream"})
    async def stream(self, input_data: dict):
        """
        Async generator that streams tokens per-agent as the graph executes.
        Yields dict events shaped like:
          {"type": "token", "agent": "graphDB_search_agent", "role": "assistant", "content": "...partial..."}
          {"type": "done", "session_id": "..."}
          {"type": "error", "error": "...", "session_id": "..."}
        """
        question = input_data.get("question", "")
        session_id = input_data.get("session_id", "default")

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")
        print(f"[STREAM] Question: {question}")



        config = {"configurable": {"thread_id": session_id}}
        human_message = HumanMessage(content=question)

        initial_state = {
            "messages": [human_message],
            "remaining_steps": 10
        }
        # Track all streamed messages for post-run artifact extraction
        stream_messages = [human_message]

        try:
            
            # Ensure async graph is ready (normally pre-initialized at FastAPI startup)
            if getattr(self, "chat_qa_bot_async", None) is None:
                await self.setup_async_streaming()

            # -------------------------------------------------------------
            reset_tool_outputs()
            final_text = ""  # accumulate assistant text to persist at the end

            # Prefer true token streaming using LangGraph event stream; fallback to message-level if unavailable
            did_stream_tokens = False
            try:
                async for ev in self.chat_qa_bot_async.astream_events(initial_state, config):
                    try:
                        stream_messages.append(ev)
                    except Exception:
                        pass

                    event_name = ev.get("event")
                    # Model token chunks
                    if event_name == "on_chat_model_stream":
                        chunk = ev.get("data", {}).get("chunk")
                        text = safe_get_text_from_message(chunk)
                        if text:
                            did_stream_tokens = True
                            final_text += text
                            # Best effort node name from metadata
                            node = ev.get("metadata", {}).get("langgraph_node") or ev.get("metadata", {}).get("node")
                            yield {"type": "token", "agent": node, "role": "assistant", "content": text}
            except Exception as _ev_err:
                # Fallback: message-level streaming
                async for token, metadata in self.chat_qa_bot_async.astream(initial_state, config, stream_mode="messages"):
                    text = safe_get_text_from_message(token)
                    node = None
                    try:
                        node = metadata.get("langgraph_node") or metadata.get("node") or metadata.get("source")
                    except Exception:
                        node = None
                    try:
                        stream_messages.append(token)
                    except Exception:
                        pass

                    if not isinstance(token, (AIMessage, AIMessageChunk)):
                        continue
                    if text:
                        did_stream_tokens = True
                        final_text += text
                        yield {"type": "token", "agent": node, "role": "assistant", "content": text}


            # If no token events were emitted, fallback to message-level streaming
            if not did_stream_tokens:
                async for token, metadata in self.chat_qa_bot_async.astream(initial_state, config, stream_mode="messages"):
                    text = safe_get_text_from_message(token)
                    node = None
                    try:
                        node = metadata.get("langgraph_node") or metadata.get("node") or metadata.get("source")
                    except Exception:
                        node = None
                    try:
                        stream_messages.append(token)
                    except Exception:
                        pass

                    if not isinstance(token, (AIMessage, AIMessageChunk)):
                        continue
                    if text:
                        final_text += text
                        yield {"type": "token", "agent": node, "role": "assistant", "content": text}

            # NOTE: We rely on the AsyncSqliteSaver-backed graph for persistence.
            # No manual update_state() here to avoid duplicating checkpoints/messages.

  
        
            try:
                source_details = get_tool_outputs()
                print("source_details: ", source_details)
            except Exception as _e1:
                source_details = []


            print("-----------------")
            print("stream_messages: ", stream_messages)
            print("-----------------")
            print("source_details: ", source_details)
            print("-----------------")
            print("answer: ", final_text)
            print("-----------------")

            yield {
                "type": "done",
                "session_id": session_id,
                "answer": final_text,
                "source_details": source_details,
                "source": source_details,
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error in stream:\n{tb_str}")
            yield {"type": "error", "error": str(e), "session_id": session_id}
