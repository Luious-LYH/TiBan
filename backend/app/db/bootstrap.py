from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, inspect, select, text

from app.core.config import DEMO_QBANK_BOOTSTRAP, DESKTOP_CMEXAM_BUNDLE

from .database import Base, SessionLocal, engine
from .models import (  # noqa: F401
    AttemptModel,
    PracticeSessionModel,
    QuestionBankModel,
    QuestionBankDeletionModel,
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
    QuestionImportBatchModel,
    QuestionImportDraftModel,
    QuestionImageAssetModel,
    KnowledgeFolderModel,
    KnowledgeMediaAssetModel,
    KnowledgeEntityModel,
    KnowledgeRelationModel,
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
        deleted_ids = set(session.scalars(select(QuestionBankDeletionModel.bank_id)))
        rows = session.execute(
            select(QuestionModel.bank_id, func.count(QuestionModel.question_id))
            .where(QuestionModel.business_usage == "user_ready")
            .where(QuestionModel.bank_id.in_(DEMO_QBANK_EXPECTATIONS))
            .group_by(QuestionModel.bank_id)
        ).all()
    counts = {bank_id: 0 for bank_id in DEMO_QBANK_EXPECTATIONS}
    counts.update({str(bank_id): int(count) for bank_id, count in rows})
    for bank_id in deleted_ids:
        counts.pop(str(bank_id), None)
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
    with SessionLocal() as session:
        deleted_ids = set(session.scalars(select(QuestionBankDeletionModel.bank_id)))
    missing = {
        bank_id
        for bank_id, expected in DEMO_QBANK_EXPECTATIONS.items()
        if bank_id not in deleted_ids and before.get(bank_id, 0) < expected
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
        if bank_id not in deleted_ids and after.get(bank_id, 0) < expected
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
    before = demo_qbank_counts().get("bank-cmexam-real", 0)
    with SessionLocal() as session:
        if session.get(QuestionBankDeletionModel, "bank-cmexam-real") is not None:
            return {"imported": 0, "counts": {"bank-cmexam-real": 0}, "status": "deleted"}
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
    _ensure_knowledge_folders()
    # Seed/import code intentionally leaves new banks at the neutral order
    # value.  Once the catalog rows exist, append any such rows deterministically
    # so a restart never causes a newly imported bank to jump around.
    _backfill_local_sqlite_question_bank_order()
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
        _upgrade_local_sqlite_knowledge_multimodal(connection, inspector)
        _upgrade_local_sqlite_v32_state(connection, inspector)
        _upgrade_local_sqlite_question_import_review(connection, inspector)
        _upgrade_local_sqlite_question_image_assets(connection, inspector)
        _upgrade_local_sqlite_agent_image_flags(connection, inspector)
        _upgrade_local_sqlite_question_bank_order(connection, inspector)
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
        "folder_id": "VARCHAR(120)",
        "parse_stats": "JSON NOT NULL DEFAULT '{}'",
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
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_source_documents_folder_id ON source_documents (folder_id)"))


def _ensure_knowledge_folders() -> None:
    """Create the small default folder set and place legacy sources in it.

    This is intentionally idempotent and metadata-only.  It runs for both the
    fresh local bootstrap and an existing SQLite database without touching
    chunks, media assets or vector collections.
    """

    defaults = (
        ("folder-clinical-guidelines", "临床诊疗指南", "本机导入的临床诊疗与教学参考资料。", "user", False, 10),
        ("folder-system", "系统资料", "TiBan 随附的学习资料。", "system", True, 20),
        ("folder-qbank-explanations", "题库解析", "由已发布题库整理的可检索解析。", "qbank_explanations", True, 30),
        ("folder-my-materials", "我的资料", "个人上传的学习资料。", "user", False, 40),
    )
    with SessionLocal() as session:
        for folder_id, name, description, scope, is_system, display_order in defaults:
            row = session.get(KnowledgeFolderModel, folder_id)
            if row is None:
                session.add(KnowledgeFolderModel(
                    folder_id=folder_id,
                    name=name,
                    description=description,
                    scope=scope,
                    is_system=is_system,
                    display_order=display_order,
                ))
            else:
                # Folder names are learner-owned organization metadata.  Do
                # not silently undo a rename every time the API restarts.  The
                # stable default rows still receive their scope/ordering
                # contract; their current name and description remain intact.
                row.scope = scope
                row.is_system = is_system
                row.display_order = display_order
        session.flush()
        for row in session.scalars(select(SourceDocumentModel).where(SourceDocumentModel.status != "deleted")):
            if row.source_scope == "qbank_explanations" or row.namespace == "qbank_explanations":
                row.folder_id = "folder-qbank-explanations"
                row.source_scope = "qbank_explanations"
            elif row.folder_id == "folder-clinical-guidelines":
                row.source_scope = "user"
                row.namespace = "user"
            elif row.folder_id == "folder-system" or row.source_scope == "system":
                row.source_scope = "user"
                row.namespace = "user"
                row.folder_id = "folder-my-materials"
            elif row.source_scope == "user" and row.folder_id is None:
                row.folder_id = "folder-my-materials"
        session.commit()


def _upgrade_local_sqlite_knowledge_multimodal(connection: object, inspector: object) -> None:
    """Add the additive metadata used by the knowledge media pipeline.

    Existing local databases receive the image-asset, image-index and
    evidence-graph columns without rewriting source/chunk content.  Actual
    media extraction and graph/index rebuilds remain in the knowledge service,
    so startup stays safe when optional vector services are unavailable.
    """

    source_columns = {column["name"] for column in inspect(connection).get_columns("source_documents")}
    source_definitions = {
        "image_count": "INTEGER NOT NULL DEFAULT 0",
        "image_index_status": "VARCHAR(24) NOT NULL DEFAULT 'empty'",
        "image_index_error": "TEXT",
        "graph_status": "VARCHAR(24) NOT NULL DEFAULT 'empty'",
        "graph_node_count": "INTEGER NOT NULL DEFAULT 0",
        "graph_edge_count": "INTEGER NOT NULL DEFAULT 0",
        "graph_error": "TEXT",
    }
    for name, definition in source_definitions.items():
        if name not in source_columns:
            connection.execute(text(f"ALTER TABLE source_documents ADD COLUMN {name} {definition}"))

    chunk_columns = {column["name"] for column in inspect(connection).get_columns("knowledge_chunks")}
    chunk_definitions = {
        "modality": "VARCHAR(16) NOT NULL DEFAULT 'text'",
        "media_asset_ids": "JSON NOT NULL DEFAULT '[]'",
        "parent_chunk_id": "VARCHAR(150)",
        "element_ids": "JSON NOT NULL DEFAULT '[]'",
        "element_type": "VARCHAR(24) NOT NULL DEFAULT 'paragraph'",
        "page_start": "INTEGER NOT NULL DEFAULT 1",
        "page_end": "INTEGER NOT NULL DEFAULT 1",
        "provenance": "JSON NOT NULL DEFAULT '{}'",
    }
    for name, definition in chunk_definitions.items():
        if name not in chunk_columns:
            connection.execute(text(f"ALTER TABLE knowledge_chunks ADD COLUMN {name} {definition}"))

    # ``create_all`` covers fresh databases.  ``checkfirst`` makes this safe
    # for an older database that is upgraded in place and for test fixtures
    # created from a partially migrated checkout.
    for table_name in ("knowledge_media_assets", "knowledge_entities", "knowledge_relations"):
        Base.metadata.tables[table_name].create(connection, checkfirst=True)
    asset_columns = {column["name"] for column in inspect(connection).get_columns("knowledge_media_assets")}
    asset_definitions = {
        "asset_type": "VARCHAR(24) NOT NULL DEFAULT 'figure'",
        "bbox": "JSON",
        "source_element_id": "VARCHAR(180)",
        "section_path": "VARCHAR(500)",
    }
    for name, definition in asset_definitions.items():
        if name not in asset_columns:
            connection.execute(text(f"ALTER TABLE knowledge_media_assets ADD COLUMN {name} {definition}"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_media_assets_asset_type ON knowledge_media_assets (asset_type)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_media_assets_source_element_id ON knowledge_media_assets (source_element_id)"))


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


def _upgrade_local_sqlite_question_import_review(connection: object, inspector: object) -> None:
    """Preserve validation issues for review batches created before this field.

    The review UI is resumable, so parse warnings must survive leaving the page.
    This is the SQLite equivalent of the Alembic column below; it only adds a
    JSON field and backfills existing rows with an empty list.
    """

    columns = {column["name"] for column in inspector.get_columns("question_import_batches")}
    if "issues" not in columns:
        connection.execute(text("ALTER TABLE question_import_batches ADD COLUMN issues JSON NOT NULL DEFAULT '[]'"))


def _upgrade_local_sqlite_question_image_assets(connection: object, inspector: object) -> None:
    """Add the V3.5 runtime image asset table for an existing local SQLite DB."""

    if "question_image_assets" in inspector.get_table_names():
        return
    connection.execute(text(
        "CREATE TABLE question_image_assets ("
        "asset_id VARCHAR(150) NOT NULL PRIMARY KEY, "
        "kind VARCHAR(32) NOT NULL, batch_id VARCHAR(150), bank_id VARCHAR(100), "
        "storage_path VARCHAR(300) NOT NULL UNIQUE, original_filename VARCHAR(300) NOT NULL, "
        "sha256 VARCHAR(64) NOT NULL, mime_type VARCHAR(40) NOT NULL, width INTEGER NOT NULL, "
        "height INTEGER NOT NULL, size_bytes INTEGER NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'staged', "
        "created_at DATETIME NOT NULL, expires_at DATETIME"
        ")"
    ))
    for name, column in (
        ("ix_question_image_assets_kind", "kind"),
        ("ix_question_image_assets_batch_id", "batch_id"),
        ("ix_question_image_assets_bank_id", "bank_id"),
        ("ix_question_image_assets_sha256", "sha256"),
        ("ix_question_image_assets_status", "status"),
        ("ix_question_image_assets_expires_at", "expires_at"),
    ):
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON question_image_assets ({column})"))


def _upgrade_local_sqlite_agent_image_flags(connection: object, inspector: object) -> None:
    """Add non-sensitive attachment metadata to existing chat tables."""

    for table_name in ("agent_messages", "tutor_messages"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "image_attached" not in columns:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN image_attached BOOLEAN NOT NULL DEFAULT 0"))
        if "image_asset_id" not in columns:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN image_asset_id VARCHAR(150)"))
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_image_asset_id ON {table_name} (image_asset_id)"))


def _upgrade_local_sqlite_question_bank_order(connection: object, inspector: object) -> None:
    """Add the non-destructive catalog ordering field to old local databases."""

    columns = {column["name"] for column in inspector.get_columns("question_banks")}
    if "display_order" not in columns:
        connection.execute(text("ALTER TABLE question_banks ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0"))
    _backfill_question_bank_order(connection)


def _backfill_local_sqlite_question_bank_order() -> None:
    """Append rows created during bootstrap while preserving existing order."""

    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        _backfill_question_bank_order(connection)


def _backfill_question_bank_order(connection: object) -> None:
    """Give only neutral-order rows a stable position after existing rows."""

    rows = connection.execute(
        text("SELECT bank_id, display_order FROM question_banks ORDER BY name, bank_id")
    ).mappings().all()
    next_order = max((int(row["display_order"] or 0) for row in rows), default=0)
    for row in rows:
        if int(row["display_order"] or 0) > 0:
            continue
        next_order += 1
        connection.execute(
            text("UPDATE question_banks SET display_order = :display_order WHERE bank_id = :bank_id"),
            {"display_order": next_order, "bank_id": row["bank_id"]},
        )


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
