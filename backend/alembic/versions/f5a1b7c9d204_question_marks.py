"""Add persistent learner question marks for the V3.1 review flow.

Revision ID: f5a1b7c9d204
Revises: e4c6a1b8f203
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a1b7c9d204"
down_revision: Union[str, Sequence[str], None] = "e4c6a1b8f203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_marks",
        sa.Column("mark_id", sa.String(length=150), nullable=False),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("question_id", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.question_id"]),
        sa.PrimaryKeyConstraint("mark_id"),
        sa.UniqueConstraint("learner_id", "question_id", name="uq_question_mark_learner_question"),
    )
    op.create_index("ix_question_marks_learner_id", "question_marks", ["learner_id"])
    op.create_index("ix_question_marks_question_id", "question_marks", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_question_marks_question_id", table_name="question_marks")
    op.drop_index("ix_question_marks_learner_id", table_name="question_marks")
    op.drop_table("question_marks")
