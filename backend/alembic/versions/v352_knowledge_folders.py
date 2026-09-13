"""Add learner-facing knowledge folders for TiBan V3.5.2."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v352_knowledge_folders"
down_revision: Union[str, Sequence[str], None] = "v35_knowledge_multimodal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "knowledge_folders" not in tables:
        op.create_table(
            "knowledge_folders",
            sa.Column("folder_id", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("scope", sa.String(length=32), nullable=False, server_default="user"),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("folder_id"),
            sa.UniqueConstraint("name", name="uq_knowledge_folder_name"),
        )
    existing = {column["name"] for column in sa.inspect(bind).get_columns("source_documents")}
    if "folder_id" not in existing:
        op.add_column(
            "source_documents",
            sa.Column("folder_id", sa.String(length=120), nullable=True),
        )
    indexes = {item.get("name") for item in sa.inspect(bind).get_indexes("source_documents")}
    if "ix_source_documents_folder_id" not in indexes:
        op.create_index("ix_source_documents_folder_id", "source_documents", ["folder_id"])
    for name, table_name, column in (
        ("ix_knowledge_folders_scope", "knowledge_folders", "scope"),
        ("ix_knowledge_folders_display_order", "knowledge_folders", "display_order"),
    ):
        indexes = {item.get("name") for item in sa.inspect(bind).get_indexes(table_name)}
        if name not in indexes:
            op.create_index(name, table_name, [column])


def downgrade() -> None:
    bind = op.get_bind()
    if "source_documents" in sa.inspect(bind).get_table_names():
        indexes = {item.get("name") for item in sa.inspect(bind).get_indexes("source_documents")}
        if "ix_source_documents_folder_id" in indexes:
            op.drop_index("ix_source_documents_folder_id", table_name="source_documents")
        if "folder_id" in {column["name"] for column in sa.inspect(bind).get_columns("source_documents")}:
            op.drop_column("source_documents", "folder_id")
    if "knowledge_folders" in sa.inspect(bind).get_table_names():
        for name in ("ix_knowledge_folders_display_order", "ix_knowledge_folders_scope"):
            indexes = {item.get("name") for item in sa.inspect(bind).get_indexes("knowledge_folders")}
            if name in indexes:
                op.drop_index(name, table_name="knowledge_folders")
        op.drop_table("knowledge_folders")
