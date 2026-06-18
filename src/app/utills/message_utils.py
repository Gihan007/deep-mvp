"""Utility functions for message handling across different graph implementations."""
from typing import List, Any


def safe_get_text_from_message(msg: Any) -> str:
    """
    Robustly extract text from a variety of message shapes:
    - LangChain BaseMessage (has .content)
    - dict with {'content': ...}
    - list of content parts [{'text': '...'}, ...]
    - plain string
    """
    try:
        content = getattr(msg, "content", msg)
    except Exception:
        content = msg

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()

    if isinstance(content, dict):
        c = content.get("content")
        if isinstance(c, str):
            return c
        try:
            return str(c) if c is not None else ""
        except Exception:
            return ""

    try:
        return str(content) if content is not None else ""
    except Exception:
        return ""
