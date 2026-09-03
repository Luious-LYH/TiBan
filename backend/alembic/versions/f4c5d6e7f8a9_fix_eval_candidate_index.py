"""Make model candidate identity enforcement work with JSON null storage.

Revision ID: f4c5d6e7f8a9
Revises: f3b4c5d6e7f8
"""

from alembic import op
import sqlalchemy as sa


revision = "f4c5d6e7f8a9"
down_revision = "f3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {item.get("name") for item in inspector.get_indexes("eval_lab_runs")}
    if "uq_eval_lab_run_endpoint_model" in indexes:
        op.drop_index("uq_eval_lab_run_endpoint_model", table_name="eval_lab_runs")

    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.create_index(
            "uq_eval_lab_run_endpoint_model",
            "eval_lab_runs",
            ["experiment_id", "provider_base_url", "model"],
            unique=True,
            sqlite_where=sa.text("retrieval_profile IS NULL OR retrieval_profile = 'null'"),
        )
    elif dialect == "postgresql":
        op.create_index(
            "uq_eval_lab_run_endpoint_model",
            "eval_lab_runs",
            ["experiment_id", "provider_base_url", "model"],
            unique=True,
            postgresql_where=sa.text("retrieval_profile IS NULL OR retrieval_profile = 'null'::json"),
        )
    else:
        # The application supports PostgreSQL and SQLite. Keep a safe
        # fallback for schema inspection tools using another SQL dialect.
        op.create_index(
            "uq_eval_lab_run_endpoint_model",
            "eval_lab_runs",
            ["experiment_id", "provider_base_url", "model"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_eval_lab_run_endpoint_model", table_name="eval_lab_runs")
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.create_index(
            "uq_eval_lab_run_endpoint_model",
            "eval_lab_runs",
            ["experiment_id", "provider_base_url", "model"],
            unique=True,
            sqlite_where=sa.text("retrieval_profile IS NULL"),
        )
    elif dialect == "postgresql":
        op.create_index(
            "uq_eval_lab_run_endpoint_model",
            "eval_lab_runs",
            ["experiment_id", "provider_base_url", "model"],
            unique=True,
            postgresql_where=sa.text("retrieval_profile IS NULL"),
        )
