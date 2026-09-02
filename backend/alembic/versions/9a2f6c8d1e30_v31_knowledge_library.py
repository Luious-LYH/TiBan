"""Add explicit source-library metadata for V3.1 Knowledge.

Revision ID: 9a2f6c8d1e30
Revises: f5a1b7c9d204
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a2f6c8d1e30"
down_revision: Union[str, Sequence[str], None] = "f5a1b7c9d204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("source_scope", sa.String(length=32), nullable=False, server_default="system"))
    op.add_column("source_documents", sa.Column("file_name", sa.String(length=300), nullable=True))
    op.add_column("source_documents", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("source_documents", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("source_documents", sa.Column("parser_version", sa.String(length=80), nullable=True))
    op.add_column("source_documents", sa.Column("embedding_model", sa.String(length=180), nullable=True))
    op.add_column("source_documents", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE source_documents SET source_scope = 'qbank_explanations' WHERE namespace = 'qbank_explanations'")
    op.execute("UPDATE source_documents SET source_scope = 'user' WHERE business_usage = 'factory_source'")
    op.execute("UPDATE source_documents SET file_name = name WHERE file_name IS NULL")
    op.execute("UPDATE source_documents SET updated_at = created_at WHERE updated_at IS NULL")
    op.create_index("ix_source_documents_source_scope", "source_documents", ["source_scope"])
    op.create_index("ix_source_documents_enabled", "source_documents", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_source_documents_enabled", table_name="source_documents")
    op.drop_index("ix_source_documents_source_scope", table_name="source_documents")
    for name in ("updated_at", "embedding_model", "parser_version", "enabled", "size_bytes", "file_name", "source_scope"):
        op.drop_column("source_documents", name)
