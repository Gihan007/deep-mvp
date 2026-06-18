from typing import Literal

# Define available LLM types for this graph
LLMType = Literal["basic", "reasoning", "vision"]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "basic",   # coordinator uses basic llm
    "planner": "basic",   # planner can use reasoning llm (fallback to basic if creds missing)
    "supervisor": "basic",    # supervisor uses basic llm
    "coder": "basic",         # programming tasks use basic llm
    "reporter": "basic",      # report writing uses basic llm
    "visualization": "basic",
    "researcher": "basic",     # reasoning
}
