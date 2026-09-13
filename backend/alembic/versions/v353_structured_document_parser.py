"""Add structured parsing and media provenance metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v353_structured_parser"
down_revision: Union[str, Sequence[str], None] = "v352_knowledge_folders"
branch_labels = None
depends_on = None


def _add_columns(table: str, columns: list[sa.Column]) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    _add_columns("source_documents", [
        sa.Column("parse_stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    ])
    _add_columns("knowledge_chunks", [
        sa.Column("parent_chunk_id", sa.String(length=150), nullable=True),
        sa.Column("element_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("element_type", sa.String(length=24), nullable=False, server_default="paragraph"),
        sa.Column("page_start", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("page_end", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    ])
    _add_columns("knowledge_media_assets", [
        sa.Column("asset_type", sa.String(length=24), nullable=False, server_default="figure"),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("source_element_id", sa.String(length=180), nullable=True),
        sa.Column("section_path", sa.String(length=500), nullable=True),
    ])
    for name, table, column in (
        ("ix_knowledge_chunks_parent_chunk_id", "knowledge_chunks", "parent_chunk_id"),
        ("ix_knowledge_media_assets_asset_type", "knowledge_media_assets", "asset_type"),
        ("ix_knowledge_media_assets_source_element_id", "knowledge_media_assets", "source_element_id"),
    ):
        indexes = {item.get("name") for item in sa.inspect(op.get_bind()).get_indexes(table)}
        if name not in indexes:
            op.create_index(name, table, [column])


def downgrade() -> None:
    # Columns are additive and may be used by locally retained source history.
    # Alembic downgrade removes only the indexes; data-preserving local bootstrap
    # remains compatible with older application versions.
    for name, table in (
        ("ix_knowledge_media_assets_source_element_id", "knowledge_media_assets"),
        ("ix_knowledge_media_assets_asset_type", "knowledge_media_assets"),
        ("ix_knowledge_chunks_parent_chunk_id", "knowledge_chunks"),
    ):
        if name in {item.get("name") for item in sa.inspect(op.get_bind()).get_indexes(table)}:
            op.drop_index(name, table_name=table)
