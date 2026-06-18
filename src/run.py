# path: src/run.py

import uvicorn
import logging
import os
from app import create_app

# Suppress HTTPX/OpenAI client INFO logs (OpenAI SDK uses httpx under the hood)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

app = create_app()

if __name__ == '__main__':
    # Dev/prod toggle: default to NO reload in production containers.
    # Enable with UVICORN_RELOAD=1 (or true/yes/on).
    reload_env = os.getenv("UVICORN_RELOAD", "0").strip().lower()
    reload_enabled = reload_env in ("1", "true", "yes", "y", "on")

    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=8080,
        reload=reload_enabled,
        # Only watch code directories; exclude DBs and generated artifacts to prevent reload during requests
        reload_dirs=["src/app", "src"],
        reload_excludes=[
            "src/databases/*",
            "src/databases/**",
            "src/temp_charts/*",
            "src/temp_charts/**",
            "data/*",
            "data/**",
            "*.db",
            "*.db-shm",
            "*.db-wal",
            "*.sqlite3*",
            "*.pdf",
            "*.png",
        ],
    )