from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class QuestionBankModel(Base):
    __tablename__ = "question_banks"

    bank_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="seed-v1")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="published")
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_type_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    modality_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    body_parts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class QuestionModel(Base):
    __tablename__ = "questions"

    question_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    bank_id: Mapped[str] = mapped_column(ForeignKey("question_banks.bank_id"), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    modality: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    case_summary: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_alt: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    complexity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    question_class: Mapped[str] = mapped_column(String(80), nullable=False, default="基础识别")
    task: Mapped[str] = mapped_column(String(120), nullable=False, default="图像观察")
    body_part: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_dataset: Mapped[str] = mapped_column(String(150), nullable=False)
    citation_note: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    grading_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    teaching_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    false_premise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    doctor_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    safety_notice: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source_item_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    derived_from_dataset: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    business_usage: Mapped[str] = mapped_column(String(40), nullable=False, default="user_ready")
    answer_source: Mapped[str] = mapped_column(String(40), nullable=False, default="dataset_gold")
    explanation_source: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    license_gate_status: Mapped[str] = mapped_column(String(30), nullable=False, default="needs_review")
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_explanation_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subject: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    topic: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PracticeSessionModel(Base):
    __tablename__ = "practice_sessions"

    session_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bank_id: Mapped[str] = mapped_column(ForeignKey("question_banks.bank_id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="practice")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PracticeSessionItemModel(Base):
    """Stable, server-side membership for one bounded practice/exam session."""

    __tablename__ = "practice_session_items"
    __table_args__ = (
        UniqueConstraint("practice_session_id", "ordinal", name="uq_practice_session_item_ordinal"),
        UniqueConstraint("practice_session_id", "question_id", name="uq_practice_session_item_question"),
    )

    session_item_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.session_id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.question_id"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class AttemptModel(Base):
    __tablename__ = "attempts"

    attempt_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.session_id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.question_id"), nullable=False, index=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    selected_answer: Mapped[Any] = mapped_column(JSON, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    hint_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)


class ReviewCardModel(Base):
    __tablename__ = "review_cards"
    __table_args__ = (UniqueConstraint("learner_id", "question_id", name="uq_review_card_learner_question"),)

    review_card_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.question_id"), nullable=False, index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # FSRS is the canonical scheduling state.  The legacy interval fields stay
    # readable during migration, but are derived from this record after Stage 2.
    fsrs_card: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    fsrs_logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrievability: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_state: Mapped[str] = mapped_column(String(32), nullable=False, default="Learning")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"

    document_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bank_id: Mapped[str | None] = mapped_column(ForeignKey("question_banks.bank_id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="seed")
    source_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    business_usage: Mapped[str] = mapped_column(String(40), nullable=False, default="knowledge_base")
    license_gate_status: Mapped[str] = mapped_column(String(30), nullable=False, default="needs_review")
    ai_ingestion_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    namespace: Mapped[str] = mapped_column(String(80), nullable=False, default="medical_general", index=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class DocumentVersionModel(Base):
    __tablename__ = "document_versions"

    version_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.document_id"), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(80), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    parser: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="indexed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    chunk_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.document_id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.version_id"), nullable=False, index=True)
    parent_section: Mapped[str] = mapped_column(String(300), nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    namespace: Mapped[str] = mapped_column(String(80), nullable=False, default="medical_general", index=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class LearnerMasteryModel(Base):
    __tablename__ = "learner_mastery"
    __table_args__ = (UniqueConstraint("learner_id", "knowledge_point", name="uq_mastery_learner_point"),)

    mastery_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    knowledge_point: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    common_errors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class FactoryJobModel(Base):
    __tablename__ = "factory_jobs"

    job_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.document_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    queue_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class QuestionRevisionModel(Base):
    __tablename__ = "question_revisions"

    revision_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    parent_revision_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("factory_jobs.job_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    draft_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    judge_decision: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    rewrite_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EvalDatasetModel(Base):
    __tablename__ = "eval_datasets"

    dataset_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_dataset: Mapped[str] = mapped_column(String(120), nullable=False)
    modality: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tutor_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EvalDatasetVersionModel(Base):
    __tablename__ = "eval_dataset_versions"

    dataset_version_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("eval_datasets.dataset_id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EvalRunModel(Base):
    __tablename__ = "eval_runs"

    eval_run_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dataset_version: Mapped[str] = mapped_column(String(120), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(180), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EvalCaseModel(Base):
    __tablename__ = "eval_cases"

    eval_case_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.eval_run_id"), nullable=False, index=True)
    source_item_id: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_output: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_answer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gold_answer: Mapped[str] = mapped_column(String(100), nullable=False)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    valid_parse: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task: Mapped[str] = mapped_column(String(120), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EvalArtifactModel(Base):
    __tablename__ = "eval_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.eval_run_id"), nullable=False, index=True)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
