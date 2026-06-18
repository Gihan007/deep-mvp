# File: graphs/LangGraph_Supervisor_Graph.py

from langgraph_supervisor import create_supervisor

from langgraph.prebuilt import create_react_agent
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
import base64
from datetime import datetime

from app.prompts.prompts import General_QA_Agent_Prompt, Supervisor_Prompt
from app.prompts.markdown import get_prompt_template
from langchain_core.prompts import PromptTemplate

# Import the tool initialization system
from app.tools import initialize_all_tools
from typing import List, Optional, Dict, Any, Annotated
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict
from app.utills.media_content_handdler import MediaContentMixin
import traceback
import re
from langgraph.prebuilt import ToolNode
from app.utills.source_details_coillector_utills import images_to_base64, extract_images_from_source_details
from app.utills.tool_output_collector import reset_tool_outputs, get_tool_outputs
from app.utills.custom_supervisor_graph_utills.langgraph_agents import AgentNode
from app.utills.custom_supervisor_graph_utills.langgraph_supervisor import SupervisorNode
from app.utills.custom_supervisor_graph_utills.langgraph_agent_router import AgentRouter
from langgraph.graph import END, START, StateGraph
from app.utills.message_utils import safe_get_text_from_message


from app.utills.logging_config import configure_graph_logging
configure_graph_logging(__name__)
import logging
logger = logging.getLogger(__name__)
for _neo_logger_name in ("neo4j", "neo4j.io", "neo4j.pool"):
    logging.getLogger(_neo_logger_name).setLevel(logging.WARNING)

    
# ADD THIS: Define proper state schema for conversation tracking
class GAG_GraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]  # This enables conversation history
    sender: Optional[str]

class GAG_ChatQABot:

    def __init__(self, llm, config, graphdb_vector_store, chromadb_vector_store):
        self.llm = llm
        self.graphdb_vector_store = graphdb_vector_store
        self.chromadb_vector_store = chromadb_vector_store
        self.config = config

        self.db_path = self.config.SESSION_DATABASE_PATH

        # Initialize all tools
        self.tools = initialize_all_tools(graphdb_vector_store, chromadb_vector_store , llm, config)
        self._organize_tools()
        self.chat_qa_bot = self.create_graph()

    def _user_facing_policy(self) -> str:
        """
        Global instruction to prevent leaking internal implementation (queries, tool calls)
        into user-visible answers unless explicitly requested by the user.
        """
        return (
            "\n\nIMPORTANT RESPONSE POLICY (USER-FACING):\n"
            "- Do NOT include Cypher queries, code blocks, tool names (e.g., graph_db_*), or function-call arguments in answers.\n"
            "- Only provide the final answer, concise reasoning, and optionally a small table of key results.\n"
            "- If and only if the user explicitly asks to see queries or debug steps, you may include them. Otherwise, never expose them.\n"
        )
    
    
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
        # Get tools by name for easy access
        tool_dict = {tool.name: tool for tool in self.tools}

        # GraphDB tools
        self.graphdb_structured_data_tools = []
        if 'graph_db_strctured_data_cypher_query_tool' in tool_dict:
            self.graphdb_structured_data_tools.append(tool_dict['graph_db_strctured_data_cypher_query_tool'])

        # GraphDB tools
        self.graphdb_tenk_data_tools = []
        if 'graph_db_tenk_data_cypher_query_tool' in tool_dict:
            self.graphdb_tenk_data_tools.append(tool_dict['graph_db_tenk_data_cypher_query_tool'])
        

        # Web search tools
        self.web_search_tools = []
        if 'duckduckgo_search_tool' in tool_dict:
            self.web_search_tools.append(tool_dict['duckduckgo_search_tool'])

        # Visualization tools
        self.visualization_tools = []
        if 'visualization_tool' in tool_dict:
            self.visualization_tools.append(tool_dict['visualization_tool'])

        # Alphavantage tools
        self.alphavantage_tools = []
        if 'alphavantage_company_overview_tool' in tool_dict:
            self.alphavantage_tools.append(tool_dict['alphavantage_company_overview_tool'])
        if 'alphavantage_earnings_call_transcript_tool' in tool_dict:
            self.alphavantage_tools.append(tool_dict['alphavantage_earnings_call_transcript_tool'])
        if 'alphavantage_market_news_and_sentiment_tool' in tool_dict:
            self.alphavantage_tools.append(tool_dict['alphavantage_market_news_and_sentiment_tool'])
        if 'alphavantage_daily_stock_tool' in tool_dict:
            self.alphavantage_tools.append(tool_dict['alphavantage_daily_stock_tool'])

        # coder tools
        self.coder_tools = []
        if 'python_repl_tool' in tool_dict:
            self.coder_tools.append(tool_dict['python_repl_tool'])

        # Investment factor ranking agent toolsh_Agent.
        self.investment_factor_ranking_tools = []
        if 'investment_factor_ranking_table_tool' in tool_dict:
            self.investment_factor_ranking_tools.append(tool_dict['investment_factor_ranking_table_tool'])
        if 'investment_metrics_calculator_tool' in tool_dict:
            self.investment_factor_ranking_tools.append(tool_dict['investment_metrics_calculator_tool'])




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


    def _get_current_date_context(self):
        """Generate current date context string for agents."""
        now = datetime.now()
        current_year = now.year
        
        date_context = f"""

        **CRITICAL TEMPORAL CONTEXT - READ CAREFULLY:**
        - Current Date: {now.strftime('%B %d, %Y')}
        - Current Year: {current_year}

        **STRICT RULES FOR TEMPORAL QUERIES:**
        1. "current year" or "this year" = {current_year} ONLY
        2. "last year" or "previous year" = {current_year - 1} ONLY
        3. "last 3 years" (WITHOUT "including current") = {current_year-1}, {current_year-2}, {current_year-3}
        4. "last 3 years including current year" = {current_year}, {current_year-1}, {current_year-2}
        5. "over the last 3 years" = {current_year-1}, {current_year-2}, {current_year-3}
        6. When in doubt about range queries, "last X years" means PREVIOUS X COMPLETED years, NOT including {current_year}

        **EXAMPLES:**
        - Q: "Revenue in last 3 years?" → Answer: {current_year-1}, {current_year-2}, {current_year-3}
        - Q: "Revenue over last 3 years?" → Answer: {current_year-1}, {current_year-2}, {current_year-3}
        - Q: "Revenue for last 3 years including current?" → Answer: {current_year}, {current_year-1}, {current_year-2}
        - Q: "Revenue in current year?" → Answer: {current_year} only
        - Q: "Last year's revenue?" → Answer: {current_year-1} only

        **ALWAYS use these exact year ranges. Never deviate.**
        """
        return date_context
    

    def create_graph(self):
 
        # Create checkpointer
        self.memory = self._create_checkpointer(self.db_path)

        # Helper to format shared markdown prompts into a system message string (as a callable)
        def _fmt_md_fn(name: str, extra=None):
            def _make():
                tmpl = PromptTemplate(input_variables=["CURRENT_TIME"], template=get_prompt_template(name))
                sys_str = tmpl.format(CURRENT_TIME=datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S %z"))
                extra_str = extra() if callable(extra) else (extra or "")
                return sys_str + extra_str
            return _make


        GraphDB_Structured_Data_Search_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.graphdb_structured_data_tools,
            system_message=_fmt_md_fn("graphdb_structured_data_search_agent", lambda: self._user_facing_policy() + self._get_current_date_context()),
            agent_name="graphDB_structured_data_search_agent"
        ).agent_node

        GraphDB_TENK_Data_Search_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.graphdb_tenk_data_tools,
            system_message=_fmt_md_fn("graphdb_tenK_data_search_agent", lambda: self._user_facing_policy() + self._get_current_date_context()),
            agent_name="graphDB_tenK_data_search_agent"
        ).agent_node

        Web_Search_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.web_search_tools,
            system_message=_fmt_md_fn("web_search_agent", self._get_current_date_context),
            agent_name="web_search_agent"
        ).agent_node


        Visualization_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.visualization_tools,
            system_message=_fmt_md_fn("visualization_agent", self._get_current_date_context),
            agent_name="visualization_agent"
        ).agent_node

        AlphaVantage_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.alphavantage_tools,
            system_message=_fmt_md_fn("alphavantage_agent", self._get_current_date_context),
            agent_name="alphavantage_agent"
        ).agent_node      

        General_QA_Agent = AgentNode(
            llm=self.llm,
            agent_tools=None,
            system_message= General_QA_Agent_Prompt + self._get_current_date_context(),
            agent_name="general_qa_agent"
        ).agent_node 

        Coder_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.coder_tools,
            system_message=_fmt_md_fn("coder_agent", self._get_current_date_context),
            agent_name="coder_agent"
        ).agent_node            


        Investment_Factor_Ranking_Agent = AgentNode(
            llm=self.llm,
            agent_tools=self.investment_factor_ranking_tools,
            system_message=_fmt_md_fn(
                "investment_factor_ranking_agent",
                lambda: self._user_facing_policy() + self._get_current_date_context(),
            ),
            agent_name="investment_factor_ranking_agent"
        ).agent_node

        Supervisor = SupervisorNode(
            llm=self.llm,
            base_instructions=_fmt_md_fn("custom_supervisor_agent", self._get_current_date_context),
            agents_name=[
                "graphDB_structured_data_search_agent",
                "graphDB_tenK_data_search_agent",
                "web_search_agent",
                "coder_agent",
                "visualization_agent",
                "alphavantage_agent",
                "investment_factor_ranking_agent",
                "general_qa_agent",
            ]
        ).supervisor_node        # OUTPUTS: END , agent_name




        All_tools = (
            self.graphdb_structured_data_tools +
            self.graphdb_tenk_data_tools +
            self.web_search_tools +
            self.visualization_tools +
            self.alphavantage_tools +
            self.coder_tools +
            self.investment_factor_ranking_tools
        )

        tool_node = ToolNode(All_tools)
        agent_router = AgentRouter(ends="true").agent_router   # OUTPUTS: tool_calls , continue, END

        builder = StateGraph(GAG_GraphState)

        builder.add_edge(START, "supervisor")

        builder.add_node("supervisor", Supervisor)
        builder.add_node("graphDB_structured_data_search_agent", GraphDB_Structured_Data_Search_Agent)
        builder.add_node("graphDB_tenK_data_search_agent", GraphDB_TENK_Data_Search_Agent)
        builder.add_node("web_search_agent", Web_Search_Agent)
        builder.add_node("visualization_agent", Visualization_Agent)
        builder.add_node("alphavantage_agent", AlphaVantage_Agent)
        builder.add_node("coder_agent", Coder_Agent)
        builder.add_node("investment_factor_ranking_agent", Investment_Factor_Ranking_Agent)
        builder.add_node("general_qa_agent", General_QA_Agent)
        builder.add_node("Tool_Node", tool_node)


        builder.add_conditional_edges("graphDB_structured_data_search_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("graphDB_tenK_data_search_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("web_search_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("alphavantage_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("general_qa_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("visualization_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("coder_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)
        builder.add_conditional_edges("investment_factor_ranking_agent",agent_router,{"continue": "supervisor", "call_tool": "Tool_Node", END: END},)


        builder.add_conditional_edges("Tool_Node",lambda x: x["sender"],
            {
                "graphDB_structured_data_search_agent": "graphDB_structured_data_search_agent",
                "graphDB_tenK_data_search_agent": "graphDB_tenK_data_search_agent",
                "web_search_agent": "web_search_agent",
                "visualization_agent": "visualization_agent",
                "alphavantage_agent": "alphavantage_agent",
                "coder_agent": "coder_agent",
                "investment_factor_ranking_agent": "investment_factor_ranking_agent",
                "general_qa_agent": "general_qa_agent",
            },
        )
        
        # Keep builder so we can compile an async (AsyncSqliteSaver) graph lazily for streaming.
        self._builder = builder

        compiled_graph_sql = builder.compile(checkpointer=self.memory)
        self._save_workflow_diagram(compiled_graph_sql)
        return compiled_graph_sql
        


    #@traceable(name="CS_ChatQABot.run",metadata={"component": "chatbot", "entrypoint": "run"})
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:

        question = input_data.get("question", "")
        path_images = input_data.get("path_images", [])
        path_files = input_data.get("path_files", [])
        path_audios = input_data.get("path_audios", [])
        session_id = input_data.get("session_id", "default")

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")
        print(f"Question: {question}")

        # CHANGE THIS: Create proper initial state using HumanMessage
        media_content_messages = MediaContentMixin._add_media_content_to_messages(self, path_images, path_files, path_audios)
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        if media_content_messages:
            human_message = HumanMessage(content=[{"type": "text", "text": question}] + media_content_messages)
        else:
            human_message = HumanMessage(content=question)

        initial_state = {
            "messages": [human_message],  # This will be added to conversation history
            "remaining_steps": 10,        # Required by create_react_agent (max steps before stopping)
        }

        try:
            # Run the graph - it will now maintain conversation history
            reset_tool_outputs()
            response = self.chat_qa_bot.invoke(initial_state, config)
            messages = response["messages"]
            last_ai_index = None
            for i in reversed(range(len(messages))):
                if isinstance(messages[i], AIMessage):
                    last_ai_index = i
                    break
            last_ai_message = messages[last_ai_index] if last_ai_index is not None else None

       
            source_details = get_tool_outputs()
            images_data = extract_images_from_source_details(source_details)
            base64_images = images_to_base64(images_data)
            answer = safe_get_text_from_message(last_ai_message)

    
            # print("-----------------")
            # print("messages: ", messages)
            # print("-----------------")
            # print("source_details: ", source_details)
            # print("-----------------")
            # print("images_data: ", images_data)
            # print("-----------------")
            # print("last_ai_message: ", last_ai_message)
            # print("-----------------")
            # print("answer: ", answer)
            # print("-----------------")
 

            return {
                "answer": answer,      
                "session_id": session_id,
                "source_details": source_details,
                "base64_images": base64_images
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error in _add_media_content_to_messages:\n{tb_str}")
            raise



    #@traceable(name="CS_ChatQABot.stream",metadata={"component": "chatbot", "entrypoint": "stream"})
    async def stream(self, input_data: dict):
        """
        Async generator that streams tokens per-agent as the graph executes.
        Yields dict events shaped like:
          {"type": "token", "agent": "graphDB_search_agent", "role": "assistant", "content": "...partial..."}
          {"type": "done", "session_id": "..."}
          {"type": "error", "error": "...", "session_id": "..."}
        """
        question = input_data.get("question", "")
        path_images = input_data.get("path_images", [])
        path_files = input_data.get("path_files", [])
        path_audios = input_data.get("path_audios", [])
        session_id = input_data.get("session_id", "default")

        print("")
        print("=========================================================================+===========")
        print(f"============================== Session: {session_id} ================================")
        print(f"[STREAM] Question: {question}")

        media_content_messages = MediaContentMixin._add_media_content_to_messages(self, path_images, path_files, path_audios)
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        if media_content_messages:
            human_message = HumanMessage(content=[{"type": "text", "text": question}] + media_content_messages)
        else:
            human_message = HumanMessage(content=question)

        initial_state = {"messages": [human_message],"remaining_steps": 10}
        # Track all streamed messages for post-run artifact extraction
        stream_messages = [human_message]

        try:

            # Ensure async graph is ready (normally pre-initialized at FastAPI startup)
            if getattr(self, "chat_qa_bot_async", None) is None:
                await self.setup_async_streaming()
            # NOTE: We rely on the AsyncSqliteSaver-backed graph for persistence.
            # No manual update_state() here to avoid duplicating checkpoints/messages.


            # -------------------------------------------------------------
            reset_tool_outputs()
            final_text = ""  # accumulate assistant text to persist at the end

            # Stream messages/token chunks from the graph (AsyncSqliteSaver-backed)
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
                    yield {"type": "token","agent": node,"role": "assistant","content": text}



            # NOTE: We rely on the AsyncSqliteSaver-backed graph for persistence.
            # No manual update_state() here to avoid duplicating checkpoints/messages.


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


                
            # print("-----------------")
            # print("stream_messages: ", stream_messages)
            # print("-----------------")
            # print("source_details: ", source_details)
            # print("-----------------")
            # print("images_data: ", images_data)
            # print("-----------------")
            # print("answer: ", final_text)
            # print("-----------------")

            yield {
                "type": "done",
                "session_id": session_id,
                "answer": final_text,
                "source_details": source_details,
                "output_images_data": images_data,
                "base64_images": base64_images
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error in stream:\n{tb_str}")
            yield {"type": "error", "error": str(e), "session_id": session_id}





"""


=============================  Non stream messages  =============================





[HumanMessage(content='What was Walmart’s  Revenue Growth Rate over the last 5 years?', 
             additional_kwargs={}, 
             response_metadata={}, 
             id='b452c851-8d48-4c1f-82d9-4da660d24a54'), 
             
AIMessage(content='', 
          additional_kwargs={'tool_calls': [{'id': 'call_o0wVPl5C9PxsfXaeMDf0zRpS', 'function': {'arguments': '{"query":"MATCH (c:Company {ticker: \'WMT\'})-[:HAS_METRIC]->(m:Metric {metricName: \'RevenueGrowthRate\'}) RETURN m.financial_data"}', 'name': 'graph_db_strctured_data_cypher_query_tool'}, 'type': 'function'}], 'refusal': None}, 
          response_metadata={'token_usage': {'completion_tokens': 58, 'prompt_tokens': 3589, 'total_tokens': 3647, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}, 'model_name': 'gpt-4o-mini-2024-07-18', 'system_fingerprint': 'fp_560af6e559', 'id': 'chatcmpl-CdIsgfzG5tq71Hgh1MjPOCdnhbbV4', 'service_tier': 'default', 'finish_reason': 'tool_calls', 'logprobs': None}, 
          name='graphDB_structured_data_search_agent', id='run--2daaa369-c506-4ac4-a029-023c57069a22-0', 
          tool_calls=[{'name': 'graph_db_strctured_data_cypher_query_tool', 'args': {'query': "MATCH (c:Company {ticker: 'WMT'})-[:HAS_METRIC]->(m:Metric {metricName: 'RevenueGrowthRate'}) RETURN m.financial_data"}, 'id': 'call_o0wVPl5C9PxsfXaeMDf0zRpS', 'type': 'tool_call'}], 
          usage_metadata={'input_tokens': 3589, 'output_tokens': 58, 'total_tokens': 3647, 'input_token_details': {'audio': 0, 'cache_read': 0}, 'output_token_details': {'audio': 0, 'reasoning': 0}}), 
          
ToolMessage(content='[{\'m.financial_data\': \'{"2020": 1.8582634305654104, "2021": 6.7155377086975445, "2022": 2.432795434506958, "2023": 6.728019359096575, "2024": 6.025954990192854, "2025": 5.514341853698388, "2026": 5.568303869954122, "2027": 5.622265886209857, "2028": 5.676227902465592, "2029": 5.730189918721326, "2030": 5.784151934977061, "2031": 5.838113951232796, "2032": 5.89207596748853, "2033": 5.946037983744265, "2034": 6.0, "2035": 6.053962016255735}\'}]', 
            name='graph_db_strctured_data_cypher_query_tool', id='286e864e-229a-417f-b4d1-430abe986e74', 
            tool_call_id='call_o0wVPl5C9PxsfXaeMDf0zRpS'), 
            
AIMessage(content='### Walmart Revenue Growth Rate Over the Last 5 Years\n\nThe Revenue Growth Rate for Walmart over the last five years was as follows:\n\n- **2020:** 1.86%\n- **2021:** 6.72%\n- **2022:** 2.43%\n- **2023:** 6.73%\n- **2024:** 6.03%\n\nThis data reflects a trend of fluctuating growth, with significant increases in 2021 and 2023. \n\nIf you need further information or insights, feel free to ask!', 
          additional_kwargs={'refusal': None}, 
          response_metadata={'token_usage': {'completion_tokens': 114, 'prompt_tokens': 3887, 'total_tokens': 4001, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 3456}}, 'model_name': 'gpt-4o-mini-2024-07-18', 'system_fingerprint': 'fp_560af6e559', 'id': 'chatcmpl-CdIsikz4C9Zw6ybVbYufNCElCM2lW', 'service_tier': 'default', 'finish_reason': 'stop', 'logprobs': None}, 
          name='graphDB_structured_data_search_agent', 
          id='run--0a617d43-1039-49d3-bfd4-0a7a835818e5-0', 
          usage_metadata={'input_tokens': 3887, 'output_tokens': 114, 'total_tokens': 4001, 'input_token_details': {'audio': 0, 'cache_read': 3456}, 'output_token_details': {'audio': 0, 'reasoning': 0}})]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
 

============================= Stream messages  =============================

Why not reuse the same SQLite checkpointer for streaming?

*** High write frequency during streaming:
  - Token-by-token or node-by-node updates cause many small writes. 
  - With SQLite this leads to “database is locked” contention and noticeable latency spikes under concurrency.
*** Event loop blocking:
  - sqlite3 is synchronous; frequent disk I/O from the async generator can block the loop and slow down streaming responsiveness.
*** Overhead vs value:
  - Most intermediate streaming states are transient. 
  - Persisting them adds I/O without much user-facing value when you already persist the initial and final messages.
*** Reliability:
  - If a user cancels the stream, you avoid partial/half-written checkpoints scattered across steps.


"""
