"""Self-contained FastAPI entry point used by the Windows desktop bundle."""

from __future__ import annotations

import os

import uvicorn

from app.main import app


def main() -> None:
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("ARIS_BACKEND_PORT", "8002")),
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
