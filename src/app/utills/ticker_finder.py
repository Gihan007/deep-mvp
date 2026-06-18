"""ticker_finder.py

Goal
----
Turn a user's natural-language screen (e.g. "healthcare companies with market cap >= 10B")
into a READ-ONLY Cypher query, execute it using the existing Neo4j tool
`graph_db_cypher_query_tool`, and return ONLY the ticker list.

Notes
-----
- This is intentionally schema-flexible: you can update the SYSTEM_PROMPT section later
  once you finalize your graph schema.
- The tool used for execution is:
    src/app/tools/graph_db_cypher_query_tool.py
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# Allow running this file directly for quick testing:
#   python3 src/app/utills/ticker_finder.py
# by ensuring `src/` is on PYTHONPATH so `import app...` works.
# _SRC_DIR = Path(__file__).resolve().parents[2]
# if str(_SRC_DIR) not in sys.path:
#     sys.path.insert(0, str(_SRC_DIR))

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

from app.prompts.markdown import get_prompt_template

# IMPORTANT: Use the project's existing tool for Cypher execution.
from app.tools.graph_db_cypher_query_tool import graph_db_cypher_query_tool


SYSTEM_PROMPT = get_prompt_template("ticker_finder").strip()


def _build_llm(*, model: str, temperature: float) -> ChatOpenAI:
    """Create a ChatOpenAI instance using the project's Config when available.

    Notes:
    - The project exposes OPENAI_API_KEY via `src/config.py` (loaded from .env).
    - langchain_openai also reads OPENAI_API_KEY from the environment automatically,
      but we pass it explicitly here to align with the project's config pattern.
    """
    api_key = None
    try:
        # `src/config.py`
        from config import get_config  # type: ignore

        cfg = get_config()
        api_key = getattr(cfg, "OPENAI_API_KEY", None)
    except Exception:
        api_key = None

    if api_key:
        return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)

    # Fallback: rely on environment variables / default LangChain behavior
    return ChatOpenAI(model=model, temperature=temperature)


def _bind_tools_required(llm: ChatOpenAI):
    """Bind tools in a way that forces tool calling when supported."""
    try:
        # Newer langchain-openai versions support tool_choice="required".
        return llm.bind_tools([graph_db_cypher_query_tool], tool_choice="required")
    except TypeError:
        # Backwards-compatible fallback.
        return llm.bind_tools([graph_db_cypher_query_tool])


def _extract_tickers_from_tool_output(tool_output: str) -> List[str]:
    """Parse graph_db_cypher_query_tool output (stringified python list of dicts) -> ticker list."""
    if not tool_output:
        return []

    s = str(tool_output).strip()
    if s.lower().startswith("error") or "error" in s.lower():
        return []
    if "no results" in s.lower():
        return []

    # Tool returns `str(result)` where result is usually `List[Dict[str, Any]]`.
    # This string uses single quotes, so json.loads may fail; ast.literal_eval is safer here.
    rows: Any = None
    try:
        rows = ast.literal_eval(s)
    except Exception:
        # Some Neo4j drivers stringify differently; try json as fallback.
        try:
            rows = json.loads(s)
        except Exception:
            return []

    if not isinstance(rows, list):
        return []

    out: List[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        t = r.get("ticker")
        if t is None:
            continue
        t = str(t).upper().strip()
        if t and t not in out:
            out.append(t)
    return out


def find_tickers(user_query: str, *, model: str = "gpt-4o-mini", temperature: float = 0) -> List[str]:
    """Return tickers matching the user's query.

    This:
      1) Uses an LLM to translate the natural language into a Cypher query (via tool call).
      2) Executes the query via `graph_db_cypher_query_tool`.
      3) Extracts and returns ONLY the tickers list.
    """
    llm = _build_llm(model=model, temperature=temperature)
    llm_with_tools = _bind_tools_required(llm)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{input}"),
        ]
    )

    # First call: force tool call containing Cypher.
    messages = prompt.format_messages(input=user_query)
    ai: AIMessage = llm_with_tools.invoke(messages)  # type: ignore[assignment]

    tool_calls = getattr(ai, "tool_calls", None) or []
    if not tool_calls:
        # If the model didn't tool-call, treat this as no tickers.
        # (You can also re-try with a stricter prompt if you want.)
        return []

    # Execute tool calls (we expect exactly one)
    tickers: List[str] = []
    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("args") or {}
        call_id = tc.get("id")

        if name != graph_db_cypher_query_tool.name:
            continue

        # `graph_db_cypher_query_tool` is a LangChain tool, so we can call `.invoke`.
        tool_result = graph_db_cypher_query_tool.invoke(args)
        tickers = _extract_tickers_from_tool_output(str(tool_result))

        # Keep the transcript (optional): if you later want a 2nd LLM pass to format output.
        if call_id:
            messages.append(ToolMessage(content=str(tool_result), tool_call_id=call_id))

    return tickers


if __name__ == "__main__":
    # Example
    q = "companies in the Discount Stores industry"
    print(find_tickers(q))


