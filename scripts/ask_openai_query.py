#!/usr/bin/env python3
"""Send a one-off query to an OpenAI model using OPENAI_API_KEY."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_key_from_dotenv(dotenv_path: Path) -> str | None:
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
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key.strip()

    project_root = Path(__file__).resolve().parents[1]
    return _load_key_from_dotenv(project_root / ".env")


def ask_openai(prompt: str, model: str, api_key: str, timeout_seconds: int = 60) -> str:
    payload = {
        "model": model,
        "input": prompt,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = body.get("output_text")
        if text:
            return text

        # Compatibility path for responses that provide text under output[].content[].text
        output = body.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        txt = part.get("text")
                        if isinstance(txt, str) and txt.strip():
                            chunks.append(txt)
            if chunks:
                return "\n".join(chunks)

        return json.dumps(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask one query to OpenAI")
    parser.add_argument("prompt", help="Prompt to send")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model name (default: gpt-4o)")
    args = parser.parse_args()

    api_key = get_openai_api_key()
    if not api_key:
        print("OPENAI_API_KEY not found in environment or .env file.")
        return 2

    try:
        answer = ask_openai(args.prompt, args.model, api_key)
        print(answer)
        return 0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {detail}")
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
