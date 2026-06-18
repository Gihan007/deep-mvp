import logging
from typing import Optional
from langchain_openai import ChatOpenAI

from config import get_config
from .agent_map import LLMType


cfg = get_config()


def create_openai_llm(
    model: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    **kwargs,
) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance with the specified configuration
    """
    # Only include base_url in the arguments if it's not None or empty
    llm_kwargs = {"model": model, "temperature": temperature, **kwargs}

    if base_url:  # This will handle None or empty string
        llm_kwargs["base_url"] = base_url

    if api_key:  # This will handle None or empty string
        llm_kwargs["api_key"] = api_key

    return ChatOpenAI(**llm_kwargs)


def maybe_enable_parallel_tool_calls(model: ChatOpenAI) -> ChatOpenAI:
    """Enable OpenAI parallel tool calls when supported.

    This allows the model to emit multiple tool_calls in a single turn.
    LangGraph's ToolNode can then execute those tool calls concurrently.

    Note: This does not *force* parallelism; prompts should encourage batching.
    """
    try:
        return model.bind(parallel_tool_calls=True)
    except Exception:
        return model


# Cache for plain LLM instances (NO tool-related kwargs)
_llm_cache: dict[LLMType, ChatOpenAI] = {}

# Cache for tool-enabled LLM instances (safe to use only when tools are passed)
_tool_llm_cache: dict[LLMType, ChatOpenAI] = {}


def get_llm_by_type(llm_type: LLMType) -> ChatOpenAI :
    """
    Get LLM instance by type. Returns cached instance if available.
    """
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]

    if llm_type == "reasoning":
        llm = create_openai_llm(model=cfg.REASONING_MODEL,base_url=cfg.REASONING_BASE_URL,api_key=cfg.REASONING_API_KEY)
    elif llm_type == "basic":
        llm = create_openai_llm(model=cfg.BASIC_MODEL,base_url=cfg.BASIC_BASE_URL,api_key=cfg.BASIC_API_KEY)
    elif llm_type == "vision":
        llm = create_openai_llm(model=cfg.VL_MODEL,base_url=cfg.VL_BASE_URL,api_key=cfg.VL_API_KEY)
    else:
        raise ValueError(f"Unknown LLM type: {llm_type}")

    _llm_cache[llm_type] = llm
    return llm


def get_tool_llm_by_type(llm_type: LLMType) -> ChatOpenAI:
    """Return an LLM configured for tool-using agents.

    IMPORTANT: The returned runnable passes `parallel_tool_calls=True` to OpenAI.
    OpenAI only allows this when the request includes tools, so this MUST ONLY be
    used in contexts where tools are provided (e.g., create_react_agent with tools).
    """
    if llm_type in _tool_llm_cache:
        return _tool_llm_cache[llm_type]

    base = get_llm_by_type(llm_type)
    tool_llm = maybe_enable_parallel_tool_calls(base)
    _tool_llm_cache[llm_type] = tool_llm
    return tool_llm
