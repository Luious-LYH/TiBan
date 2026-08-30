"""Make Question Factory job state durable and recoverable.

Revision ID: b7c9d2e4f610
Revises: a5b6c7d8e9f0
"""

from alembic import op
import sqlalchemy as sa


revision = "b7c9d2e4f610"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("factory_jobs", sa.Column("job_type", sa.String(length=48), nullable=False, server_default="question_factory"))
    op.add_column("factory_jobs", sa.Column("stage", sa.String(length=40), nullable=False, server_default="queued"))
    op.add_column("factory_jobs", sa.Column("progress", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("factory_jobs", sa.Column("input_summary", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("factory_jobs", sa.Column("result_ref", sa.String(length=160), nullable=True))
    op.add_column("factory_jobs", sa.Column("error_code", sa.String(length=80), nullable=True))
    op.add_column("factory_jobs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("factory_jobs", sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("factory_jobs", sa.Column("idempotency_key", sa.String(length=160), nullable=True))
    op.add_column("factory_jobs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("factory_jobs", sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column("factory_jobs", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column("factory_jobs", sa.Column("cancel_requested_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE factory_jobs SET idempotency_key = job_id WHERE idempotency_key IS NULL")
    op.alter_column("factory_jobs", "idempotency_key", nullable=False)
    op.create_index("ix_factory_jobs_idempotency_key", "factory_jobs", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_factory_jobs_idempotency_key", table_name="factory_jobs")
    for column in ("cancel_requested_at", "completed_at", "heartbeat_at", "started_at", "idempotency_key", "attempt", "error_message", "error_code", "result_ref", "input_summary", "progress", "stage", "job_type"):
        op.drop_column("factory_jobs", column)
