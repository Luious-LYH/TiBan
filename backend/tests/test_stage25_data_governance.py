from __future__ import annotations

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import KnowledgeChunkModel, QuestionModel, SourceDocumentModel
from app.services.data_governance import source_can_enter_tutor


def test_endobench_is_not_a_tutor_source() -> None:
    assert not source_can_enter_tutor(
        business_usage="benchmark_only",
        license_gate_status="allow_noncommercial",
        ai_ingestion_allowed=True,
    )


def test_x1_legacy_rows_are_not_learner_ready() -> None:
    with SessionLocal() as session:
        rows = list(session.scalars(select(QuestionModel).where(QuestionModel.source_dataset == "Kvasir-VQA-x1")))
    assert rows
    assert all(row.business_usage == "generation_source" for row in rows)


def test_kvasir_curated_bank_has_lineage_and_legacy_vqa_is_quarantined() -> None:
    with SessionLocal() as session:
        curated = list(
            session.scalars(
                select(QuestionModel).where(
                    QuestionModel.source_dataset == "Kvasir-VQA",
                    QuestionModel.business_usage == "user_ready",
                )
            )
        )
        legacy = list(
            session.scalars(
                select(QuestionModel).where(
                    QuestionModel.source_dataset == "Kvasir-VQA",
                    QuestionModel.source_item_id.is_(None),
                )
            )
        )
    assert len(curated) == 400
    assert all(item.bank_id == "bank-kvasir-vqa-curated" and item.source_item_id for item in curated)
    assert legacy
    assert all(item.business_usage == "generation_source" for item in legacy)


def test_postgres_runtime_contains_no_endobench_tutor_lineage() -> None:
    with SessionLocal() as session:
        benchmark_documents = list(
            session.scalars(
                select(SourceDocumentModel).where(
                    SourceDocumentModel.source_id.ilike("%endobench%")
                )
            )
        )
        benchmark_document_ids = {item.document_id for item in benchmark_documents}
        chunks = list(session.scalars(select(KnowledgeChunkModel)))
        endobench_questions = list(
            session.scalars(
                select(QuestionModel).where(
                    (QuestionModel.source_dataset == "EndoBench")
                    | (QuestionModel.derived_from_dataset == "EndoBench")
                )
            )
        )
    assert not benchmark_documents
    assert not any(chunk.document_id in benchmark_document_ids for chunk in chunks)
    assert all(item.business_usage == "benchmark_only" for item in endobench_questions)
