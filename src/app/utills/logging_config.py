"""
Centralized logging setup for graph modules.

Usage in any graph file (e.g., app/graphs/Langmanus_Graph.py):
    from app.utills.logging_config import configure_graph_logging
    configure_graph_logging(__name__)

Behavior:
- Reads DEBUG_ENABLE and LOG_LEVEL from config.get_config()
- Prints logs to terminal using StreamHandler
- Shows DEBUG logs only for `app.graphs` package (Langmanus_Graph.py and peers)
- Keeps global/root logging at LOG_LEVEL (defaults to INFO), minimizing noise
- Reduces third-party library noise when DEBUG_ENABLE is false
"""
from __future__ import annotations

import logging


def _ensure_root_handler(level: int) -> None:
    """Ensure a single root StreamHandler exists with the given level."""
    root = logging.getLogger()
    # If no handlers on root, attach one StreamHandler
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")
        )
        root.addHandler(handler)
    # Always set root level to at least INFO or the provided level
    root.setLevel(level)


def configure_graph_logging(target_logger_name: str | None = None) -> None:
    """
    Configure logging such that:
    - Root logs to terminal with LOG_LEVEL (INFO by default)
    - `app.graphs` logger (and all its children) emit DEBUG when DEBUG_ENABLE is true,
      without making the entire app noisy.
    """
    try:
        from config import get_config  # local import to avoid import cycles
        cfg = get_config()
    except Exception:
        cfg = None

    debug_enable = bool(getattr(cfg, "DEBUG_ENABLE", False)) if cfg else False
    level_name = getattr(cfg, "LOG_LEVEL", "INFO") if cfg else "INFO"
    global_level = getattr(logging, level_name.upper(), logging.INFO)

    # Keep global at configured level (default INFO) and ensure a terminal handler exists
    _ensure_root_handler(global_level)

    logger_name = target_logger_name or "app.graphs"
    target_logger = logging.getLogger(logger_name)

    # When DEBUG is enabled, attach a dedicated DEBUG handler to app.graphs
    # so only graph modules print debug details; do not spam the whole app.
    if debug_enable:
        # If no handler on app.graphs, add one at DEBUG
        if not target_logger.handlers:
            h = logging.StreamHandler()
            h.setLevel(logging.DEBUG)
            h.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")
            )
            target_logger.addHandler(h)
        target_logger.setLevel(logging.DEBUG)
        # Stop propagating to root to avoid duplicate lines
        target_logger.propagate = False
    else:
        # When not debugging, remove any dedicated handlers and let it use root settings
        for h in list(target_logger.handlers):
            target_logger.removeHandler(h)
        target_logger.setLevel(global_level)
        target_logger.propagate = True

        # Reduce noise from common external libraries when not debugging
        for noisy in ("httpx", "urllib3", "neo4j", "openai"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
