"""Add frozen Evaluation Lab suites and durable experiment runs.

Revision ID: f2b3c4d5e6f7
Revises: e8f4c2a9b316
"""

from alembic import op
import sqlalchemy as sa


revision = "f2b3c4d5e6f7"
down_revision = "e8f4c2a9b316"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_suites",
        sa.Column("suite_id", sa.String(length=150), primary_key=True),
        sa.Column("bank_id", sa.String(length=100), sa.ForeignKey("question_banks.bank_id"), nullable=False),
        sa.Column("domain_id", sa.String(length=100), nullable=False),
        sa.Column("bank_version", sa.String(length=80), nullable=False),
        sa.Column("bank_hash", sa.String(length=128), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("suite_hash", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name in ("bank_id", "domain_id", "suite_hash"):
        op.create_index(f"ix_eval_suites_{name}", "eval_suites", [name])
    op.create_table(
        "eval_experiments",
        sa.Column("experiment_id", sa.String(length=150), primary_key=True),
        sa.Column("experiment_type", sa.String(length=24), nullable=False),
        sa.Column("suite_id", sa.String(length=150), sa.ForeignKey("eval_suites.suite_id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("fixed_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    for name in ("experiment_type", "suite_id", "status"):
        op.create_index(f"ix_eval_experiments_{name}", "eval_experiments", [name])
    op.create_table(
        "eval_lab_runs",
        sa.Column("run_id", sa.String(length=150), primary_key=True),
        sa.Column("experiment_id", sa.String(length=150), sa.ForeignKey("eval_experiments.experiment_id"), nullable=False),
        sa.Column("job_id", sa.String(length=150), sa.ForeignKey("background_jobs.job_id"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=180), nullable=False),
        sa.Column("retrieval_profile", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("aggregate", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    for name in ("experiment_id", "job_id", "status"):
        op.create_index(f"ix_eval_lab_runs_{name}", "eval_lab_runs", [name])
    op.create_table(
        "eval_lab_cases",
        sa.Column("case_id", sa.String(length=150), primary_key=True),
        sa.Column("run_id", sa.String(length=150), sa.ForeignKey("eval_lab_runs.run_id"), nullable=False),
        sa.Column("question_id", sa.String(length=150), sa.ForeignKey("questions.question_id"), nullable=False),
        sa.Column("valid_response", sa.Boolean(), nullable=False),
        sa.Column("provider_success", sa.Boolean(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("gold_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_eval_lab_cases_run_id", "eval_lab_cases", ["run_id"])
    op.create_index("ix_eval_lab_cases_question_id", "eval_lab_cases", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_lab_cases_question_id", table_name="eval_lab_cases")
    op.drop_index("ix_eval_lab_cases_run_id", table_name="eval_lab_cases")
    op.drop_table("eval_lab_cases")
    for name in ("status", "job_id", "experiment_id"):
        op.drop_index(f"ix_eval_lab_runs_{name}", table_name="eval_lab_runs")
    op.drop_table("eval_lab_runs")
    for name in ("status", "suite_id", "experiment_type"):
        op.drop_index(f"ix_eval_experiments_{name}", table_name="eval_experiments")
    op.drop_table("eval_experiments")
    for name in ("suite_hash", "domain_id", "bank_id"):
        op.drop_index(f"ix_eval_suites_{name}", table_name="eval_suites")
    op.drop_table("eval_suites")
