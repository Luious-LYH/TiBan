"""Persist reusable Evaluation Lab RAG comparison profiles.

Revision ID: a6b7c8d9e0f1
Revises: f4c5d6e7f8a9
"""

from alembic import op
import sqlalchemy as sa


revision = "a6b7c8d9e0f1"
down_revision = "f4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_rag_profiles",
        sa.Column("profile_id", sa.String(length=150), primary_key=True),
        sa.Column("bank_id", sa.String(length=100), sa.ForeignKey("question_banks.bank_id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False, server_default="hybrid"),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("candidate_pool", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("rerank_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rrf_k", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("section_dedupe", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_eval_rag_profiles_bank_id", "eval_rag_profiles", ["bank_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_rag_profiles_bank_id", table_name="eval_rag_profiles")
    op.drop_table("eval_rag_profiles")
