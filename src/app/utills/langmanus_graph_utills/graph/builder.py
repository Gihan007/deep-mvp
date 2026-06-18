from langgraph.graph import StateGraph, START

from .types import State
from .nodes import (
    supervisor_node,
    coder_node,
    coordinator_node,
    reporter_node,
    planner_node,
    researcher_node,
    visualization_node
)


def build_graph():
    """Build and return the agent workflow graph."""
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator_agent")

    # Coordination and planning
    builder.add_node("coordinator_agent", coordinator_node)
    builder.add_node("planner_agent", planner_node)
    builder.add_node("supervisor_agent", supervisor_node)

    # Core agents
    builder.add_node("coder_agent", coder_node)
    builder.add_node("reporter_agent", reporter_node)
    builder.add_node("researcher_agent", researcher_node)
    builder.add_node("visualization_agent", visualization_node)

    return builder
