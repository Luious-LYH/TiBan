"""Add controlled question and chat image assets for TiBan V3.5."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision = "v35_multimodal_assets"
down_revision: Union[str, Sequence[str], None] = "v312_question_bank_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_image_assets",
        sa.Column("asset_id", sa.String(length=150), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("batch_id", sa.String(length=150), nullable=True),
        sa.Column("bank_id", sa.String(length=100), nullable=True),
        sa.Column("storage_path", sa.String(length=300), nullable=False),
        sa.Column("original_filename", sa.String(length=300), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=40), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="staged"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("asset_id"),
        sa.UniqueConstraint("storage_path"),
    )
    for name, column in (
        ("kind", "kind"), ("batch_id", "batch_id"), ("bank_id", "bank_id"),
        ("sha256", "sha256"), ("status", "status"), ("expires_at", "expires_at"),
    ):
        op.create_index(f"ix_question_image_assets_{name}", "question_image_assets", [column])
    op.add_column("agent_messages", sa.Column("image_attached", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tutor_messages", sa.Column("image_attached", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("tutor_messages", "image_attached")
    op.drop_column("agent_messages", "image_attached")
    for name in ("expires_at", "status", "sha256", "bank_id", "batch_id", "kind"):
        op.drop_index(f"ix_question_image_assets_{name}", table_name="question_image_assets")
    op.drop_table("question_image_assets")
