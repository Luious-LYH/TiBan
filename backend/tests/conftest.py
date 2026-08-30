"""Shared clean-checkout test initialization.

The application normally creates its local schema during FastAPI startup.  A
few service-level tests intentionally exercise persistence without starting an
HTTP client, so make the same local bootstrap explicit for every pytest run.
"""

import os

# RAG has its own deterministic retrieval/benchmark coverage. Tutor contract
# tests use question provenance and must not require an optional Qdrant service
# or model-cache download just to exercise permissions and SSE ordering.
os.environ.setdefault("TUTOR_RETRIEVAL_ENABLED", "false")

from app.db.bootstrap import initialize_database


def pytest_sessionstart() -> None:
    initialize_database()
