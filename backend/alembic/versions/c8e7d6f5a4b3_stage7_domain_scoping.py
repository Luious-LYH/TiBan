"""Add explicit domain scope to learner-state and evaluation records.

Revision ID: c8e7d6f5a4b3
Revises: b7c9d2e4f610
"""

from alembic import op
import sqlalchemy as sa


revision = "c8e7d6f5a4b3"
down_revision = "b7c9d2e4f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("practice_sessions", "review_cards", "learner_mastery", "learning_memory_items", "eval_datasets"):
        op.add_column(table, sa.Column("domain_id", sa.String(length=100), nullable=False, server_default="endoscopy"))

    # SQLite does not support ALTER TABLE DROP/ADD CONSTRAINT directly.  Batch
    # mode performs the safe copy-and-move that SQLite needs and uses ordinary
    # ALTER statements on PostgreSQL.
    with op.batch_alter_table("learner_mastery", recreate="auto") as batch:
        batch.drop_constraint("uq_mastery_learner_point", type_="unique")
        batch.create_unique_constraint("uq_mastery_learner_domain_point", ["learner_id", "domain_id", "knowledge_point"])
    with op.batch_alter_table("learning_memory_items", recreate="auto") as batch:
        batch.drop_constraint("uq_learning_memory_learner_dedupe", type_="unique")
        batch.create_unique_constraint("uq_learning_memory_learner_domain_dedupe", ["learner_id", "domain_id", "dedupe_key"])
    op.create_index("ix_review_cards_learner_domain_due", "review_cards", ["learner_id", "domain_id", "due_at"])
    op.create_index("ix_learning_memory_learner_domain_status", "learning_memory_items", ["learner_id", "domain_id", "status"])
    # The former Stage 2.5 label was never a product-level domain contract.
    # Keep all rows but normalize them to the first manifest's stable id.
    for table in ("question_banks", "questions", "source_documents"):
        op.execute(sa.text(f"UPDATE {table} SET domain_id = 'endoscopy' WHERE domain_id = 'medical-education'"))


def downgrade() -> None:
    op.drop_index("ix_learning_memory_learner_domain_status", table_name="learning_memory_items")
    op.drop_index("ix_review_cards_learner_domain_due", table_name="review_cards")
    with op.batch_alter_table("learning_memory_items", recreate="auto") as batch:
        batch.drop_constraint("uq_learning_memory_learner_domain_dedupe", type_="unique")
        batch.create_unique_constraint("uq_learning_memory_learner_dedupe", ["learner_id", "dedupe_key"])
    with op.batch_alter_table("learner_mastery", recreate="auto") as batch:
        batch.drop_constraint("uq_mastery_learner_domain_point", type_="unique")
        batch.create_unique_constraint("uq_mastery_learner_point", ["learner_id", "knowledge_point"])
    for table in ("eval_datasets", "learning_memory_items", "learner_mastery", "review_cards", "practice_sessions"):
        op.drop_column(table, "domain_id")
