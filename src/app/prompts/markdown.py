import os
import re
from datetime import datetime
from typing import Dict, Any, List

from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt.chat_agent_executor import AgentState

# Shared markdown prompts directory for ALL architectures
SHARED_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "md")


def _strip_frontmatter(text: str) -> str:
    """
    Remove YAML-style frontmatter delimited by --- ... --- at the top of the file.
    This prevents PromptTemplate from seeing dangling placeholders inside frontmatter.
    """
    s = text.lstrip()
    if s.startswith("---"):
        # Find the closing '---' after the first line
        parts = s.split("\n", 1)
        if len(parts) == 2:
            rest = parts[1]
            end_idx = rest.find("\n---")
            if end_idx != -1:
                # Skip everything up to the closing delimiter line
                after = rest[end_idx + len("\n---") :]
                # Preserve original leading whitespace before the frontmatter
                prefix_len = len(text) - len(s)
                return text[:prefix_len] + after.lstrip("\n")
    return text


def get_prompt_template(prompt_name: str) -> str:
    """
    Load the markdown template for a given prompt name from the shared prompts folder.
    Supports placeholder conversion:
      - Escapes curly braces {}
      - Replaces <<VAR>> with {VAR}
      - Strips YAML frontmatter (--- ... ---) if present
    """
    path = os.path.join(SHARED_PROMPTS_DIR, f"{prompt_name}.md")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt markdown not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        template = f.read()

    # Strip YAML frontmatter (e.g., CURRENT_TIME header block)
    template = _strip_frontmatter(template)

    # Escape existing curly braces to avoid unintended formatting
    template = template.replace("{", "{{").replace("}", "}}")
    # Only convert CURRENT_TIME placeholder to {CURRENT_TIME}
    template = re.sub(r"<<\s*CURRENT_TIME\s*>>", "{CURRENT_TIME}", template)
    return template


def apply_prompt_template(prompt_name: str, state: AgentState) -> List[Dict[str, Any]]:
    """
    Formats the prompt as a system message using CURRENT_TIME and expands known custom tokens.
    Returns a list of messages: system prompt followed by historical messages.
    - We only allow CURRENT_TIME through PromptTemplate to avoid KeyError from accidental braces.
    - We manually expand <<TEAM_MEMBERS>> using state if present.
    """
    tmpl = get_prompt_template(prompt_name)

    # Expand custom inline tokens safely (do not route via PromptTemplate)
    team = state.get("TEAM_MEMBERS", [])
    team_str = ", ".join(team) if isinstance(team, list) else str(team or "")
    tmpl = tmpl.replace("<<TEAM_MEMBERS>>", team_str)

    system_prompt = PromptTemplate(
        input_variables=["CURRENT_TIME"],
        template=tmpl,
    ).format(CURRENT_TIME=datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"))

    return [{"role": "system", "content": system_prompt}] + state["messages"]
