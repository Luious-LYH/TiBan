"""Shared clean-checkout test initialization.

The application normally creates its local schema during FastAPI startup.  A
few service-level tests intentionally exercise persistence without starting an
HTTP client, so make the same local bootstrap explicit for every pytest run.
"""

import os
import shutil
from pathlib import Path

# The live application deliberately uses ``runtime/data/stage1.sqlite3``.
# Keep service tests away from that file: otherwise a developer's test-only
# evaluation suites can become the newest record in the learner-facing lab.
_runtime_data_dir = Path(__file__).resolve().parents[1] / "runtime" / "data"
_live_db = _runtime_data_dir / "stage1.sqlite3"
_test_db = _runtime_data_dir / "pytest-stage1.sqlite3"
_test_db.unlink(missing_ok=True)
if _live_db.is_file():
    # Keep the current local catalog available to integration tests without
    # ever letting a test write sessions, suites, or results into the live
    # learner database that a running TiBan instance is serving.
    shutil.copy2(_live_db, _test_db)
os.environ["ENDO_DATABASE_URL"] = f"sqlite:///{_test_db.as_posix()}"

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
