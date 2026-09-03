from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, inspect, select, text

from app.core.config import DEMO_QBANK_BOOTSTRAP, DESKTOP_CMEXAM_BUNDLE

from .database import Base, SessionLocal, engine
from .models import (  # noqa: F401
    AttemptModel,
    PracticeSessionModel,
    QuestionBankModel,
    QuestionModel,
    AgentConversationModel,
    AgentMessageModel,
    TutorThreadModel,
    TutorMessageModel,
    ReviewCardModel,
    SourceDocumentModel,
    DocumentVersionModel,
    KnowledgeChunkModel,
    LearnerMasteryModel,
    LearningMemoryItemModel,
    VectorIndexStateModel,
    BackgroundJobModel,
    FactoryJobModel,
    QuestionRevisionModel,
    EvalDatasetModel,
    EvalDatasetVersionModel,
    EvalRunModel,
    EvalCaseModel,
    EvalArtifactModel,
    EvalSuiteModel,
    EvalExperimentModel,
    EvalLabRunModel,
    EvalLabCaseModel,
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


def bootstrap_desktop_cmexam() -> dict[str, object]:
    """Populate the release-only desktop demo with the approved CMExam slice.

    The desktop bundle intentionally imports only CMExam.  It must not require
    the larger local CMB or Kvasir sources that are used by developer/acceptance
    environments, and it remains idempotent on every subsequent launch.
    """

    expected = DEMO_QBANK_EXPECTATIONS["bank-cmexam-real"]
    before = demo_qbank_counts()["bank-cmexam-real"]
    if before >= expected:
        return {"imported": 0, "counts": {"bank-cmexam-real": before}, "status": "complete"}

    from app.services.qbank_import_service import CMEXAM_ROOT, import_cmexam

    source_path = CMEXAM_ROOT / "data" / "test_with_annotations.csv"
    if not source_path.is_file():
        raise RuntimeError(
            "TiBan 桌面版缺少内置 CMExam 数据资源，请重新下载完整 Windows 发布包。"
        )
    imported = int(import_cmexam(limit=expected))
    after = demo_qbank_counts()["bank-cmexam-real"]
    if after < expected:
        raise RuntimeError(
            f"TiBan 桌面版 CMExam 数据未达到预期题量：expected={expected}, found={after}"
        )
    return {"imported": imported, "counts": {"bank-cmexam-real": after}, "status": "complete"}


def initialize_database() -> int:
    """Create the local schema and idempotently seed the catalog.

    Alembic owns production schema history.  ``create_all`` is intentionally kept
    as a small local-dev bootstrap so the existing FastAPI TestClient and a fresh
    checkout can start without a separate migration command.
    """

    Base.metadata.create_all(engine)
    _upgrade_local_sqlite_domain_scope()
    with SessionLocal() as session:
        seeded = seed_database(session)
    if DESKTOP_CMEXAM_BUNDLE:
        result = bootstrap_desktop_cmexam()
        return seeded + int(result["imported"])
    if DEMO_QBANK_BOOTSTRAP:
        result = bootstrap_demo_qbank()
        return seeded + int(result["imported"])
    return seeded


def _upgrade_local_sqlite_domain_scope() -> None:
    """Keep the opt-in SQLite developer fallback compatible with Stage 7.

    Production and Docker use the Alembic/PostgreSQL migration.  ``create_all``
    cannot alter an already-created SQLite table, though, which used to make a
    developer's harmless existing local database fail at startup as soon as a
    domain-scoped query touched it.  This narrowly scoped compatibility upgrade
    preserves all existing rows, assigns their established medical domain, and
    replaces only the two legacy unique keys that must now include ``domain``.
    It deliberately never drops user data.
    """

    if engine.dialect.name != "sqlite":
        return

    domain_tables = (
        "practice_sessions",
        "review_cards",
        "learner_mastery",
        "learning_memory_items",
        "eval_datasets",
    )
    with engine.begin() as connection:
        inspector = inspect(connection)
        _upgrade_local_sqlite_factory_jobs(connection, inspector)
        _upgrade_local_sqlite_knowledge_sources(connection, inspector)
        _upgrade_local_sqlite_v32_state(connection, inspector)
        for table_name in domain_tables:
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "domain_id" not in columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        "ADD COLUMN domain_id VARCHAR(100) NOT NULL DEFAULT 'endoscopy'"
                    )
                )

        _rebuild_sqlite_unique_scope(
            connection,
            "learner_mastery",
            "uq_mastery_learner_domain_point",
        )
        _rebuild_sqlite_unique_scope(
            connection,
            "learning_memory_items",
            "uq_learning_memory_learner_domain_dedupe",
        )
        # Stage 2.5 used ``medical-education`` as an internal catalog label.
        # Stage 7 promotes the stable public manifest id to ``endoscopy``.
        # This is a value migration only: bank/question/source identities and
        # all learner history remain untouched.
        for table_name in ("question_banks", "questions", "source_documents"):
            connection.execute(
                text(f"UPDATE {table_name} SET domain_id = 'endoscopy' WHERE domain_id = 'medical-education'")
            )


def _upgrade_local_sqlite_factory_jobs(connection: object, inspector: object) -> None:
    """Apply the non-destructive Stage 6 job columns to an old SQLite checkout.

    ``create_all`` cannot evolve an existing local database.  Some developers
    still have a Stage 2 database whose ``factory_jobs`` table predates durable
    job fields, so ORM reads fail before the app can serve anything.  PostgreSQL
    uses Alembic; this is only the equivalent local fallback and preserves all
    existing rows.
    """

    columns = {column["name"] for column in inspector.get_columns("factory_jobs")}
    definitions = {
        "job_type": "VARCHAR(48) NOT NULL DEFAULT 'question_factory'",
        "stage": "VARCHAR(40) NOT NULL DEFAULT 'queued'",
        "progress": "INTEGER NOT NULL DEFAULT 0",
        "input_summary": "JSON NOT NULL DEFAULT '{}'",
        "result_ref": "VARCHAR(160)",
        "error_code": "VARCHAR(80)",
        "error_message": "TEXT",
        "attempt": "INTEGER NOT NULL DEFAULT 0",
        "idempotency_key": "VARCHAR(160)",
        "started_at": "DATETIME",
        "heartbeat_at": "DATETIME",
        "completed_at": "DATETIME",
        "cancel_requested_at": "DATETIME",
        "queue_message_id": "VARCHAR(160)",
    }
    for name, definition in definitions.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE factory_jobs ADD COLUMN {name} {definition}"))
    # The column is nullable only during this compatibility transition.  Fill
    # both newly-added and partially-upgraded local tables before the unique
    # index is created, preserving the existing job identity for every row.
    connection.execute(text("UPDATE factory_jobs SET idempotency_key = job_id WHERE idempotency_key IS NULL"))
    indexes = {item["name"] for item in inspector.get_indexes("factory_jobs") if item.get("name")}
    if "ix_factory_jobs_idempotency_key" not in indexes:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_factory_jobs_idempotency_key ON factory_jobs (idempotency_key)"))


def _upgrade_local_sqlite_knowledge_sources(connection: object, inspector: object) -> None:
    """Add V3.1 knowledge-library metadata without replacing local sources."""

    columns = {column["name"] for column in inspector.get_columns("source_documents")}
    definitions = {
        "source_scope": "VARCHAR(32) NOT NULL DEFAULT 'system'",
        "file_name": "VARCHAR(300)",
        "size_bytes": "INTEGER NOT NULL DEFAULT 0",
        "enabled": "BOOLEAN NOT NULL DEFAULT 1",
        "parser_version": "VARCHAR(80)",
        "embedding_model": "VARCHAR(180)",
        "embedding_provider": "VARCHAR(80)",
        "embedding_dimension": "INTEGER",
        "index_version": "INTEGER NOT NULL DEFAULT 0",
        "index_job_id": "VARCHAR(150)",
        "index_stage": "VARCHAR(48)",
        "index_progress": "INTEGER NOT NULL DEFAULT 0",
        "index_error": "TEXT",
        "updated_at": "DATETIME",
    }
    for name, definition in definitions.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE source_documents ADD COLUMN {name} {definition}"))
    connection.execute(text("UPDATE source_documents SET source_scope = 'qbank_explanations' WHERE namespace = 'qbank_explanations'"))
    connection.execute(text("UPDATE source_documents SET source_scope = 'user' WHERE business_usage = 'factory_source'"))
    connection.execute(text("UPDATE source_documents SET file_name = name WHERE file_name IS NULL"))
    connection.execute(text("UPDATE source_documents SET updated_at = created_at WHERE updated_at IS NULL"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_source_documents_source_scope ON source_documents (source_scope)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_source_documents_enabled ON source_documents (enabled)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_source_documents_index_job_id ON source_documents (index_job_id)"))


def _upgrade_local_sqlite_v32_state(connection: object, inspector: object) -> None:
    """Non-destructively add V3.2 lifecycle fields for existing local data."""

    session_columns = {column["name"] for column in inspector.get_columns("practice_sessions")}
    session_definitions = {
        "requested_question_count": "INTEGER NOT NULL DEFAULT 20",
        "current_position": "INTEGER NOT NULL DEFAULT 0",
        "completed_at": "DATETIME",
        "updated_at": "DATETIME",
        "reflection_dirty": "BOOLEAN NOT NULL DEFAULT 0",
        "reflection_status": "VARCHAR(32) NOT NULL DEFAULT 'clean'",
        "reflection_version": "INTEGER NOT NULL DEFAULT 0",
        "last_reflected_at": "DATETIME",
        "last_reflection_event_id": "VARCHAR(160)",
    }
    for name, definition in session_definitions.items():
        if name not in session_columns:
            connection.execute(text(f"ALTER TABLE practice_sessions ADD COLUMN {name} {definition}"))
    connection.execute(text("UPDATE practice_sessions SET updated_at = last_active_at WHERE updated_at IS NULL"))
    connection.execute(text("UPDATE agent_conversations SET agent_profile = 'mentor' WHERE agent_profile = 'coach'"))


def _rebuild_sqlite_unique_scope(connection: object, table_name: str, expected_constraint: str) -> None:
    """Replace a legacy SQLite unique constraint without losing local rows."""

    inspector = inspect(connection)
    unique_names = {item.get("name") for item in inspector.get_unique_constraints(table_name)}
    if expected_constraint in unique_names:
        return

    table = Base.metadata.tables[table_name]
    legacy_name = f"{table_name}_stage6_legacy"
    legacy_columns = {column["name"] for column in inspector.get_columns(table_name)}
    index_names = [
        item["name"]
        for item in inspector.get_indexes(table_name)
        if item.get("name")
    ]
    quoted_columns = ", ".join(column.name for column in table.columns)
    select_columns = ", ".join(
        column.name if column.name in legacy_columns else "'endoscopy'"
        for column in table.columns
    )

    connection.execute(text(f"ALTER TABLE {table_name} RENAME TO {legacy_name}"))
    # SQLite keeps index names globally unique when a table is renamed.  Drop
    # only this table's recreatable named indexes before SQLAlchemy creates the
    # replacement table and its Stage 7 indexes.
    for index_name in index_names:
        connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
    table.create(connection)
    connection.execute(
        text(
            f"INSERT INTO {table_name} ({quoted_columns}) "
            f"SELECT {select_columns} FROM {legacy_name}"
        )
    )
    connection.execute(text(f"DROP TABLE {legacy_name}"))
