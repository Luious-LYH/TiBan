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
# Tests that exercise the bounded runtime use the deterministic local gateway;
# external-provider acceptance remains an explicit, separately invoked smoke.
# This prevents a developer's private backend/.env from making regression
# tests wait on a LAN gateway or accidentally consume provider quota.
os.environ.setdefault("TUTOR_PROVIDER_ENABLED", "false")

from app.db.bootstrap import initialize_database


def pytest_sessionstart() -> None:
    initialize_database()
