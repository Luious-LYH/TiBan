"""Shared clean-checkout test initialization.

The application normally creates its local schema during FastAPI startup.  A
few service-level tests intentionally exercise persistence without starting an
HTTP client, so make the same local bootstrap explicit for every pytest run.
"""

from app.db.bootstrap import initialize_database


def pytest_sessionstart() -> None:
    initialize_database()
