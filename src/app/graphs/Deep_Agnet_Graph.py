import sqlite3
import traceback
from typing import Any, AsyncGenerator, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage 
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from app.utills.source_details_coillector_utills import images_to_base64, extract_images_from_source_details, strip_unmatched_fig_placeholders
from app.utills.tool_output_collector import reset_tool_outputs, get_tool_outputs
import base64
#from langsmith import traceable
from app.utills.markdown_pdf_base64_converter import create_pdf_from_markdown
from app.utills.media_content_handdler import MediaContentMixin
from app.utills.message_utils import safe_get_text_from_message

from app.utills.logging_config import configure_graph_logging
configure_graph_logging(__name__)
import logging
logger = logging.getLogger(__name__)
for _neo_logger_name in ("neo4j", "neo4j.io", "neo4j.pool"):
    logging.getLogger(_neo_logger_name).setLevel(logging.WARNING)




class DAG_ChatQABot:
    """
    Langmanus Graph chatbot (consolidated).
    - Compiles the graph with a persistent SQLite checkpointer so chat history is saved
    - Implements run() and stream() compatible with existing routes
    - Uses thread_id (session_id) to scope conversation history
    """

    def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store):
        # Keep signature for Get-Deep app wiring, but we manage our own graph compilation
        self.llm = llm
        self.config = config
        self.graphdb_vector_store = graphdb_vector_store
        self.chromadb_vector_store = chromadb_vector_store

        # Load graph builder and TEAM_MEMBERS from global config
        from app.utills.langmanus_graph_utills.graph.builder import build_graph
        # Filter team members to the nodes that actually exist in the graph.
        # This prevents prompting the supervisor with workers that cannot be routed to.
        from app.utills.langmanus_graph_utills.graph.types import TEAM_MEMBERS

        self.TEAM_MEMBERS = TEAM_MEMBERS

        # Create persistent SQLite checkpointer
        self.db_path = getattr(self.config, "SESSION_DATABASE_PATH", "session_checkpoints.sqlite")
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.memory = SqliteSaver(conn)
            print(f"[Langmanus_Graph] SQLite checkpointer at: {self.db_path}")
        except Exception as e:
            print(f"[Langmanus_Graph] Failed to create SQLite checkpointer ({e}); falling back to MemorySaver")
            self.memory = MemorySaver()

        # Keep base graph builder so we can compile an async (AsyncSqliteSaver) graph lazily for streaming
        self._base_graph = build_graph()
        self.chat_qa_bot = self._base_graph.compile(checkpointer=self.memory)
        self.async_memory = None
        self.chat_qa_bot_async = None


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
        if self.chat_qa_bot_async is not None:
            return
        self.async_memory = await self._create_async_checkpointer(self.db_path)
        self.chat_qa_bot_async = self._base_graph.compile(checkpointer=self.async_memory)





    
   
    #------------------------------ Non Stream ----------------------------
    #@traceable(name="CM_ChatQABot.run",metadata={"component": "chatbot", "entrypoint": "run"})
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:

        question = input_data.get("question", "")
        path_images = input_data.get("path_images", [])
        path_files = input_data.get("path_files", [])
        path_audios = input_data.get("path_audios", [])
        session_id = input_data.get("session_id", "default")
        report_requred = bool(input_data.get("report_requred", False))
        logger.debug(
            "[Langmanus_Graph.run] input: session_id=%s, q_len=%d, images=%d, files=%d, audios=%d",
            session_id, len(question or ""), len(path_images or []), len(path_files or []), len(path_audios or [])
        )

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")
        print(f"Question: {question}")

        # CHANGE THIS: Create proper initial state using HumanMessage
        media_content_messages = MediaContentMixin._add_media_content_to_messages(self, path_images, path_files, path_audios)
        config = {"configurable": {"thread_id": session_id}}
        if media_content_messages:
            human_message = HumanMessage(content=[{"type": "text", "text": question}] + media_content_messages)
        else:
            human_message = HumanMessage(content=question)

        initial_state = {
            "TEAM_MEMBERS": self.TEAM_MEMBERS,
            "messages": [human_message],
        }

        if not question.strip():
            return {
                "answer": "I'm sorry, I couldn't generate a response to this question.",
                "session_id": session_id,
                "source_details": None,
                "output_images_data": [],
                "base64_images": [],
            }

        try:
            reset_tool_outputs()
            result = self.chat_qa_bot.invoke(initial_state, config)
            # Extract last assistant-ish message
            messages = result.get("messages", [])
            # Debug logging instead of writing to file
            logger.debug(f"Messages result: {messages}")


            source_details = get_tool_outputs()
            images_data = extract_images_from_source_details(source_details)
            base64_images = images_to_base64(images_data)
            


            try:
                print("[Langmanus_Graph.run] Message types:", [getattr(m, "__class__", type(m)).__name__ for m in messages])
                print("[Langmanus_Graph.run] Message names:", [getattr(m, "name", None) for m in messages])
            except Exception as _e:
                print(f"[Langmanus_Graph.run] Debug print failed: {_e}")
            answer_text = ""
            if isinstance(messages, list) and messages:
                answer_text = safe_get_text_from_message(messages[-1])

            answer_text = answer_text.strip() or "I'm sorry, I couldn't generate a response to this question."

            # Remove fig placeholders that don't have a matching visualization_tool output
            answer_text = strip_unmatched_fig_placeholders(answer_text, images_data)

            report_base64 = ""
            if report_requred:
                report_base64 = create_pdf_from_markdown(answer_text, base64_images=base64_images)


            # print("-----------------")
            # print("messages: ", messages)
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
            tb = traceback.format_exc()
            raise RuntimeError(f"Langmanus run failed: {e}\n{tb}") from e




    #------------------------------ Stream ----------------------------
    #@traceable(name="CM_ChatQABot.stream",metadata={"component": "chatbot", "entrypoint": "stream"})
    async def stream(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream assistant tokens as the graph runs. We:
          - Persist the human message to the persistent (SQLite) graph
          - Stream tokens from the async graph compiled with MemorySaver
          - On completion, persist the final AI message back to the persistent graph
        Yields:
          {"type": "token", "content": "..."}
          {"type": "done", "session_id": "...", "answer": "..."}
          {"type": "error", "error": "...", "session_id": "..."}
        """

        question = input_data.get("question", "")
        path_images = input_data.get("path_images", [])
        path_files = input_data.get("path_files", [])
        path_audios = input_data.get("path_audios", [])
        session_id = input_data.get("session_id", "default")
        report_requred = bool(input_data.get("report_requred", False))
        logger.debug(
            "[Langmanus_Graph.stream] input: session_id=%s, q_len=%d, images=%d, files=%d, audios=%d",
            session_id, len(question or ""), len(path_images or []), len(path_files or []), len(path_audios or [])
        )

        if not question.strip():
            yield {"type": "error", "error": "Question is required", "session_id": session_id}
            return

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")
        print(f"[STREAM] Question: {question}")

        media_content_messages = MediaContentMixin._add_media_content_to_messages(self, path_images, path_files, path_audios)
        config = {"configurable": {"thread_id": session_id}}
        if media_content_messages:
            human_message = HumanMessage(content=[{"type": "text", "text": question}] + media_content_messages)
        else:
            human_message = HumanMessage(content=question)

        initial_state = {
            "TEAM_MEMBERS": self.TEAM_MEMBERS,
            "messages": [human_message],
        }
        # Track all streamed messages for post-run artifact extraction
        stream_messages = [human_message]

        # Ensure async graph is ready (normally pre-initialized at FastAPI startup)
        if self.chat_qa_bot_async is None:
            await self.setup_async_streaming()


        reset_tool_outputs()
        final_text = ""
        try:
            # Stream message chunks from async-compiled graph
            async for token, metadata in self.chat_qa_bot_async.astream(initial_state, config, stream_mode="messages"):
                # Extract text
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
                # Stream reporter output preserving newlines as-is (line-by-line)
                if isinstance(token, AIMessage) and node == "reporter_agent":
                    final_text = text or ""
                    try:
                        # Filter ghost placeholders during streaming as well.
                        source_details_now = get_tool_outputs()
                        images_data_now = extract_images_from_source_details(source_details_now)
                        for line in final_text.splitlines(True):  # keep line endings
                            if line.strip().startswith("[fig_description-"):
                                filtered = strip_unmatched_fig_placeholders(line, images_data_now)
                                if filtered:
                                    yield {"type": "token", "content": filtered}
                            else:
                                yield {"type": "token", "content": line}
                    except Exception:
                        pass
            
            ################### -----------AFtre loop Done -------------- ########################
            # Determine final assistant text: prefer reporter's AIMessage, else last AIMessage
            if not (final_text and final_text.strip()):
                try:
                    # Prefer the reporter agent's message
                    for _m in reversed(stream_messages):
                        if isinstance(_m, AIMessage) and getattr(_m, "name", None) == "reporter_agent":
                            final_text = safe_get_text_from_message(_m) or ""
                            if final_text.strip():
                                break
                    # Fallback to the last AIMessage if reporter not found
                    if not (final_text and final_text.strip()):
                        for _m in reversed(stream_messages):
                            if isinstance(_m, AIMessage):
                                final_text = safe_get_text_from_message(_m) or ""
                                if final_text.strip():
                                    break
                except Exception:
                    pass

                
            # NOTE: We rely on the AsyncSqliteSaver-backed graph for persistence.
            # No manual update_state() here to avoid duplicating checkpoints/messages.

            # Collect source details and images from streamed messages
            try:
                source_details = get_tool_outputs()
            except Exception as _e1:
                source_details = []
            images_paths = []
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
            try:
                report_base64 = ""
                if report_requred:
                    report_base64 = create_pdf_from_markdown(final_text, base64_images=base64_images)
            except Exception as _e3:
                report_base64 = ""

            # print("-----------------")
            # print("stream_messages: ", stream_messages)
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
                "report_base64": report_base64,
            }

        except Exception as e:
            tb = traceback.format_exc()
            yield {
                "type": "error",
                "error": f"Langmanus stream failed: {e}\n{tb}",
                "session_id": session_id,
            }





"""

=============================  Non stream messages  =============================


================================ stream messages  =============================


"""
