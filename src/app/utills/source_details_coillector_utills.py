
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage ,AIMessageChunk
from typing import List, Optional, Dict, Any, Annotated
import json
import re
from pathlib import Path
import traceback
from typing import List, Dict, Any
import os
import base64


FIG_PLACEHOLDER_RE = re.compile(r"^\[fig_description-(.+?)\]\s*$")


def images_to_base64(images_data):
        """
        Convert image paths to base64 and keep their descriptions.
        Args:
            images_data: List of dicts: 
                [{"image_path": "...", "description": "..."}]
        Returns:
            List of dicts:
                [{"image_base64": "...", "description": "..."}]
        """
        results = []
        for item in images_data:
            image_path = item.get("image_path")
            description = item.get("description", "")
            if not image_path:
                results.append({"image_base64": None,"description": description})
                continue
            try:
                with open(image_path, "rb") as image_file:
                    image_data = image_file.read()
                    base64_encoded = base64.b64encode(image_data).decode("utf-8")
                results.append({"image_base64": base64_encoded,"description": description})
            except FileNotFoundError:
                print(f"Warning: File not found - {image_path}")
                results.append({"image_base64": None,"description": description})

            except Exception as e:
                print(f"Error processing {image_path}: {str(e)}")
                results.append({"image_base64": None,"description": description})
        return results


def extract_images_from_source_details(source_details: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build images_data list from source_details entries.
    Handles both:
      - visualization_tool: expects tool_output to be an image path string and description in input_arguments
      - visualization_tool returning dict: if tool_output is a dict-like string with image_path/description/status
    Each entry includes:
      - image_path: absolute path string
      - description: optional description
    """
    images: List[Dict[str, str]] = []
    try:
        for item in (source_details or []):
            if not isinstance(item, dict):
                continue
            if item.get("tool_name") != "visualization_tool":
                continue

            tool_output = item.get("tool_output")
            image_path: str = ""
            description: str = ""

            # Case A: tool_output is already a path string (current tool implementation)
            if isinstance(tool_output, str) and tool_output:
                image_path = tool_output
                args = item.get("input_arguments") or {}
                description = args.get("description", "") or ""

            # Case B: tool_output may be a dict-like string (legacy/fallback)
            # Try to parse minimal structure to recover image_path/description
            if (not image_path) and isinstance(tool_output, str):
                try:
                    parsed = None
                    try:
                        parsed = json.loads(tool_output)
                    except json.JSONDecodeError:
                        import ast
                        parsed = ast.literal_eval(tool_output)
                    if isinstance(parsed, dict):
                        # Accept either 'image_path' or nested keys
                        candidate = parsed.get("image_path") or parsed.get("path") or ""
                        if isinstance(candidate, str):
                            image_path = candidate
                        description = parsed.get("description", "") or description
                except Exception:
                    # ignore parsing failures
                    pass

            if image_path:
                images.append({"image_path": image_path, "description": description})
    except Exception:
        # fail soft: return what was collected so far
        pass
    return images


def strip_unmatched_fig_placeholders(markdown_text: str, images_data: List[Dict[str, str]]) -> str:
    """Remove fig_description placeholders that do not have a matching generated image.

    This protects against cases where the LLM emits placeholders but never actually
    calls `visualization_tool`.

    Matching rule:
    - Keep a placeholder line only if its description matches one of the
      `images_data[*]['description']` values exactly.
    """
    if not markdown_text:
        return markdown_text

    allowed = set()
    try:
        for item in images_data or []:
            desc = (item or {}).get("description")
            if not (isinstance(desc, str) and desc.strip()):
                continue

            # Only treat an image as "generated" if we can actually access it.
            img_path = (item or {}).get("image_path")
            ok = False
            try:
                if isinstance(img_path, str) and img_path:
                    ok = os.path.exists(img_path)
            except Exception:
                ok = False

            if ok:
                allowed.add(desc.strip())
    except Exception:
        allowed = set()

    out_lines: List[str] = []
    for line in markdown_text.splitlines(True):
        m = FIG_PLACEHOLDER_RE.match(line.strip())
        if m:
            desc = m.group(1).strip()
            if desc in allowed:
                out_lines.append(line)
            else:
                # drop unmatched placeholder
                continue
        else:
            out_lines.append(line)

    return "".join(out_lines)
