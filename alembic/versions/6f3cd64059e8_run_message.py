"""run message

Revision ID: 6f3cd64059e8
Revises: 7d0542356ca4
Create Date: 2026-09-26 10:14:29.232969

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f3cd64059e8"
down_revision: str | Sequence[str] | None = "7d0542356ca4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.add_column(sa.Column("message", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_column("message")
