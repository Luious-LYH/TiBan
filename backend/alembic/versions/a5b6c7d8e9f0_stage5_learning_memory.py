"""Persist evidence-backed Stage 5 learning memory.

Revision ID: a5b6c7d8e9f0
Revises: e4c6a1b8f203
"""

from alembic import op
import sqlalchemy as sa


revision = "a5b6c7d8e9f0"
down_revision = "e4c6a1b8f203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_memory_items",
        sa.Column("memory_id", sa.String(length=150), primary_key=True),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("topic_keys", sa.JSON(), nullable=False),
        sa.Column("concept_keys", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("learner_id", "dedupe_key", name="uq_learning_memory_learner_dedupe"),
    )
    op.create_index("ix_learning_memory_items_learner_id", "learning_memory_items", ["learner_id"])
    op.create_index("ix_learning_memory_items_kind", "learning_memory_items", ["kind"])
    op.create_index("ix_learning_memory_items_status", "learning_memory_items", ["status"])
    op.create_index("ix_learning_memory_items_last_seen_at", "learning_memory_items", ["last_seen_at"])
    op.create_index("ix_learning_memory_learner_status", "learning_memory_items", ["learner_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_learning_memory_learner_status", table_name="learning_memory_items")
    op.drop_index("ix_learning_memory_items_last_seen_at", table_name="learning_memory_items")
    op.drop_index("ix_learning_memory_items_status", table_name="learning_memory_items")
    op.drop_index("ix_learning_memory_items_kind", table_name="learning_memory_items")
    op.drop_index("ix_learning_memory_items_learner_id", table_name="learning_memory_items")
    op.drop_table("learning_memory_items")
