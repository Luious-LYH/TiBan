"""Stage 2 FSRS state and factory queue trace.

Revision ID: 8c4fe812d1a7
Revises: 3d1c6a99d8c4
"""

from alembic import op
import sqlalchemy as sa


revision = "8c4fe812d1a7"
down_revision = "3d1c6a99d8c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_cards", sa.Column("fsrs_card", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("review_cards", sa.Column("fsrs_logs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("review_cards", sa.Column("difficulty", sa.Float(), nullable=True))
    op.add_column("review_cards", sa.Column("stability", sa.Float(), nullable=True))
    op.add_column("review_cards", sa.Column("retrievability", sa.Float(), nullable=True))
    op.add_column("review_cards", sa.Column("fsrs_state", sa.String(length=32), nullable=False, server_default="Learning"))
    op.add_column("factory_jobs", sa.Column("queue_message_id", sa.String(length=160), nullable=True))
    op.add_column("question_revisions", sa.Column("source_chunk_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("question_revisions", "source_chunk_ids")
    op.drop_column("factory_jobs", "queue_message_id")
    op.drop_column("review_cards", "fsrs_state")
    op.drop_column("review_cards", "retrievability")
    op.drop_column("review_cards", "stability")
    op.drop_column("review_cards", "difficulty")
    op.drop_column("review_cards", "fsrs_logs")
    op.drop_column("review_cards", "fsrs_card")
