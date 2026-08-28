from __future__ import annotations

from .database import Base, SessionLocal, engine
from .models import (  # noqa: F401
    AttemptModel,
    PracticeSessionModel,
    QuestionBankModel,
    QuestionModel,
    ReviewCardModel,
    SourceDocumentModel,
    DocumentVersionModel,
    KnowledgeChunkModel,
    LearnerMasteryModel,
    FactoryJobModel,
    QuestionRevisionModel,
    EvalDatasetModel,
    EvalDatasetVersionModel,
    EvalRunModel,
    EvalCaseModel,
    EvalArtifactModel,
)
from .seed import seed_database


def initialize_database() -> int:
    """Create the local schema and idempotently seed the catalog.

    Alembic owns production schema history.  ``create_all`` is intentionally kept
    as a small local-dev bootstrap so the existing FastAPI TestClient and a fresh
    checkout can start without a separate migration command.
    """

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        return seed_database(session)
