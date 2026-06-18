from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import MessagesState

from config import get_config

# IMPORTANT:
# The graph only defines these nodes. We filter config.TEAM_MEMBERS to avoid
# routing to non-existent nodes (which would create invalid edges / runtime fallbacks).
SUPPORTED_NODES = [
    "coordinator_agent",
    "planner_agent",
    "supervisor_agent",
    "coder_agent",
    "researcher_agent",
    "visualization_agent",
    "reporter_agent",
]

TEAM_MEMBERS = [m for m in get_config().TEAM_MEMBERS if m in SUPPORTED_NODES]

# Define routing options
OPTIONS = TEAM_MEMBERS + ["FINISH"]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""
    next: Literal[*OPTIONS]


class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Constants
    TEAM_MEMBERS: list[str]

    # Runtime Variables
    next: str
    full_plan: str
