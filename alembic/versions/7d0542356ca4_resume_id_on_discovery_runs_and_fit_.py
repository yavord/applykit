"""resume id on discovery runs and fit scores

Revision ID: 7d0542356ca4
Revises: 6b1bafd42563
Create Date: 2026-09-03 13:52:19.835916

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d0542356ca4"
down_revision: str | Sequence[str] | None = "6b1bafd42563"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.add_column(
            sa.Column("resume_id", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(
            sa.Column("resume_rev", sa.Integer(), nullable=False, server_default=sa.text("1"))
        )
        batch_op.alter_column("resume_id", server_default=None)
        batch_op.alter_column("resume_rev", server_default=None)
        batch_op.create_foreign_key(
            "fk_discovery_runs_resume_id_resumes",
            "resumes",
            ["resume_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("fit_scores") as batch_op:
        batch_op.add_column(
            sa.Column("resume_id", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.alter_column("resume_id", server_default=None)
        batch_op.drop_constraint("pk_fit_scores", type_="primary")
        batch_op.create_primary_key("pk_fit_scores", ["job_id", "resume_id"])
        batch_op.create_foreign_key(
            "fk_fit_scores_resume_id_resumes",
            "resumes",
            ["resume_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("fit_scores") as batch_op:
        batch_op.drop_constraint("fk_fit_scores_resume_id_resumes", type_="foreignkey")
        batch_op.drop_constraint("pk_fit_scores", type_="primary")
        batch_op.drop_column("resume_id")
        batch_op.create_primary_key("pk_fit_scores", ["job_id"])

    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_constraint("fk_discovery_runs_resume_id_resumes", type_="foreignkey")
        batch_op.drop_column("resume_id")
        batch_op.drop_column("resume_rev")
