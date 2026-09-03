"""Store non-secret Evaluation Lab candidate endpoint identity.

Revision ID: f3b4c5d6e7f8
Revises: f2b3c4d5e6f7
"""

from alembic import op
import sqlalchemy as sa


revision = "f3b4c5d6e7f8"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("eval_lab_runs")}
    if "provider_base_url" not in columns:
        op.add_column(
            "eval_lab_runs",
            sa.Column("provider_base_url", sa.Text(), nullable=False, server_default=""),
        )
    # Model candidates are identified by endpoint + model. RAG baseline and
    # variants deliberately share the same answer model, so their non-null
    # retrieval profile must not collide with this candidate guard.
    indexes = {item.get("name") for item in inspector.get_indexes("eval_lab_runs")}
    if "uq_eval_lab_run_endpoint_model" not in indexes:
        op.create_index(
            "uq_eval_lab_run_endpoint_model",
            "eval_lab_runs",
            ["experiment_id", "provider_base_url", "model"],
            unique=True,
            sqlite_where=sa.text("retrieval_profile IS NULL OR retrieval_profile = 'null'"),
            postgresql_where=sa.text("retrieval_profile IS NULL OR retrieval_profile = 'null'::json"),
        )


def downgrade() -> None:
    op.drop_index("uq_eval_lab_run_endpoint_model", table_name="eval_lab_runs")
    op.drop_column("eval_lab_runs", "provider_base_url")
