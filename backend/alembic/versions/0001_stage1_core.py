"""Create the Stage 1 relational persistence boundary.

Revision ID: 0001_stage1_core
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_stage1_core"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_banks",
        sa.Column("bank_id", sa.String(length=100), nullable=False),
        sa.Column("domain_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("question_type_counts", sa.JSON(), nullable=False),
        sa.Column("modality_counts", sa.JSON(), nullable=False),
        sa.Column("body_parts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("bank_id"),
    )
    op.create_index("ix_question_banks_domain_id", "question_banks", ["domain_id"])

    op.create_table(
        "questions",
        sa.Column("question_id", sa.String(length=150), nullable=False),
        sa.Column("bank_id", sa.String(length=100), nullable=False),
        sa.Column("domain_id", sa.String(length=100), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("modality", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("case_summary", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_alt", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=30), nullable=False),
        sa.Column("complexity", sa.Integer(), nullable=False),
        sa.Column("question_class", sa.String(length=80), nullable=False),
        sa.Column("task", sa.String(length=120), nullable=False),
        sa.Column("body_part", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_dataset", sa.String(length=150), nullable=False),
        sa.Column("citation_note", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("grading_payload", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("teaching_tags", sa.JSON(), nullable=False),
        sa.Column("expected_keywords", sa.JSON(), nullable=False),
        sa.Column("false_premise", sa.Boolean(), nullable=False),
        sa.Column("doctor_review_required", sa.Boolean(), nullable=False),
        sa.Column("safety_notice", sa.Text(), nullable=False),
        sa.Column("source_document_id", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["question_banks.bank_id"]),
        sa.PrimaryKeyConstraint("question_id"),
    )
    op.create_index("ix_questions_bank_id", "questions", ["bank_id"])
    op.create_index("ix_questions_domain_id", "questions", ["domain_id"])
    op.create_index("ix_questions_question_type", "questions", ["question_type"])
    op.create_index("ix_questions_body_part", "questions", ["body_part"])

    op.create_table(
        "practice_sessions",
        sa.Column("session_id", sa.String(length=150), nullable=False),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("bank_id", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["question_banks.bank_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_practice_sessions_learner_id", "practice_sessions", ["learner_id"])
    op.create_index("ix_practice_sessions_bank_id", "practice_sessions", ["bank_id"])

    op.create_table(
        "attempts",
        sa.Column("attempt_id", sa.String(length=150), nullable=False),
        sa.Column("practice_session_id", sa.String(length=150), nullable=False),
        sa.Column("question_id", sa.String(length=150), nullable=False),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("selected_answer", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("error_tags", sa.JSON(), nullable=False),
        sa.Column("hint_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["practice_session_id"], ["practice_sessions.session_id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.question_id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index("ix_attempts_practice_session_id", "attempts", ["practice_session_id"])
    op.create_index("ix_attempts_question_id", "attempts", ["question_id"])
    op.create_index("ix_attempts_learner_id", "attempts", ["learner_id"])
    op.create_index("ix_attempts_created_at", "attempts", ["created_at"])

    op.create_table(
        "review_cards",
        sa.Column("review_card_id", sa.String(length=150), nullable=False),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("question_id", sa.String(length=150), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.question_id"]),
        sa.PrimaryKeyConstraint("review_card_id"),
        sa.UniqueConstraint("learner_id", "question_id", name="uq_review_card_learner_question"),
    )
    op.create_index("ix_review_cards_learner_id", "review_cards", ["learner_id"])
    op.create_index("ix_review_cards_question_id", "review_cards", ["question_id"])
    op.create_index("ix_review_cards_due_at", "review_cards", ["due_at"])

    op.create_table(
        "source_documents",
        sa.Column("document_id", sa.String(length=150), nullable=False),
        sa.Column("domain_id", sa.String(length=100), nullable=False),
        sa.Column("bank_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["question_banks.bank_id"]),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index("ix_source_documents_domain_id", "source_documents", ["domain_id"])
    op.create_index("ix_source_documents_bank_id", "source_documents", ["bank_id"])


def downgrade() -> None:
    op.drop_index("ix_source_documents_bank_id", table_name="source_documents")
    op.drop_index("ix_source_documents_domain_id", table_name="source_documents")
    op.drop_table("source_documents")
    op.drop_index("ix_review_cards_due_at", table_name="review_cards")
    op.drop_index("ix_review_cards_question_id", table_name="review_cards")
    op.drop_index("ix_review_cards_learner_id", table_name="review_cards")
    op.drop_table("review_cards")
    op.drop_index("ix_attempts_created_at", table_name="attempts")
    op.drop_index("ix_attempts_learner_id", table_name="attempts")
    op.drop_index("ix_attempts_question_id", table_name="attempts")
    op.drop_index("ix_attempts_practice_session_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_practice_sessions_bank_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_learner_id", table_name="practice_sessions")
    op.drop_table("practice_sessions")
    op.drop_index("ix_questions_body_part", table_name="questions")
    op.drop_index("ix_questions_question_type", table_name="questions")
    op.drop_index("ix_questions_domain_id", table_name="questions")
    op.drop_index("ix_questions_bank_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_question_banks_domain_id", table_name="question_banks")
    op.drop_table("question_banks")
