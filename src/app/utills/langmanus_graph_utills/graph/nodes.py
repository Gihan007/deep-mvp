import logging
import json
import re
from typing import Literal
from langchain_core.messages import AIMessage
from langgraph.types import Command

from ..agents import (
    coder_agent,
    researcher_agent,
    visualization_agent
)
from ..agents.llm import get_llm_by_type
from config import get_config
# Filter TEAM_MEMBERS to supported nodes only to avoid edges to unknown nodes.
# Keep in sync with `graph/types.py` and `graph/builder.py`.
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
from ..agents.agent_map import AGENT_LLM_MAP
from app.prompts.markdown import apply_prompt_template
from .types import State, Router
logger = logging.getLogger(__name__)

RESPONSE_FORMAT = "{1}"




def coordinator_node(state: State) -> Command[Literal["planner_agent", "__end__"]]:
    """Coordinator node that communicates with customers."""
    logger.info("Coordinator talking.")
    messages = apply_prompt_template("coordinator_agent", state)
    response = get_llm_by_type(AGENT_LLM_MAP["coordinator"]).invoke(messages)
    #logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"coordinator response: {response}")

    goto = "__end__"
    if "handoff_to_planner" in response.content:
        goto = "planner_agent"

    return Command(goto=goto,)





def planner_node(state: State) -> Command[Literal["supervisor_agent", "__end__"]]:
    """Planner node that generates the full plan."""
    logger.info("Planner generating full plan")
    messages = apply_prompt_template("planner_agent", state)

    llm = get_llm_by_type("basic")
    stream = llm.stream(messages)
    full_response = ""
    for chunk in stream:
        full_response += chunk.content
    #logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"Planner response: {full_response}")
    
    # Sanitize common code fences and extraneous text before JSON parsing
    resp = full_response.strip()
    if resp.startswith("```"):
        nl = resp.find("\n")
        if nl != -1:
            resp = resp[nl + 1 :]
        if resp.endswith("```"):
            resp = resp[:-3].rstrip()

    # Prefer extracting object assigned to a const/let/var (e.g., const plan: Plan = { ... })
    candidate = resp
    m = re.search(r"(?:const|let|var)\s+\w+\s*:?[^{=]*=\s*(\{[\s\S]*\})", resp)
    if m:
        candidate = m.group(1).strip()
    elif not (candidate.startswith("{") and candidate.endswith("}")):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = candidate[start : end + 1].strip()

    goto = "supervisor_agent"
    try:
        # Attempt strict JSON parse first
        json.loads(candidate)
        full_response = candidate
    except json.JSONDecodeError:
        # Try to clean common JSON-like issues (e.g., trailing commas)
        cleaned = re.sub(r',(\s*[}\]])', r'\1', candidate)
        try:
            json.loads(cleaned)
            full_response = cleaned
        except json.JSONDecodeError:
            logger.warning("Planner response is not a valid JSON; continuing with raw plan text")
            # Continue workflow with the raw (sanitized) planner content instead of ending
            full_response = resp
            # keep goto as 'supervisor_agent'

    return Command(
        update={
            "messages": state["messages"] + [AIMessage(content=full_response, name="planner_agent")],
            "full_plan": full_response,
        },
        goto=goto,
    )





def supervisor_node(state: State) -> Command[Literal[*TEAM_MEMBERS, "__end__"]]:
    """Supervisor node that decides which agent should act next."""
    logger.info("Supervisor evaluating next action")
    # We keep the plan (`full_plan`) in state for context, but the supervisor
    # does not enforce or verify step-by-step compliance.
    messages = apply_prompt_template("supervisor_agent", state)
    response = (get_llm_by_type(AGENT_LLM_MAP["supervisor"]).with_structured_output(Router).invoke(messages))
    goto = response["next"]
    logger.debug(f"Supervisor response: {response}")

    if goto == "FINISH":
        goto = "__end__"
        logger.info("Workflow completed")
    else:
        if goto not in TEAM_MEMBERS:
            logger.warning(f"Unknown agent '{goto}', defaulting to researcher_agent")
            goto = "researcher_agent"
        logger.info(f"Supervisor delegating to: {goto}")

    return Command(goto=goto,update={"next": goto,},)






def researcher_node(state: State) -> Command[Literal["supervisor_agent"]]:
    """Researcher node.

    Intentionally simple: invoke the researcher agent once and hand control back
    to the supervisor. Any plan/tooling decisions should be made by the supervisor
    + agent prompts, not by hard-coded enforcement here.
    """
    logger.info("Researcher agent starting task")
    result = researcher_agent.invoke(state)
    logger.info("Researcher agent completed task")
    logger.debug(f"Researcher agent response: {result['messages'][-1].content}")
    return Command(
        update={
            "messages": result["messages"] + 
                        [AIMessage(content=RESPONSE_FORMAT.format("researcher_agent",result["messages"][-1].content,),name="researcher_agent",)]
        },
        goto="supervisor_agent",
    )



def coder_node(state: State) -> Command[Literal["supervisor_agent"]]:
    """Node for the coder agent that executes Python/Bash."""
    logger.info("Code agent starting task")
    result = coder_agent.invoke(state)
    logger.info("Code agent completed task")
    logger.debug(f"Code agent response: {result['messages'][-1].content}")
    return Command(
        update={
            "messages": result["messages"] + 
                        [AIMessage(content=RESPONSE_FORMAT.format("coder_agent", result["messages"][-1].content),name="coder_agent",)]},
        goto="supervisor_agent",
    )





def visualization_node(state: State) -> Command[Literal["supervisor_agent"]]:
    """Visualization node (charts/images)."""
    logger.info("Visualization agent starting task")
    result = visualization_agent.invoke(state)
    logger.info("Visualization agent completed task")
    logger.debug(f"Visualization agent response: {result['messages'][-1].content}")
    return Command(
        update={
            "messages": result["messages"] + 
                        [AIMessage(content=RESPONSE_FORMAT.format("visualization_agent", result["messages"][-1].content),name="visualization_agent",)]},
        goto="supervisor_agent",
    )





def reporter_node(state: State) -> Command[Literal["__end__"]]:
    """Reporter node that writes the final report."""
    logger.info("Reporter write final report")
    messages = apply_prompt_template("reporter_agent", state)
    response = get_llm_by_type(AGENT_LLM_MAP["reporter"]).invoke(messages)
    #logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"reporter response: {response}")

    return Command(
        update={
            "messages": state["messages"] + 
                        [AIMessage(content=RESPONSE_FORMAT.format("reporter_agent", response.content),name="reporter_agent",)]},
        goto="__end__",
    )
