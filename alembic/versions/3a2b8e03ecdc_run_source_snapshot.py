"""run source snapshot

Revision ID: 3a2b8e03ecdc
Revises: 6f3cd64059e8
Create Date: 2026-09-28 08:51:52.963370

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a2b8e03ecdc"
down_revision: str | Sequence[str] | None = "6f3cd64059e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.add_column(
            sa.Column("sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )

    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.alter_column("sources", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_column("sources")
