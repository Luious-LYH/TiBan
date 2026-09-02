"""Add durable V3.1 learning-coach conversations.

Revision ID: b7c3e1d4f208
Revises: 9a2f6c8d1e30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c3e1d4f208"
down_revision: Union[str, Sequence[str], None] = "9a2f6c8d1e30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("conversation_id", sa.String(length=150), primary_key=True),
        sa.Column("learner_id", sa.String(length=100), nullable=False),
        sa.Column("agent_profile", sa.String(length=40), nullable=False, server_default="coach"),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_conversations_learner_id", "agent_conversations", ["learner_id"])
    op.create_index("ix_agent_conversations_agent_profile", "agent_conversations", ["agent_profile"])
    op.create_index("ix_agent_conversations_updated_at", "agent_conversations", ["updated_at"])
    op.create_table(
        "agent_messages",
        sa.Column("message_id", sa.String(length=150), primary_key=True),
        sa.Column("conversation_id", sa.String(length=150), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("activity", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("sources", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.conversation_id"]),
    )
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_index("ix_agent_messages_created_at", "agent_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_messages_created_at", table_name="agent_messages")
    op.drop_index("ix_agent_messages_conversation_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_conversations_updated_at", table_name="agent_conversations")
    op.drop_index("ix_agent_conversations_agent_profile", table_name="agent_conversations")
    op.drop_index("ix_agent_conversations_learner_id", table_name="agent_conversations")
    op.drop_table("agent_conversations")
