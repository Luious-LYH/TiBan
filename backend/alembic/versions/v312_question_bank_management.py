"""Add restart-safe deletion records for user-managed question banks."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v312_question_bank_management"
down_revision: Union[str, Sequence[str], None] = "v312_question_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_bank_deletions",
        sa.Column("bank_id", sa.String(length=100), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("bank_id"),
    )


def downgrade() -> None:
    op.drop_table("question_bank_deletions")
