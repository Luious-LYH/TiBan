"""Stage 2.5 data lineage, license gate and retrieval namespace fields."""

from alembic import op
import sqlalchemy as sa


revision = "5e1a7d9c2f10"
down_revision = "8c4fe812d1a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    question_columns = [
        sa.Column("source_item_id", sa.String(length=200), nullable=True),
        sa.Column("derived_from_dataset", sa.String(length=120), nullable=True),
        sa.Column("business_usage", sa.String(length=40), nullable=False, server_default=sa.text("'user_ready'")),
        sa.Column("answer_source", sa.String(length=40), nullable=False, server_default=sa.text("'dataset_gold'")),
        sa.Column("explanation_source", sa.String(length=40), nullable=False, server_default=sa.text("'none'")),
        sa.Column("license_gate_status", sa.String(length=30), nullable=False, server_default=sa.text("'needs_review'")),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("official_explanation_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("subject", sa.String(length=160), nullable=True),
        sa.Column("topic", sa.String(length=160), nullable=True),
    ]
    for column in question_columns:
        op.add_column("questions", column)
    op.create_index("ix_questions_source_item_id", "questions", ["source_item_id"])
    op.create_index("ix_questions_derived_from_dataset", "questions", ["derived_from_dataset"])
    op.create_index("ix_questions_subject", "questions", ["subject"])
    op.create_index("ix_questions_topic", "questions", ["topic"])

    document_columns = [
        sa.Column("source_id", sa.String(length=180), nullable=True),
        sa.Column("business_usage", sa.String(length=40), nullable=False, server_default=sa.text("'knowledge_base'")),
        sa.Column("license_gate_status", sa.String(length=30), nullable=False, server_default=sa.text("'needs_review'")),
        sa.Column("ai_ingestion_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("namespace", sa.String(length=80), nullable=False, server_default=sa.text("'medical_general'")),
        sa.Column("attribution", sa.Text(), nullable=True),
    ]
    for column in document_columns:
        op.add_column("source_documents", column)
    op.create_index("ix_source_documents_source_id", "source_documents", ["source_id"])
    op.create_index("ix_source_documents_namespace", "source_documents", ["namespace"])

    op.add_column("knowledge_chunks", sa.Column("namespace", sa.String(length=80), nullable=False, server_default=sa.text("'medical_general'")))
    op.add_column("knowledge_chunks", sa.Column("source_uri", sa.Text(), nullable=True))
    op.create_index("ix_knowledge_chunks_namespace", "knowledge_chunks", ["namespace"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_namespace", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "source_uri")
    op.drop_column("knowledge_chunks", "namespace")
    op.drop_index("ix_source_documents_namespace", table_name="source_documents")
    op.drop_index("ix_source_documents_source_id", table_name="source_documents")
    for name in ["attribution", "namespace", "source_uri", "ai_ingestion_allowed", "license_gate_status", "business_usage", "source_id"]:
        op.drop_column("source_documents", name)
    for name in ["topic", "subject", "official_explanation_available", "source_uri", "license_gate_status", "explanation_source", "answer_source", "business_usage", "derived_from_dataset", "source_item_id"]:
        op.drop_index(f"ix_questions_{name}", table_name="questions") if name in {"topic", "subject", "derived_from_dataset", "source_item_id"} else None
        op.drop_column("questions", name)
