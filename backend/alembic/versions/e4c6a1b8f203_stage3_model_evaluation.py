"""Persist model-evaluation run metadata and structured cases, never secrets."""

from alembic import op
import sqlalchemy as sa


revision = "e4c6a1b8f203"
down_revision = "d91a4c0ef312"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_datasets",
        sa.Column("dataset_id", sa.String(length=120), primary_key=True),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_dataset", sa.String(length=120), nullable=False),
        sa.Column("modality", sa.String(length=30), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("dataset_hash", sa.String(length=128), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("supports_vision", sa.Boolean(), nullable=False),
        sa.Column("tutor_indexed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "eval_dataset_versions",
        sa.Column("dataset_version_id", sa.String(length=150), primary_key=True),
        sa.Column("dataset_id", sa.String(length=120), sa.ForeignKey("eval_datasets.dataset_id"), nullable=False, index=True),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("dataset_hash", sa.String(length=128), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "eval_runs",
        sa.Column("eval_run_id", sa.String(length=150), primary_key=True),
        sa.Column("dataset_id", sa.String(length=120), nullable=False, index=True),
        sa.Column("dataset_version", sa.String(length=120), nullable=False),
        sa.Column("dataset_hash", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=180), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, index=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("aggregate", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "eval_cases",
        sa.Column("eval_case_id", sa.String(length=150), primary_key=True),
        sa.Column("eval_run_id", sa.String(length=150), sa.ForeignKey("eval_runs.eval_run_id"), nullable=False, index=True),
        sa.Column("source_item_id", sa.String(length=200), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("candidate_output", sa.Text(), nullable=False),
        sa.Column("parsed_answer", sa.String(length=100), nullable=True),
        sa.Column("gold_answer", sa.String(length=100), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("valid_parse", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column("task", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "eval_artifacts",
        sa.Column("artifact_id", sa.String(length=150), primary_key=True),
        sa.Column("eval_run_id", sa.String(length=150), sa.ForeignKey("eval_runs.eval_run_id"), nullable=False, index=True),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("eval_artifacts")
    op.drop_table("eval_cases")
    op.drop_table("eval_runs")
    op.drop_table("eval_dataset_versions")
    op.drop_table("eval_datasets")
