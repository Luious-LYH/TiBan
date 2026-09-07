"""Persist the V3.1.2 question-import review workbench.

Revision ID: v312_question_import
Revises: a6b7c8d9e0f1, f5a1b7c9d204
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v312_question_import"
down_revision: Union[str, Sequence[str], None] = ("a6b7c8d9e0f1", "f5a1b7c9d204")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_import_batches",
        sa.Column("batch_id", sa.String(length=150), nullable=False),
        sa.Column("domain_id", sa.String(length=100), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("file_name", sa.String(length=300), nullable=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="reviewing"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_bank_id", sa.String(length=100), nullable=True),
        sa.Column("source_document_id", sa.String(length=150), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("batch_id"),
    )
    op.create_index("ix_question_import_batches_domain_id", "question_import_batches", ["domain_id"])
    op.create_index("ix_question_import_batches_content_hash", "question_import_batches", ["content_hash"])
    op.create_index("ix_question_import_batches_status", "question_import_batches", ["status"])
    op.create_index("ix_question_import_batches_published_bank_id", "question_import_batches", ["published_bank_id"])
    op.create_index("ix_question_import_batches_source_document_id", "question_import_batches", ["source_document_id"])
    op.create_index("ix_question_import_batches_updated_at", "question_import_batches", ["updated_at"])

    op.create_table(
        "question_import_drafts",
        sa.Column("draft_id", sa.String(length=150), nullable=False),
        sa.Column("batch_id", sa.String(length=150), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["question_import_batches.batch_id"]),
        sa.PrimaryKeyConstraint("draft_id"),
        sa.UniqueConstraint("batch_id", "ordinal", name="uq_question_import_draft_ordinal"),
    )
    op.create_index("ix_question_import_drafts_batch_id", "question_import_drafts", ["batch_id"])
    op.create_index("ix_question_import_drafts_status", "question_import_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_question_import_drafts_status", table_name="question_import_drafts")
    op.drop_index("ix_question_import_drafts_batch_id", table_name="question_import_drafts")
    op.drop_table("question_import_drafts")
    op.drop_index("ix_question_import_batches_updated_at", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_source_document_id", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_published_bank_id", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_status", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_content_hash", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_domain_id", table_name="question_import_batches")
    op.drop_table("question_import_batches")
