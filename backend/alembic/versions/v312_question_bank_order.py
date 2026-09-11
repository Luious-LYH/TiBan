"""Persist the user-managed question-bank catalog order."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v312_question_bank_order"
down_revision: Union[str, Sequence[str], None] = "v312_question_bank_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "question_banks",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    # Existing installations keep their current name-based order until a user
    # explicitly changes it in the management view.  Positive values make the
    # persisted ordering unambiguous; later imports are appended by bootstrap.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT bank_id FROM question_banks ORDER BY name, bank_id")
    ).fetchall()
    for position, (bank_id,) in enumerate(rows, start=1):
        bind.execute(
            sa.text("UPDATE question_banks SET display_order = :display_order WHERE bank_id = :bank_id"),
            {"display_order": position, "bank_id": bank_id},
        )
    # SQLite cannot change a column default with ALTER COLUMN.  The default is
    # only needed while adding/backfilling the column, so leave it in place on
    # SQLite; SQLAlchemy model writes still provide the explicit order value.
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("question_banks", "display_order", server_default=None)


def downgrade() -> None:
    op.drop_column("question_banks", "display_order")
