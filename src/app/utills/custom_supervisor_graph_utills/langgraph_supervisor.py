
from enum import Enum
from pydantic import BaseModel, Field, create_model
from langgraph.graph import END
from langgraph.types import Command
import logging

logger = logging.getLogger(__name__)


class SupervisorNode():
    def __init__(self, llm, base_instructions: str, agents_name: list):
        # Store for dynamic evaluation each invocation
        self.base_instructions = base_instructions
        self.agents_name = agents_name
        self.llm = llm
        self.OptionsType = agents_name + ["FINISH"]   # v Creates list of allowed next options , Supervisor can route to any agent or FINISH.

        # Dynamically create an Enum of allowed next values
        enum_members = {}
        for name in self.OptionsType:
            enum_members[name] = name
        NextEnum = Enum(
            "NextEnum",
            enum_members
        )
        
        # Build a Pydantic model dynamically to avoid forward-ref issues
        self.Router = create_model("Router",next=(NextEnum, Field(description="Next agent to route to")),)
    
    def system_prompt(self, members: str, base_instructions: str):
        system_prompt = (
            "You are a supervisor tasked with managing a conversation between the"
            f" following workers: {members}. Given the following user request,"
            " respond with the worker to act next. Each worker will perform a"
            " task and respond with their results and status. When finished,"
            " respond with FINISH."
            f"{base_instructions}"
            ""
        )
        return system_prompt

    def _extract_next_from_text(self, text: str):
        text_lower = text.lower() if isinstance(text, str) else str(text).lower()
        for name in self.OptionsType:
            if name.lower() in text_lower:
                return name
        return "FINISH"
        
    def supervisor_node(self, state):
        # Rebuild system prompt per invocation to allow dynamic base_instructions (e.g., real-time CURRENT_TIME)
        base_str = self.base_instructions() if callable(self.base_instructions) else self.base_instructions
        system_message = self.system_prompt(", ".join(self.agents_name), base_str)
        messages = [{"role": "system", "content": system_message},] + state["messages"]
        try:
            resp = self.llm.with_structured_output(self.Router).invoke(messages)     # resp = { "next": "CodingAgent" }
            # Handle Pydantic v2 BaseModel instance or dict
            if isinstance(resp, BaseModel):
                goto = resp.next
            elif isinstance(resp, dict):
                goto = resp.get("next")
            else:
                goto = getattr(resp, "next", None)
        except Exception:
            # Fallback: call the LLM without structured output and parse a route name from text
            raw = self.llm.invoke(messages)
            text = getattr(raw, "content", str(raw))
            goto = self._extract_next_from_text(text)

        # Normalize Enum to string if necessary
        if isinstance(goto, Enum):
            goto = goto.value
        # Coerce to string and validate against allowed options
        if not isinstance(goto, str):
            goto = str(goto) if goto is not None else "FINISH"
        if goto not in self.OptionsType:
            goto = "FINISH"
        if goto == "FINISH":
            goto = END
        try:
            logger.debug("[SupervisorNode] Routing to: %s", goto if goto != END else "END")
        except Exception:
            pass
        return Command(goto=goto)
