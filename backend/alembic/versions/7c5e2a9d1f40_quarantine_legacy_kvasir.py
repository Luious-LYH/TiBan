"""Apply the Kvasir suitability gate to legacy Stage 2 seed rows."""

from alembic import op
import sqlalchemy as sa


revision = "7c5e2a9d1f40"
down_revision = "6f3a1d4c8b29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE questions
            SET business_usage = 'generation_source',
                derived_from_dataset = 'Kvasir-VQA',
                license_gate_status = 'allow_noncommercial',
                source_uri = 'https://github.com/ENDObenchmark/Kvasir-VQA'
            WHERE source_dataset = 'Kvasir-VQA'
              AND source_item_id IS NULL
              AND business_usage <> 'generation_source'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE questions
            SET business_usage = 'user_ready',
                derived_from_dataset = NULL,
                license_gate_status = 'needs_review',
                source_uri = NULL
            WHERE source_dataset = 'Kvasir-VQA'
              AND source_item_id IS NULL
            """
        )
    )
