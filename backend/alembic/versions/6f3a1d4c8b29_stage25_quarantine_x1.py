"""Quarantine legacy VQA seed rows from the learner QBank."""

from alembic import op
import sqlalchemy as sa


revision = "6f3a1d4c8b29"
down_revision = "5e1a7d9c2f10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older Stage 2 fixtures used VQA-derived questions as product samples.
    # Preserve them for audit/research, but make the Stage 2.5 suitability
    # policy explicit. Curated Kvasir rows have a source_item_id and remain
    # user_ready in the dedicated bank.
    op.execute(
        sa.text(
            """
            UPDATE questions
            SET business_usage = 'generation_source',
                derived_from_dataset = 'Kvasir-VQA-x1',
                license_gate_status = 'allow_noncommercial',
                source_uri = 'https://github.com/ENDObenchmark/Kvasir-VQA-x1'
            WHERE source_dataset = 'Kvasir-VQA-x1'
              AND business_usage <> 'generation_source'
            """
        )
    )
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
    op.execute(
        sa.text(
            """
            UPDATE question_banks
            SET question_count = (
                SELECT COUNT(*) FROM questions q
                WHERE q.bank_id = question_banks.bank_id
                  AND q.business_usage = 'user_ready'
            )
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
            WHERE source_dataset IN ('Kvasir-VQA', 'Kvasir-VQA-x1')
              AND source_item_id IS NULL
            """
        )
    )
