import sys
import logging
from langchain_core.messages import BaseMessage
from langgraph.graph import END

logger = logging.getLogger(__name__)


class AgentRouter:
    def __init__(self, e=None, ends="true"):
        self.ends = ends

    def agent_router(self, state):
        try:
            messages = state["messages"]
            last_message = messages[-1]

            # Check if the last message has tool_calls (OpenAI/LC may store in different places)
            has_direct_tool_calls = getattr(last_message, "tool_calls", None)
            has_additional_tool_calls = (
                hasattr(last_message, "additional_kwargs")
                and isinstance(last_message.additional_kwargs, dict)
                and last_message.additional_kwargs.get("tool_calls")
            )
            if has_direct_tool_calls or has_additional_tool_calls:
                try:
                    logger.debug("[AgentRouter] Decision=call_tool (tool_calls present) sender=%s", getattr(last_message, "name", None))
                except Exception:
                    pass
                return "call_tool"

            # Gracefully end when the General QA agent produces a natural answer
            try:
                sender_name = getattr(last_message, "name", None)
                content_text = last_message.content if isinstance(getattr(last_message, "content", ""), str) else ""
            except Exception:
                sender_name, content_text = None, ""
            state_sender = None
            try:
                state_sender = state.get("sender")
            except Exception:
                state_sender = None
            if (sender_name == "general_qa_agent" or state_sender == "general_qa_agent") and content_text.strip():
                # No tool calls and we have an answer from the general agent → finish
                if self.ends == "true":
                    try:
                        logger.debug("[AgentRouter] Decision=END (general_qa_agent produced natural answer)")
                    except Exception:
                        pass
                    return END

            # Check for end markers (be strict to avoid premature termination)
            if isinstance(last_message, BaseMessage):
                content = last_message.content if isinstance(last_message.content, str) else ""
                content_upper = content.upper() if isinstance(content, str) else ""
                # End only on explicit "FINAL ANSWER" or clarifying "STOP:" prefix
                if "FINAL ANSWER" in content_upper or content_upper.strip().startswith("STOP:"):
                    if self.ends == "true":
                        try:
                            logger.debug("[AgentRouter] Decision=END (explicit end marker detected)")
                        except Exception:
                            pass
                        return END

            try:
                logger.debug("[AgentRouter] Decision=continue")
            except Exception:
                pass
            return "continue"

        except Exception as ex:
            exception = "AN EXCEPTION OCCURRED IN {filename} AND FUNC {method}() AT {line_no}: {ex}".format(
                filename="ai_agent_workflow_routes.py",
                method="agent_router",
                line_no=sys.exc_info()[2].tb_lineno,
                ex=ex,
            )
            raise Exception(exception)
