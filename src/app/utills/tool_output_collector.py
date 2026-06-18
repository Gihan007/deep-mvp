"""
A lightweight global collector for tool outputs within a single graph invocation.

Design:
- Uses contextvars to keep outputs isolated per invoke/context.
- Tools call add_tool_output({...}) just before returning.
- The graph runner (Custom_Supervisor_Graph) should call reset_tool_outputs() before starting an invoke/stream.
- Read collected outputs at the end using get_tool_outputs().

Note: This assumes one logical invocation per context. If you fan out to parallel contexts,
contextvars will keep isolation as long as the context is preserved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import contextvars

_tool_outputs_var: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    "tool_outputs", default=None
)


def reset_tool_outputs() -> None:
    """
    Reset the collector for a new graph invoke/stream.
    """
    _tool_outputs_var.set([])


def add_tool_output(entry: Dict[str, Any]) -> None:
    """
    Append a single tool output record to the current collector.
    If the collector was not initialized, initialize it lazily.
    """
    lst = _tool_outputs_var.get()
    if lst is None:
        lst = []
    lst.append(entry)
    _tool_outputs_var.set(lst)


def get_tool_outputs() -> List[Dict[str, Any]]:
    """
    Get all collected tool outputs for the current context.
    Returns an empty list if nothing was collected.
    """
    lst = _tool_outputs_var.get()
    return list(lst) if isinstance(lst, List) else []
