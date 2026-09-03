from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import DEFAULT_DOMAIN_ID, DEFAULT_KNOWLEDGE_NAMESPACE

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
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, default=DEFAULT_DOMAIN_ID, index=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="practice")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    requested_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    current_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    # Reflection is derived from immutable Attempts and retained session
    # evidence.  These fields only coordinate idempotent asynchronous work;
    # they are never the canonical learning state.
    reflection_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    reflection_status: Mapped[str] = mapped_column(String(32), nullable=False, default="clean", index=True)
    reflection_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reflected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reflection_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


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


class QuestionMarkModel(Base):
    """A learner-owned bookmark, deliberately separate from an Attempt.

    A mark is an intentional study signal, not a derived score.  Keeping it in
    its own small table makes the bank/review filters truthful and prevents the
    frontend from pretending a browser-local toggle is durable learning state.
    """

    __tablename__ = "question_marks"
    __table_args__ = (UniqueConstraint("learner_id", "question_id", name="uq_question_mark_learner_question"),)

    mark_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.question_id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class AgentConversationModel(Base):
    """Minimal durable history for the global Mentor only.

    Practice-side intelligent-assistant turns are deliberately scoped to the
    active question and remain ephemeral; Mentor is the cross-session
    learning surface that needs a truthful, learner-owned history.
    """

    __tablename__ = "agent_conversations"

    conversation_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    agent_profile: Mapped[str] = mapped_column(String(40), nullable=False, default="mentor", index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False, index=True)


class AgentMessageModel(Base):
    __tablename__ = "agent_messages"

    message_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("agent_conversations.conversation_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    activity: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)


class TutorThreadModel(Base):
    """Auditable, session-scoped Tutor conversation identity.

    A persisted thread supplies evidence for Reflection but is never reused as
    prompt context outside this particular browser usage of a Practice session.
    """

    __tablename__ = "tutor_threads"

    tutor_thread_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.session_id"), nullable=False, index=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TutorMessageModel(Base):
    """Current-session Tutor evidence, intentionally separate from Mentor chat."""

    __tablename__ = "tutor_messages"

    tutor_message_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    tutor_thread_id: Mapped[str] = mapped_column(ForeignKey("tutor_threads.tutor_thread_id"), nullable=False, index=True)
    practice_session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.session_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    activity: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    run_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)


class ReviewCardModel(Base):
    __tablename__ = "review_cards"
    __table_args__ = (UniqueConstraint("learner_id", "question_id", name="uq_review_card_learner_question"),)

    review_card_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.question_id"), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, default=DEFAULT_DOMAIN_ID, index=True)
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
    namespace: Mapped[str] = mapped_column(String(80), nullable=False, default=DEFAULT_KNOWLEDGE_NAMESPACE, index=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    # V3.1 knowledge-library metadata. ``name`` remains the learner-visible
    # title; the remaining fields describe the actual indexed source without
    # exposing vector/chunk implementation details to the UI.
    source_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="system", index=True)
    file_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    parser_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(180), nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    index_job_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    index_stage: Mapped[str | None] = mapped_column(String(48), nullable=True)
    index_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


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
    namespace: Mapped[str] = mapped_column(String(80), nullable=False, default=DEFAULT_KNOWLEDGE_NAMESPACE, index=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class LearnerMasteryModel(Base):
    __tablename__ = "learner_mastery"
    __table_args__ = (UniqueConstraint("learner_id", "domain_id", "knowledge_point", name="uq_mastery_learner_domain_point"),)

    mastery_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, default=DEFAULT_DOMAIN_ID, index=True)
    knowledge_point: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    common_errors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class LearningMemoryItemModel(Base):
    """Evidence-backed, cross-session learning facts.

    This model intentionally complements, rather than replaces, immutable
    attempts, derived mastery, and FSRS review state.  It contains compact
    learning facts only: never raw chat, provider prompts, answer keys, or
    model reasoning.
    """

    __tablename__ = "learning_memory_items"
    __table_args__ = (
        UniqueConstraint("learner_id", "domain_id", "dedupe_key", name="uq_learning_memory_learner_domain_dedupe"),
        Index("ix_learning_memory_learner_domain_status", "learner_id", "domain_id", "status"),
    )

    memory_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, default=DEFAULT_DOMAIN_ID, index=True)
    kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    topic_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    concept_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class VectorIndexStateModel(Base):
    """One active, rebuildable vector representation per logical index."""

    __tablename__ = "vector_index_states"

    index_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_id: Mapped[str] = mapped_column(String(180), nullable=False)
    vector_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="stale", index=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class BackgroundJobModel(Base):
    """Shared durable job record for Knowledge indexing and Reflection.

    Factory retains its dedicated trace model.  This slim generic record uses
    the same Redis/Dramatiq operational model for non-Factory heavy work.
    """

    __tablename__ = "background_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_background_job_idempotency"),)

    job_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(48), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class FactoryJobModel(Base):
    __tablename__ = "factory_jobs"

    job_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.document_id"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False, default="question_factory")
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, default=DEFAULT_DOMAIN_ID, index=True)
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


# V3.3 Evaluation Lab intentionally has its own compact persistence graph.
# The earlier ``Eval*`` tables remain the developer/CI portfolio regression
# record; mixing those artifact-oriented runs into a learner-visible
# leaderboard would make a frozen experiment impossible to reason about.
class EvalSuiteModel(Base):
    __tablename__ = "eval_suites"

    suite_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    bank_id: Mapped[str] = mapped_column(ForeignKey("question_banks.bank_id"), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bank_version: Mapped[str] = mapped_column(String(80), nullable=False)
    bank_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    question_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    suite_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EvalRagProfileModel(Base):
    """An instance-scoped, reusable RAG comparison profile.

    Profiles are deliberately separate from an experiment.  An experiment
    stores the exact profile snapshot it ran with, while this table stores the
    small set of configurations a user may want to reuse for a bank.
    """

    __tablename__ = "eval_rag_profiles"

    profile_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    bank_id: Mapped[str] = mapped_column(ForeignKey("question_banks.bank_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(12), nullable=False, default="hybrid")
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    candidate_pool: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    rerank_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rrf_k: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    section_dedupe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EvalExperimentModel(Base):
    __tablename__ = "eval_experiments"

    experiment_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    experiment_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(ForeignKey("eval_suites.suite_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    fixed_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EvalLabRunModel(Base):
    __tablename__ = "eval_lab_runs"
    __table_args__ = (
        # Fresh local databases are bootstrapped with create_all rather than
        # Alembic. Keep the same model-candidate guard in both paths. RAG
        # baseline/variants have a non-null retrieval profile and intentionally
        # do not collide on their shared answer model.
        Index(
            "uq_eval_lab_run_endpoint_model",
            "experiment_id",
            "provider_base_url",
            "model",
            unique=True,
            sqlite_where=text("retrieval_profile IS NULL OR retrieval_profile = 'null'"),
            postgresql_where=text("retrieval_profile IS NULL OR retrieval_profile = 'null'::json"),
        ),
    )

    run_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("eval_experiments.experiment_id"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("background_jobs.job_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_base_url: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    model: Mapped[str] = mapped_column(String(180), nullable=False)
    retrieval_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    aggregate: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EvalLabCaseModel(Base):
    __tablename__ = "eval_lab_cases"

    case_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("eval_lab_runs.run_id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.question_id"), nullable=False, index=True)
    valid_response: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gold_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
