from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app.core.config import DEMO_QBANK_BOOTSTRAP

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


DEMO_QBANK_EXPECTATIONS = {
    "bank-cmexam-real": 1500,
    "bank-cmb-exam-real": 1778,
    "bank-kvasir-vqa-curated": 400,
}


def demo_qbank_counts() -> dict[str, int]:
    """Return learner-ready counts for the three portfolio demo banks."""

    with SessionLocal() as session:
        rows = session.execute(
            select(QuestionModel.bank_id, func.count(QuestionModel.question_id))
            .where(QuestionModel.business_usage == "user_ready")
            .where(QuestionModel.bank_id.in_(DEMO_QBANK_EXPECTATIONS))
            .group_by(QuestionModel.bank_id)
        ).all()
    counts = {bank_id: 0 for bank_id in DEMO_QBANK_EXPECTATIONS}
    counts.update({str(bank_id): int(count) for bank_id, count in rows})
    return counts


def _require_demo_sources(missing: set[str]) -> None:
    """Fail loudly instead of serving a misleading legacy-only catalog."""

    from app.services.qbank_import_service import CMB_ROOT, CMEXAM_ROOT, LOCAL_VQA_ROOT

    required: dict[str, tuple[Path, ...]] = {
        "bank-cmexam-real": (CMEXAM_ROOT / "data" / "test_with_annotations.csv",),
        "bank-cmb-exam-real": (
            CMB_ROOT / "CMB-val" / "CMB-val-merge.json",
            CMB_ROOT / "CMB-train" / "CMB-train-merge.json",
        ),
        "bank-kvasir-vqa-curated": (LOCAL_VQA_ROOT / "Kvasir-VQA" / "Kvasir-VQA.json",),
    }
    unavailable = [
        str(path)
        for bank_id in missing
        for path in required[bank_id]
        if not path.is_file()
    ]
    if unavailable:
        raise RuntimeError(
            "Demo QBank bootstrap is enabled, but required local source files are missing: "
            + ", ".join(unavailable)
            + ". Mount code/data and configure ENDO_LOCAL_VQA_ROOT before starting the service."
        )


def bootstrap_demo_qbank() -> dict[str, object]:
    """Idempotently restore the approved 3,678-question portfolio QBank.

    Importers preserve existing rows and use stable source-derived IDs.  This
    function only fills missing inventory; it never deletes or replaces user
    data.  A source/configuration problem is raised rather than silently
    falling back to the small legacy teaching seed.
    """

    before = demo_qbank_counts()
    missing = {
        bank_id
        for bank_id, expected in DEMO_QBANK_EXPECTATIONS.items()
        if before[bank_id] < expected
    }
    if not missing:
        return {"imported": 0, "counts": before, "status": "complete"}

    _require_demo_sources(missing)
    from app.services.qbank_import_service import import_cmb, import_cmexam, import_kvasir

    importers = {
        "bank-cmexam-real": import_cmexam,
        "bank-cmb-exam-real": import_cmb,
        "bank-kvasir-vqa-curated": import_kvasir,
    }
    imported = 0
    for bank_id in ("bank-cmexam-real", "bank-cmb-exam-real", "bank-kvasir-vqa-curated"):
        if bank_id in missing:
            imported += int(importers[bank_id]())

    after = demo_qbank_counts()
    incomplete = {
        bank_id: {"expected": expected, "found": after[bank_id]}
        for bank_id, expected in DEMO_QBANK_EXPECTATIONS.items()
        if after[bank_id] < expected
    }
    if incomplete:
        raise RuntimeError(f"Demo QBank bootstrap did not reach its contract: {incomplete}")
    return {"imported": imported, "counts": after, "status": "complete"}


def initialize_database() -> int:
    """Create the local schema and idempotently seed the catalog.

    Alembic owns production schema history.  ``create_all`` is intentionally kept
    as a small local-dev bootstrap so the existing FastAPI TestClient and a fresh
    checkout can start without a separate migration command.
    """

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seeded = seed_database(session)
    if DEMO_QBANK_BOOTSTRAP:
        result = bootstrap_demo_qbank()
        return seeded + int(result["imported"])
    return seeded
