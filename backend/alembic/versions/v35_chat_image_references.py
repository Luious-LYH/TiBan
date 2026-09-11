"""Persist opaque references for short-lived chat image attachments."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision = "v35_chat_image_refs"
down_revision: Union[str, Sequence[str], None] = "v35_multimodal_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("agent_messages", "tutor_messages"):
        op.add_column(table_name, sa.Column("image_asset_id", sa.String(length=150), nullable=True))
        op.create_index(f"ix_{table_name}_image_asset_id", table_name, ["image_asset_id"])


def downgrade() -> None:
    for table_name in ("tutor_messages", "agent_messages"):
        op.drop_index(f"ix_{table_name}_image_asset_id", table_name=table_name)
        op.drop_column(table_name, "image_asset_id")
