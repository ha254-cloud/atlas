"""add payer approval and monitoring fields

Revision ID: 14d669265fc7
Revises: a1c7e4b9d2f3
Create Date: 2026-10-28 18:48:51.266627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14d669265fc7'
down_revision: Union[str, Sequence[str], None] = 'a1c7e4b9d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "payers",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            nullable=False,
            server_default="approved",
        ),
    )
    op.add_column("payers", sa.Column("submitted_by", sa.Integer(), nullable=True))
    op.add_column(
        "payers", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("payers", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column(
        "payers", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("payers", sa.Column("rejected_by", sa.Integer(), nullable=True))
    op.add_column(
        "payers", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "payers", sa.Column("rejection_reason", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "payers",
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payers", sa.Column("last_health_status", sa.String(length=20), nullable=True)
    )
    op.add_column("payers", sa.Column("last_health_error", sa.Text(), nullable=True))
    op.add_column(
        "payers",
        sa.Column(
            "health_check_failure_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_foreign_key(
        "fk_payers_submitted_by_users",
        "payers",
        "users",
        ["submitted_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_payers_approved_by_users",
        "payers",
        "users",
        ["approved_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_payers_rejected_by_users",
        "payers",
        "users",
        ["rejected_by"],
        ["id"],
    )
    op.create_index(
        "ix_payers_approval_status", "payers", ["approval_status"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_payers_approval_status", table_name="payers")
    op.drop_constraint("fk_payers_rejected_by_users", "payers", type_="foreignkey")
    op.drop_constraint("fk_payers_approved_by_users", "payers", type_="foreignkey")
    op.drop_constraint("fk_payers_submitted_by_users", "payers", type_="foreignkey")

    op.drop_column("payers", "health_check_failure_count")
    op.drop_column("payers", "last_health_error")
    op.drop_column("payers", "last_health_status")
    op.drop_column("payers", "last_health_checked_at")
    op.drop_column("payers", "rejection_reason")
    op.drop_column("payers", "rejected_at")
    op.drop_column("payers", "rejected_by")
    op.drop_column("payers", "approved_at")
    op.drop_column("payers", "approved_by")
    op.drop_column("payers", "submitted_at")
    op.drop_column("payers", "submitted_by")
    op.drop_column("payers", "approval_status")
