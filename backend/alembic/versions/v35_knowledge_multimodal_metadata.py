"""Add additive knowledge-media metadata for the V3.5 schema.

The migration extends the existing text knowledge library with controlled
media assets and one-hop text/image evidence relations while preserving the
existing text-only path.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v35_knowledge_multimodal"
down_revision: Union[str, Sequence[str], None] = "v35_chat_image_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    for table_name, columns in {
        "source_documents": (
            sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("image_index_status", sa.String(length=24), nullable=False, server_default="empty"),
            sa.Column("image_index_error", sa.Text(), nullable=True),
            sa.Column("graph_status", sa.String(length=24), nullable=False, server_default="empty"),
            sa.Column("graph_node_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("graph_edge_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("graph_error", sa.Text(), nullable=True),
        ),
        "knowledge_chunks": (
            sa.Column("modality", sa.String(length=16), nullable=False, server_default="text"),
            sa.Column("media_asset_ids", sa.JSON(), nullable=False, server_default="[]"),
        ),
    }.items():
        existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table_name, column)

    existing_tables = set(sa.inspect(bind).get_table_names())
    if "knowledge_media_assets" not in existing_tables:
        op.create_table(
            "knowledge_media_assets",
            sa.Column("asset_id", sa.String(length=150), nullable=False),
            sa.Column("document_id", sa.String(length=150), nullable=False),
            sa.Column("version_id", sa.String(length=150), nullable=False),
            sa.Column("storage_path", sa.String(length=400), nullable=False),
            sa.Column("original_filename", sa.String(length=300), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("mime_type", sa.String(length=40), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("page", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("alt_text", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="ready"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["source_documents.document_id"]),
            sa.ForeignKeyConstraint(["version_id"], ["document_versions.version_id"]),
            sa.PrimaryKeyConstraint("asset_id"),
            sa.UniqueConstraint("storage_path"),
        )
    existing_tables.add("knowledge_media_assets")

    if "knowledge_entities" not in existing_tables:
        op.create_table(
            "knowledge_entities",
            sa.Column("entity_id", sa.String(length=150), nullable=False),
            sa.Column("document_id", sa.String(length=150), nullable=False),
            sa.Column("canonical_name", sa.String(length=240), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False, server_default="concept"),
            sa.Column("properties", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["source_documents.document_id"]),
            sa.PrimaryKeyConstraint("entity_id"),
            sa.UniqueConstraint("document_id", "canonical_name", name="uq_knowledge_entity_document_name"),
        )
    existing_tables.add("knowledge_entities")

    if "knowledge_relations" not in existing_tables:
        op.create_table(
            "knowledge_relations",
            sa.Column("relation_id", sa.String(length=150), nullable=False),
            sa.Column("document_id", sa.String(length=150), nullable=False),
            sa.Column("source_entity_id", sa.String(length=150), nullable=False),
            sa.Column("target_entity_id", sa.String(length=150), nullable=False),
            sa.Column("relation_type", sa.String(length=80), nullable=False),
            sa.Column("chunk_id", sa.String(length=150), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.6"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["source_documents.document_id"]),
            sa.ForeignKeyConstraint(["source_entity_id"], ["knowledge_entities.entity_id"]),
            sa.ForeignKeyConstraint(["target_entity_id"], ["knowledge_entities.entity_id"]),
            sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.chunk_id"]),
            sa.PrimaryKeyConstraint("relation_id"),
        )
    for name, table_name, column in (
        ("ix_knowledge_media_assets_document_id", "knowledge_media_assets", "document_id"),
        ("ix_knowledge_media_assets_version_id", "knowledge_media_assets", "version_id"),
        ("ix_knowledge_media_assets_sha256", "knowledge_media_assets", "sha256"),
        ("ix_knowledge_entities_document_id", "knowledge_entities", "document_id"),
        ("ix_knowledge_relations_document_id", "knowledge_relations", "document_id"),
        ("ix_knowledge_relations_source_entity", "knowledge_relations", "source_entity_id"),
        ("ix_knowledge_relations_target_entity", "knowledge_relations", "target_entity_id"),
        ("ix_knowledge_relations_chunk_id", "knowledge_relations", "chunk_id"),
    ):
        indexes = {item.get("name") for item in sa.inspect(bind).get_indexes(table_name)}
        if name not in indexes:
            op.create_index(name, table_name, [column])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for name in ("chunk_id", "target_entity", "source_entity", "document_id"):
        if "knowledge_relations" in tables:
            indexes = {item.get("name") for item in sa.inspect(bind).get_indexes("knowledge_relations")}
            index_name = f"ix_knowledge_relations_{name}"
            if index_name in indexes:
                op.drop_index(index_name, table_name="knowledge_relations")
    for table_name in ("knowledge_relations", "knowledge_entities", "knowledge_media_assets"):
        if table_name in tables:
            op.drop_table(table_name)
    for table_name, columns in {
        "knowledge_chunks": ("media_asset_ids", "modality"),
        "source_documents": (
            "graph_error", "graph_edge_count", "graph_node_count", "graph_status",
            "image_index_error", "image_index_status", "image_count",
        ),
    }.items():
        if table_name in tables:
            existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
            for column in columns:
                if column in existing:
                    op.drop_column(table_name, column)
