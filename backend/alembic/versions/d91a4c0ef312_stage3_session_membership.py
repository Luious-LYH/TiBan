"""Persist bounded session membership for QBank scale and navigator state."""

from alembic import op
import sqlalchemy as sa


revision = "d91a4c0ef312"
down_revision = "7c5e2a9d1f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_session_items",
        sa.Column("session_item_id", sa.String(length=150), primary_key=True),
        sa.Column("practice_session_id", sa.String(length=150), sa.ForeignKey("practice_sessions.session_id"), nullable=False),
        sa.Column("question_id", sa.String(length=150), sa.ForeignKey("questions.question_id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("practice_session_id", "ordinal", name="uq_practice_session_item_ordinal"),
        sa.UniqueConstraint("practice_session_id", "question_id", name="uq_practice_session_item_question"),
    )
    op.create_index("ix_practice_session_items_practice_session_id", "practice_session_items", ["practice_session_id"])
    op.create_index("ix_practice_session_items_question_id", "practice_session_items", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_practice_session_items_question_id", table_name="practice_session_items")
    op.drop_index("ix_practice_session_items_practice_session_id", table_name="practice_session_items")
    op.drop_table("practice_session_items")
