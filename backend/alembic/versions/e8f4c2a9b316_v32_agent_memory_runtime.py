"""Add V3.2 session/Tutor evidence, derived-index and background-job state.

Revision ID: e8f4c2a9b316
Revises: b7c3e1d4f208, c8e7d6f5a4b3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f4c2a9b316"
down_revision: Union[str, Sequence[str], None] = ("b7c3e1d4f208", "c8e7d6f5a4b3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE agent_conversations SET agent_profile = 'mentor' WHERE agent_profile = 'coach'"))
    with op.batch_alter_table("agent_conversations") as batch:
        batch.alter_column("agent_profile", server_default="mentor")
    for column in (
        sa.Column("embedding_provider", sa.String(length=80), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("index_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("index_job_id", sa.String(length=150), nullable=True),
        sa.Column("index_stage", sa.String(length=48), nullable=True),
        sa.Column("index_progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("index_error", sa.Text(), nullable=True),
    ):
        op.add_column("source_documents", column)
    op.create_index("ix_source_documents_index_job_id", "source_documents", ["index_job_id"])
    for name, column in (
        ("requested_question_count", sa.Column("requested_question_count", sa.Integer(), nullable=False, server_default="20")),
        ("current_position", sa.Column("current_position", sa.Integer(), nullable=False, server_default="0")),
        ("completed_at", sa.Column("completed_at", sa.DateTime(), nullable=True)),
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
        ("reflection_dirty", sa.Column("reflection_dirty", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("reflection_status", sa.Column("reflection_status", sa.String(length=32), nullable=False, server_default="clean")),
        ("reflection_version", sa.Column("reflection_version", sa.Integer(), nullable=False, server_default="0")),
        ("last_reflected_at", sa.Column("last_reflected_at", sa.DateTime(), nullable=True)),
        ("last_reflection_event_id", sa.Column("last_reflection_event_id", sa.String(length=160), nullable=True)),
    ):
        op.add_column("practice_sessions", column)
    op.execute(sa.text("UPDATE practice_sessions SET updated_at = last_active_at WHERE updated_at IS NULL"))
    op.create_index("ix_practice_sessions_reflection_dirty", "practice_sessions", ["reflection_dirty"])
    op.create_index("ix_practice_sessions_reflection_status", "practice_sessions", ["reflection_status"])
    op.create_table(
        "tutor_threads",
        sa.Column("tutor_thread_id", sa.String(length=150), primary_key=True),
        sa.Column("practice_session_id", sa.String(length=150), sa.ForeignKey("practice_sessions.session_id"), nullable=False),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tutor_threads_practice_session_id", "tutor_threads", ["practice_session_id"])
    op.create_index("ix_tutor_threads_learner_id", "tutor_threads", ["learner_id"])
    op.create_index("ix_tutor_threads_status", "tutor_threads", ["status"])
    op.create_index("ix_tutor_threads_last_active_at", "tutor_threads", ["last_active_at"])
    op.create_table(
        "tutor_messages",
        sa.Column("tutor_message_id", sa.String(length=150), primary_key=True),
        sa.Column("tutor_thread_id", sa.String(length=150), sa.ForeignKey("tutor_threads.tutor_thread_id"), nullable=False),
        sa.Column("practice_session_id", sa.String(length=150), sa.ForeignKey("practice_sessions.session_id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("activity", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("sources", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("run_id", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for index in ("tutor_thread_id", "practice_session_id", "run_id", "created_at"):
        op.create_index(f"ix_tutor_messages_{index}", "tutor_messages", [index])
    op.create_table(
        "vector_index_states",
        sa.Column("index_key", sa.String(length=80), primary_key=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model_id", sa.String(length=180), nullable=False),
        sa.Column("vector_dimension", sa.Integer(), nullable=True),
        sa.Column("index_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="stale"),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_vector_index_states_status", "vector_index_states", ["status"])
    op.create_table(
        "background_jobs",
        sa.Column("job_id", sa.String(length=150), primary_key=True),
        sa.Column("job_type", sa.String(length=48), nullable=False),
        sa.Column("target_id", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=48), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_background_job_idempotency"),
    )
    for index in ("job_type", "target_id", "status"):
        op.create_index(f"ix_background_jobs_{index}", "background_jobs", [index])


def downgrade() -> None:
    for index in ("status", "target_id", "job_type"):
        op.drop_index(f"ix_background_jobs_{index}", table_name="background_jobs")
    op.drop_table("background_jobs")
    op.drop_index("ix_vector_index_states_status", table_name="vector_index_states")
    op.drop_table("vector_index_states")
    for index in ("created_at", "run_id", "practice_session_id", "tutor_thread_id"):
        op.drop_index(f"ix_tutor_messages_{index}", table_name="tutor_messages")
    op.drop_table("tutor_messages")
    for index in ("last_active_at", "status", "learner_id", "practice_session_id"):
        op.drop_index(f"ix_tutor_threads_{index}", table_name="tutor_threads")
    op.drop_table("tutor_threads")
    op.drop_index("ix_practice_sessions_reflection_status", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_reflection_dirty", table_name="practice_sessions")
    for name in ("last_reflection_event_id", "last_reflected_at", "reflection_version", "reflection_status", "reflection_dirty", "updated_at", "completed_at", "current_position", "requested_question_count"):
        op.drop_column("practice_sessions", name)
    op.execute(sa.text("UPDATE agent_conversations SET agent_profile = 'coach' WHERE agent_profile = 'mentor'"))
    op.drop_index("ix_source_documents_index_job_id", table_name="source_documents")
    for name in ("index_error", "index_progress", "index_stage", "index_job_id", "index_version", "embedding_dimension", "embedding_provider"):
        op.drop_column("source_documents", name)
