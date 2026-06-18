#!/usr/bin/env python3
"""Small utility to check whether OPENAI_API_KEY is valid."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_key_from_dotenv(dotenv_path: Path) -> str | None:
    """Read OPENAI_API_KEY from a .env file, tolerating spaces around '='."""
    if not dotenv_path.exists():
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        if name.strip() != "OPENAI_API_KEY":
            continue

        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None

    return None


def get_openai_api_key() -> str | None:
    """Get key from environment first, then .env in project root."""
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    project_root = Path(__file__).resolve().parents[1]
    return _load_key_from_dotenv(project_root / ".env")


def check_openai_api_key(api_key: str, timeout_seconds: int = 15) -> tuple[bool, str]:
    """Validate key by calling OpenAI models endpoint."""
    req = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
            first_model = None
            if isinstance(payload, dict) and isinstance(payload.get("data"), list) and payload["data"]:
                first = payload["data"][0]
                if isinstance(first, dict):
                    first_model = first.get("id")

            model_info = f" First model: {first_model}" if first_model else ""
            return True, f"API key is valid. HTTP {resp.status}.{model_info}"

    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = ""

        if exc.code == 401:
            return False, "API key is invalid (401 Unauthorized)."
        if exc.code == 429:
            return False, "API key recognized but rate-limited or quota-limited (429)."

        detail = f"HTTP {exc.code}"
        if error_body:
            detail = f"{detail} | {error_body}"
        return False, f"Request failed: {detail}"

    except urllib.error.URLError as exc:
        return False, f"Network error while contacting OpenAI: {exc.reason}"

    except json.JSONDecodeError:
        return False, "Received a non-JSON response from OpenAI."


if __name__ == "__main__":
    key = get_openai_api_key()
    if not key:
        print("OPENAI_API_KEY not found in environment or .env file.")
        sys.exit(2)

    ok, message = check_openai_api_key(key)
    print(message)
    sys.exit(0 if ok else 1)
